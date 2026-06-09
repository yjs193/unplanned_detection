from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = None
    StateGraph = None

from .sample_data import CAMERA_MAPPINGS, SAMPLE_TICKETS


WORK_TYPE_SYNONYMS = {
    "wire_and_cable_stringing": ["展放", "导线", "地线", "光缆", "架线"],
    "wire_tensioning": ["紧线"],
    "crimping": ["压接"],
    "accessory_installation": ["附件安装"],
    "crossing_frame_erection": ["跨越架"],
    "protective_net_installation": ["封网"],
    "retaining_wall_construction": ["挡土墙"],
    "earthwork_excavation": ["土方开挖", "开挖", "基坑", "沟槽"],
    "foundation_construction": ["地基", "基础", "桩", "承台"],
    "rebar_binding": ["钢筋绑扎"],
    "formwork_installation": ["模板"],
    "concrete_pouring": ["混凝土", "浇筑"],
    "material_transport": ["材料转运", "物料转运"],
    "lifting_operation": ["吊装", "起重", "吊车"],
    "transformer_installation": ["变压器", "主变", "电抗器"],
    "grounding_grid_installation": ["接地网", "接地"],
    "power_outage_coordination": ["停电", "邻电", "运行区域"],
}

FIELD_STOP_LABELS = [
    "工程名称", "项目名称", "编号", "计划编号", "作业票编号", "初勘风险等级", "复测后风险等级",
    "风险等级", "涉及中高风险作业", "工作地点", "作业地点", "施工地点", "作业部位及内容",
    "作业内容", "工作内容", "计划开始时间", "计划结束时间", "执行的施工方案名称",
    "作业是否需要停电配合", "是否在运行区域或邻电作业", "主要危害", "施工必备工器具",
    "计划状态", "执行状态", "工作负责人", "负责人", "施工单位",
]


class ParseState(TypedDict, total=False):
    raw_text: str
    source_type: str
    ticket_fact: dict[str, Any]
    work_content_items: list[str]
    normalized_work_types: list[str]
    validation_result: dict[str, Any]
    media_query_task: dict[str, Any]
    media_manifest: list[dict[str, Any]]


def _normalize_ticket_text(text: str) -> str:
    replacements = {
        "执行的施工方案名\n称": "执行的施工方案名称",
        "作业是否需要停电\n配合": "作业是否需要停电配合",
        "是否在运行区域或\n邻电作业": "是否在运行区域或邻电作业",
        "作业部位及内\n容": "作业部位及内容",
        "初勘风险等\n级": "初勘风险等级",
        "复测后风险等\n级": "复测后风险等级",
        "计划开始时\n间": "计划开始时间",
        "计划结束时\n间": "计划结束时间",
        "班长（现场作业负\n责人）": "班长（现场作业负责人）",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.replace("\u3000", " ")


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = value.strip().strip(" \t。。，,、>“”'\"□☑þ")
    value = re.sub(r"^[:：；;]+", "", value).strip()
    return value


def _is_stop_line(line: str, labels: list[str] | None = None) -> bool:
    compact = re.sub(r"\s+", "", line)
    for label in labels or FIELD_STOP_LABELS:
        if compact == label or compact.startswith(label) or compact.startswith(f"{label}：") or compact.startswith(f"{label}:"):
            return True
    return False


def _field(text: str, labels: list[str]) -> str:
    text = _normalize_ticket_text(text)
    for label in labels:
        match = re.search(rf"{label}[：:；;]\s*([^\n\r]+)", text)
        if match:
            return _clean_value(match.group(1))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact_labels = [re.sub(r"\s+", "", label) for label in labels]
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        if any(compact == label or compact.endswith(label) for label in compact_labels):
            values = []
            for candidate in lines[index + 1 : index + 8]:
                if _is_stop_line(candidate):
                    break
                values.append(candidate)
                if len("".join(values)) >= 160:
                    break
            return _clean_value(" ".join(values))
    return ""


def _extract_title(text: str) -> str:
    for line in _normalize_ticket_text(text).splitlines()[:12]:
        line = _clean_value(line)
        if "作业票" in line and 6 <= len(line) <= 80:
            return line
    return ""


def _normalize_plan_status(plan_status: str, execution_status: str, text: str) -> str:
    if plan_status in {"待开工", "开工中", "已完工"}:
        return plan_status
    combined = f"{plan_status} {execution_status} {text}"
    if any(word in combined for word in ["已完工", "已收工", "完工", "收工"]):
        return "已完工"
    if any(word in combined for word in ["开工", "施工中", "正在施工", "现场施工"]):
        return "开工中"
    return "待开工"


def _normalize_execution_status(execution_status: str, plan_status: str) -> str:
    if plan_status == "待开工":
        return "待开工"
    if plan_status == "已完工":
        return "已收工"
    if any(word in execution_status for word in ["已收工", "完工", "收工"]):
        return "已收工"
    return "现场施工中"


def _extract_time_range(text: str) -> dict[str, str]:
    patterns = [
        r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+\d{1,2}:\d{2})\s*(?:至|~|-)\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+\d{1,2}:\d{2})",
        r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)\s*(?:至|~|-)\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {"start": _normalize_dt(match.group(1)), "end": _normalize_dt(match.group(2))}
    return {"start": "", "end": ""}


def _normalize_dt(value: str) -> str:
    cleaned = value.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    cleaned = re.sub(r"-(\d)(?=-)", r"-0\1", cleaned)
    cleaned = re.sub(r"-(\d)(\s|$)", r"-0\1\2", cleaned)
    return cleaned.strip()


def _extract_work_scope(text: str) -> list[str]:
    candidates = set(re.findall(r"(?:构架-)?[LS]\d+(?:-[LS]?\d+)?|L\d+塔|S\d+塔", text, flags=re.I))
    location = _field(text, ["作业地点", "工作地点", "施工地点"])
    if location:
        for chunk in re.split(r"[、,，；;]", location):
            chunk = chunk.strip()
            if chunk and len(chunk) <= 24:
                candidates.add(chunk)
    if "挡土墙" in text:
        candidates.add("挡土墙")
    return sorted(candidates)


def _split_work_items(text: str) -> list[str]:
    content = _extract_work_content(text)
    if not content and "巡查问题" in text:
        content = _field(text, ["巡查问题"])
    content = content or text
    pieces = [p.strip(" 。；;，,") for p in re.split(r"[；;。]", content) if p.strip(" 。；;，,")]
    merged: list[str] = []
    for piece in pieces:
        if len(piece) <= 2:
            continue
        if len(piece) > 50 and "：" in piece:
            piece = piece.split("：", 1)[1]
        merged.append(piece)
    return merged[:12]


def _normalize_work_types(items: list[str]) -> list[str]:
    text = " ".join(items)
    result = []
    for code, keywords in WORK_TYPE_SYNONYMS.items():
        if any(k in text for k in keywords):
            result.append(code)
    return result


def _infer_scene_tags(text: str, work_types: list[str]) -> list[str]:
    tags = set()
    if any(k in text for k in ["塔", "架线", "构架", "高处"]):
        tags.add("高处作业")
    if any(k in text for k in ["吊装", "转运", "材料"]):
        tags.add("物料转运")
    if any(k in text for k in ["挡土墙", "混凝土", "基础", "钢筋", "土方", "基坑"]):
        tags.add("土建施工")
    if any(k in text for k in ["变压器", "主变", "电抗器"]):
        tags.add("主变设备作业")
    if any(k in text for k in ["停电", "邻电", "运行区域"]):
        tags.add("电气安全管控")
    if "retaining_wall_construction" in work_types:
        tags.add("挡土墙作业")
    tags.add("户外作业")
    return sorted(tags)


def _match_camera_mapping(ticket_fact: dict[str, Any]) -> dict[str, Any] | None:
    haystack = " ".join(
        [
            ticket_fact.get("project_name", ""),
            ticket_fact.get("work_location", ""),
            " ".join(ticket_fact.get("work_scope", [])),
            ticket_fact.get("work_content_raw", ""),
        ]
    )
    scored = []
    for mapping in CAMERA_MAPPINGS:
        score = 0
        for keyword in mapping["project_keywords"] + mapping["location_keywords"]:
            if keyword and keyword in haystack:
                score += 1
        if score:
            scored.append((score, mapping))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _media_manifest(mapping: dict[str, Any] | None, media_type: list[str]) -> list[dict[str, Any]]:
    if not mapping:
        return []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    manifest = []
    for idx, camera in enumerate(mapping["cameras"], start=1):
        manifest.append(
            {
                "media_id": f"media_{idx:03d}",
                "media_type": "image" if "image" in media_type else "video",
                "camera_id": camera["camera_id"],
                "camera_name": camera["camera_name"],
                "capture_time": now,
                "file_path": f"/mock-media/{camera['camera_id']}/{datetime.now():%Y%m%d_%H%M%S}.jpg",
                "confidence": 0.86 if idx == 1 else 0.72,
            }
        )
    manifest.append(
        {
            "media_id": "uav_task_001",
            "media_type": "uav_route",
            "camera_id": mapping["uav_route"]["route_id"],
            "camera_name": mapping["uav_route"]["route_name"],
            "capture_time": "待派发",
            "file_path": "/mock-uav/task/uav_task_001",
            "confidence": 0.78,
        }
    )
    return manifest


def _clean_block_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line.replace("\u3000", " ")).strip()
    line = line.strip(" \t>“”'\"")
    line = re.sub(r"^[:：；;]+", "", line).strip()
    return line


def _join_block_lines(lines: list[str]) -> str:
    cleaned = [_clean_block_line(line) for line in lines if _clean_block_line(line)]
    text = "".join(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[A-Za-z0-9#])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[A-Za-z0-9#])", "", text)
    return text.strip(" ；;")


def _extract_block(text: str, start_labels: list[str], end_labels: list[str], max_chars: int = 5000) -> str:
    text = _normalize_ticket_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact_start = [re.sub(r"\s+", "", item) for item in start_labels]
    compact_end = [re.sub(r"\s+", "", item) for item in end_labels]
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        matched_label = next((label for label in compact_start if compact == label or compact.startswith(f"{label}：") or compact.startswith(f"{label}:")), None)
        if not matched_label:
            continue
        values: list[str] = []
        for label in start_labels:
            inline = re.match(rf"{label}[：:；;]\s*(.+)$", line)
            if inline:
                values.append(inline.group(1))
                break
        for candidate in lines[index + 1:]:
            candidate_compact = re.sub(r"\s+", "", candidate)
            if any(candidate_compact == end or candidate_compact.startswith(f"{end}：") or candidate_compact.startswith(f"{end}:") for end in compact_end):
                break
            values.append(candidate)
            if len("".join(values)) >= max_chars:
                break
        return _join_block_lines(values)
    return ""


def _extract_project_name(text: str) -> str:
    return _extract_block(
        text,
        ["工程名称", "项目名称"],
        ["编号", "计划编号", "作业票编号", "初勘风险等级", "复测后风险等级"],
        max_chars=300,
    ) or _field(text, ["工程名称", "项目名称"])


def _extract_work_content(text: str) -> str:
    return _extract_block(
        text,
        ["作业部位及内容", "作业内容", "工作内容", "施工内容"],
        ["计划开始时间", "计划结束时间", "执行的施工方案名称", "作业是否需要停电配合"],
        max_chars=8000,
    ) or _field(text, ["作业部位及内容", "作业内容", "工作内容", "施工内容"])


def _extract_construction_plan(text: str) -> str:
    return _extract_block(
        text,
        ["执行的施工方案名称"],
        ["作业是否需要停电配合", "是否在运行区域或邻电作业", "主要危害"],
        max_chars=400,
    ) or _field(text, ["执行的施工方案名称"])



def _split_work_content_phrases(content: str) -> list[str]:
    content = _clean_value(content)
    if not content:
        return []
    normalized = re.sub(r"\s+", "", content)
    normalized = re.sub(r"(?<!\d)(\d{1,2})[、.．]", r"；\1、", normalized)
    parts = [part.strip("；;。,.，、 ") for part in re.split(r"[；;。]", normalized) if part.strip("；;。,.，、 ")]
    cleaned: list[str] = []
    for part in parts:
        part = re.sub(r"^\d{1,2}[、.．]", "", part).strip()
        if not part:
            continue
        if len(part) <= 80 and part not in cleaned:
            cleaned.append(part)
    return cleaned[:12]


def _extract_work_content_intelligence(content: str) -> dict[str, Any]:
    areas = []
    area_patterns = [
        r"10kV#?\d+[A-Z]?高压室", r"10kV#?\d+[A-Z]?接地变室", r"10kV#?\d+[A-Z]?电容器室",
        r"110kV#?\d+主变室", r"110kVGIS室", r"110kV GIS室", r"#?\d+主变风机房",
        r"二层", r"三层", r"四层", r"电缆层区域", r"工具间", r"休息室",
    ]
    for pattern in area_patterns:
        for item in re.findall(pattern, content):
            normalized = item.replace(" ", "")
            if normalized not in areas:
                areas.append(normalized)
    work_phrases = _split_work_content_phrases(content)
    action_keywords = [
        "安全文明施工", "土方开挖", "基坑支护", "基坑监测", "内支撑焊接", "钢筋绑扎", "模板安装", "混凝土浇筑",
        "封堵", "新建", "拆除", "迁移", "开孔", "加固", "改造", "安装", "回填", "开凿", "收货", "进退场",
        "动火", "浇筑", "支模", "绑扎", "开挖", "砌筑", "砌砖", "制作", "焊接", "监测", "支护", "破除", "敷设", "接线",
    ]
    actions = [item for item in action_keywords if item in content]
    subsumed_actions = {
        "开挖": ["土方开挖"],
        "焊接": ["内支撑焊接"],
        "监测": ["基坑监测"],
        "支护": ["基坑支护"],
        "绑扎": ["钢筋绑扎"],
        "浇筑": ["混凝土浇筑"],
        "安装": ["模板安装"],
    }
    actions = [item for item in actions if not any(full in actions for full in subsumed_actions.get(item, []))]
    target_keywords = [
        "预埋槽钢", "主变基础埋件", "油池", "主变基础", "端子箱", "风冷箱", "母线桥支架", "中性点支架基础",
        "消防管道", "GIS室基础埋件", "电缆沟", "电缆沟孔洞", "冷凝水水管", "穿墙孔", "不锈钢折叠大门",
        "排油检查井", "排油管", "防火阀", "排风机", "照明", "动力", "接地", "卵石", "隔墙", "管线",
        "基坑", "内支撑", "土方", "桩基础", "围蔽",
    ]
    targets = [item for item in target_keywords if item in content]
    special_operations = [item for item in ["动火作业", "邻电作业", "停电配合", "高处作业", "起重吊装"] if item in content]
    if "动火" in content and "动火作业" not in special_operations:
        special_operations.append("动火作业")
    summary_parts = []
    if work_phrases:
        summary_parts.append(f"本次作业包括：{'；'.join(work_phrases[:6])}")
    if areas:
        summary_parts.append(f"涉及作业区域：{'、'.join(areas[:8])}")
    if actions:
        summary_parts.append(f"主要动作：{'、'.join(actions[:10])}")
    if targets:
        summary_parts.append(f"主要对象：{'、'.join(targets[:10])}")
    return {
        "work_areas": areas[:20],
        "work_actions": actions[:20],
        "equipment_targets": targets[:24],
        "special_operations": special_operations,
        "work_content_summary": ("。".join(summary_parts) + "。") if summary_parts else (content[:180] + ("..." if len(content) > 180 else "")),
    }


def _extract_section(text: str, start_label: str, end_labels: list[str], max_chars: int = 12000) -> str:
    text = _normalize_ticket_text(text)
    start = text.find(start_label)
    if start < 0:
        return ""
    section = text[start + len(start_label):]
    end_positions = [section.find(label) for label in end_labels if section.find(label) > 0]
    if end_positions:
        section = section[: min(end_positions)]
    lines = [_clean_block_line(line) for line in section.splitlines() if _clean_block_line(line)]
    return "\n".join(lines)[:max_chars].strip()


def _extract_site_assessment_section(text: str) -> str:
    text = _normalize_ticket_text(text)
    marker = "二、现场勘察（场景式评估）情况及补充控制措施"
    start = text.find(marker)
    if start < 0:
        return ""
    section = text[start + len(marker):]
    end_candidates = []
    for marker_end in ["控制措施\n变化情况描述", "现场作业人员", "审核意见"]:
        pos = section.find(marker_end)
        if pos > 0:
            end_candidates.append(pos)
    if end_candidates:
        section = section[:min(end_candidates)]
    lines = [_clean_block_line(line) for line in section.splitlines() if _clean_block_line(line)]
    return "\n".join(lines).strip()


def _extract_site_assessment_items(text: str) -> list[dict[str, Any]]:
    section = _extract_site_assessment_section(text)
    if not section:
        return []
    categories = {"作业人员", "施工机械", "工程材料", "施工方法", "作业环境"}
    ignored = {"变化情况", "要素", "现场识别"}
    current_category = ""
    question_lines: list[str] = []
    items: list[dict[str, Any]] = []
    for raw in section.splitlines():
        line = _clean_block_line(raw)
        if not line or line in ignored:
            continue
        if line in categories:
            current_category = line
            question_lines = []
            continue
        answer_match = re.fullmatch(r"([þ☑√¨□]?是)\s*([þ☑√¨□]?否)", line)
        if answer_match:
            question = _join_block_lines(question_lines)
            yes_checked = answer_match.group(1).startswith(("þ", "☑", "√"))
            no_checked = answer_match.group(2).startswith(("þ", "☑", "√"))
            answer = "是" if yes_checked else "否" if no_checked else "未勾选"
            if question:
                items.append({
                    "category": current_category or "未分类",
                    "question": re.sub(r"^\d+[.、]", "", question),
                    "answer": answer,
                    "checked": True if yes_checked or no_checked else False,
                })
            question_lines = []
            continue
        if re.match(r"^\d+[.、]", line) or question_lines:
            question_lines.append(line)
    return items


def _extract_supplemental_controls(text: str) -> dict[str, str]:
    text = _normalize_ticket_text(text)
    start = text.find("控制措施\n变化情况描述")
    if start < 0:
        return {"change_description": "", "supplemental_measure": ""}
    section = text[start:]
    end_positions = [section.find(label) for label in ["现场作业人员", "审核意见", "签发意见"] if section.find(label) > 0]
    if end_positions:
        section = section[:min(end_positions)]
    lines = [_clean_block_line(line) for line in section.splitlines() if _clean_block_line(line)]
    values = [line for line in lines if line not in {"控制措施", "变化情况描述"}]
    return {
        "change_description": values[0] if values else "",
        "supplemental_measure": values[1] if len(values) > 1 else "",
    }


def _extract_personnel_and_approval(text: str) -> dict[str, Any]:
    text = _normalize_ticket_text(text)
    def after(label: str, stop_labels: list[str], max_lines: int = 4) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if re.sub(r"\s+", "", line) == label:
                vals = []
                for candidate in lines[index + 1:index + 1 + max_lines]:
                    if _is_stop_line(candidate, stop_labels):
                        break
                    vals.append(candidate)
                return _join_block_lines(vals)
        return ""
    return {
        "site_work_leader": after("班长（现场作业负责人）", ["安全监护人", "分组负责人", "特种作业人员", "一般施工人员"], 3),
        "safety_guardian": after("安全监护人", ["分组负责人", "特种作业人员", "一般施工人员", "审核意见"], 3),
        "group_leader": after("分组负责人", ["特种作业人员", "一般施工人员", "审核意见"], 3),
        "special_workers": after("特种作业人员", ["一般施工人员", "审核意见", "签发意见"], 8),
        "general_workers": after("一般施工人员", ["审核意见", "签发意见", "开票人"], 8),
        "audit_opinion": after("审核意见", ["签发意见", "开票人", "审核人"], 2),
        "sign_opinion": after("签发意见", ["开票人", "开票日期", "审核人"], 2),
        "issuer": after("开票人", ["开票日期", "审核人", "审核日期"], 2),
        "issue_date": after("开票日期", ["审核人", "审核日期", "施工项目部签发人"], 3),
        "auditor": after("审核人", ["审核日期", "施工项目部签发人"], 2),
        "audit_date": after("审核日期", ["施工项目部签发人", "签发日期", "备注"], 3),
        "project_signer": after("施工项目部签发人", ["签发日期", "监理项目部会签人", "备注"], 2),
        "project_sign_date": after("签发日期", ["监理项目部会签人", "会签日期", "备注"], 3),
    }


def _extract_checked_items(text: str, section_label: str, stop_labels: list[str] | None = None) -> list[str]:
    text = _normalize_ticket_text(text)
    start = text.find(section_label)
    if start < 0:
        return []
    section = text[start + len(section_label):]
    end_positions = [section.find(label) for label in (stop_labels or FIELD_STOP_LABELS) if section.find(label) > 0]
    if end_positions:
        section = section[: min(end_positions)]
    items: list[str] = []
    for raw in section.splitlines():
        line = _clean_value(raw.replace("þ", "").replace("☑", ""))
        if not line or len(line) > 80:
            continue
        if "其他" in raw or raw.strip().startswith(("þ", "☑", "√")):
            items.append(line)
    return items[:12]


def _split_list_field(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[、,，；;。]|\s{2,}", value)
    return [_clean_value(part) for part in parts if 1 < len(_clean_value(part)) <= 80][:16]


def _parse_dt(value: str) -> datetime | None:
    value = _normalize_dt(value)
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _infer_plan_status_from_time(time_range: dict[str, str], fallback: str, execution_status: str, text: str) -> str:
    normalized = _normalize_plan_status(fallback, execution_status, text) if fallback else ""
    start = _parse_dt(time_range.get("start", ""))
    end = _parse_dt(time_range.get("end", ""))
    if start and end:
        now = datetime.now()
        if now < start:
            return "待开工"
        if start <= now <= end:
            return "开工中"
        return "已完工"
    return normalized or "待开工"


def _extract_district(text: str, location: str = "") -> str:
    combined = f"{location} {_normalize_ticket_text(text)}"
    match = re.search(r"(越秀区|海珠区|荔湾区|天河区|白云区|黄埔区|番禺区|花都区|南沙区|从化区|增城区)", combined)
    return match.group(1) if match else "广州"



RISK_NAME_KEYWORDS = (
    "无证", "错误", "不足", "措施", "堆物", "超载", "驾驶", "坠落", "触电", "伤害", "坍塌", "火灾", "失稳", "倒塌",
    "打击", "倾覆", "滑落", "违章", "防护", "光线", "距离", "管线", "放坡", "围蔽", "边坡", "临边", "机械", "吊装",
)
CONTROL_START_WORDS = (
    "必须", "应", "设置", "保持", "将", "设", "汽车", "挖掘机", "施工", "按照", "不得", "禁止", "确保", "材料", "基坑",
    "作业", "进入", "离", "防止", "采用", "安排", "检查", "清理", "确认", "做好", "配置", "使用", "佩戴",
)


def _is_risk_name_line(line: str, next_line: str = "") -> bool:
    compact = re.sub(r"\s+", "", line)
    if not compact or compact in {"一", "二", "施工风险控制措施", "风险名称", "主要控制措施", "序号", "补充控制措施"}:
        return False
    if re.fullmatch(r"[0-9一二三四五六七八九十、.]+", compact):
        return False
    if any(mark in compact for mark in "，。；,;：:"):
        return False
    if compact.startswith(CONTROL_START_WORDS) or ("必须" in compact and len(compact) > 8):
        return False
    if compact.startswith("管线保护区"):
        return True
    if len(compact) <= 18 and any(word in compact for word in RISK_NAME_KEYWORDS):
        return True
    if compact.endswith("土石") and next_line.startswith("方开挖"):
        return True
    return False


def _join_control_lines(lines: list[str]) -> str:
    text = "".join(line.strip() for line in lines if line.strip())
    text = re.sub(r"\s+", "", text)
    text = text.replace("，，", "，").replace("。。", "。")
    text = text.replace("驾驶证基坑", "驾驶证，基坑").replace("警示灯防止", "警示灯，防止").replace("警示标识挖掘", "警示标识，挖掘")
    if text and text[-1] not in "。；;":
        text += "。"
    return text


def _extract_risk_measures(text: str) -> list[dict[str, str]]:
    text = _normalize_ticket_text(text)
    start = text.find("施工风险控制措施")
    if start < 0:
        start = text.find("风险名称")
    if start < 0:
        return []
    section = text[start:]
    for stop in ["现场勘察", "站班会", "作业人员", "现场照片"]:
        pos = section.find(stop, 20)
        if pos > 0:
            section = section[:pos]
            break
    raw_lines = [_clean_value(line) for line in section.splitlines() if _clean_value(line)]
    blocked = {"一", "二", "施工风险控制措施", "风险名称", "主要控制措施", "序号", "补充控制措施"}
    lines = [line for line in raw_lines if line not in blocked and not re.fullmatch(r"[0-9一二三四五六七八九十、.]+", line)]
    measures: list[dict[str, str]] = []
    current_risk = ""
    current_control: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        inline_control = ""
        if line.endswith("土石") and next_line.startswith("方开挖"):
            line = f"{line}{next_line}"
            index += 1
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            marker = "作业"
            if marker in line:
                pos = line.find(marker) + len(marker)
                inline_control = line[pos:]
                line = line[:pos]
        if _is_risk_name_line(line, next_line):
            if current_risk and current_control:
                measures.append({"risk_name": current_risk, "control_measure": _join_control_lines(current_control)})
            current_risk = line
            current_control = [inline_control] if inline_control else []
        elif current_risk:
            current_control.append(line)
        index += 1
    if current_risk and current_control:
        measures.append({"risk_name": current_risk, "control_measure": _join_control_lines(current_control)})
    deduped: list[dict[str, str]] = []
    seen = set()
    for item in measures:
        key = item["risk_name"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


def _bool_field(value: str) -> bool | None:
    if not value:
        return None
    if any(word in value for word in ["是", "需要", "有", "涉及"]):
        return True
    if any(word in value for word in ["否", "不需要", "无", "未涉及"]):
        return False
    return None


def input_adapter(state: ParseState) -> ParseState:
    raw_text = state.get("raw_text", "").strip()
    if not raw_text:
        sample = SAMPLE_TICKETS[0]
        raw_text = sample["raw_text"]
        state["source_type"] = sample["source_type"]
    state["raw_text"] = raw_text
    return state


def field_extract(state: ParseState) -> ParseState:
    text = _normalize_ticket_text(state["raw_text"])
    ticket_no = _field(text, ["编号", "计划编号", "作业票编号", "工作票编号"])
    plan_id = ticket_no
    if not plan_id:
        plan_id = "20260521" + hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:8]
        plan_id = str(int(plan_id, 16))[-16:].zfill(16)

    plan_start = _field(text, ["计划开始时间"])
    plan_end = _field(text, ["计划结束时间"])
    time_range = {"start": _normalize_dt(plan_start), "end": _normalize_dt(plan_end)} if plan_start or plan_end else _extract_time_range(text)
    work_content = _extract_work_content(text) or _field(text, ["巡查问题"])
    work_intel = _extract_work_content_intelligence(work_content)
    work_location = _field(text, ["工作地点", "作业地点", "施工地点"]) or ("L13塔附近挡土墙" if "L13" in text else "")
    project_name = _extract_project_name(text) or "待补充"
    initial_risk = _field(text, ["初勘风险等级"])
    recheck_risk = _field(text, ["复测后风险等级"])
    risk_level = recheck_risk or initial_risk or _field(text, ["风险等级", "风险级别"]) or "待确认"
    plan_status_raw = _field(text, ["计划状态"])
    execution_status_raw = _field(text, ["执行状态"])
    normalized_plan_status = _infer_plan_status_from_time(time_range, plan_status_raw, execution_status_raw, text)
    normalized_execution_status = _normalize_execution_status(execution_status_raw, normalized_plan_status)
    power_outage = _bool_field(_field(text, ["作业是否需要停电配合"]))
    running_area = _bool_field(_field(text, ["是否在运行区域或邻电作业"]))
    hazards = _split_list_field(_field(text, ["主要危害"]))
    tools = _split_list_field(_field(text, ["施工必备工器具"]))
    risk_control_section = _extract_section(text, "一、施工风险控制措施", ["二、现场勘察", "现场勘察", "现场作业人员"], max_chars=12000)
    site_assessment_items = _extract_site_assessment_items(text)
    supplemental_controls = _extract_supplemental_controls(text)
    personnel_approval = _extract_personnel_and_approval(text)
    medium_high_risk_items = _extract_checked_items(text, "涉及中高风险作业", ["工作地点", "作业地点", "施工地点"])
    leader = _field(text, ["工作负责人", "作业负责人"])
    if len(leader) > 30 or "施工人员" in leader or "审核意见" in leader:
        leader = ""
    person_match = re.search(r"(\d+)名施工人员", text)
    ticket_fact = {
        "plan_id": plan_id,
        "ticket_no": ticket_no or plan_id,
        "ticket_title": _extract_title(text),
        "project_name": project_name,
        "city": "广州",
        "district": _extract_district(text, work_location),
        "contractor": _field(text, ["施工单位"]) or "待补充",
        "plan_time_range": time_range,
        "plan_start": time_range.get("start", ""),
        "plan_end": time_range.get("end", ""),
        "risk_level": risk_level,
        "initial_risk_level": initial_risk,
        "recheck_risk_level": recheck_risk,
        "plan_status": normalized_plan_status,
        "execution_status": normalized_execution_status,
        "work_leader": leader or ("无" if "无工作负责人" in text else ""),
        "video_control_enabled": bool(re.search(r"视频管控[：:]\s*是|纳入视频管控[：:]\s*是|监控", text)),
        "work_location": work_location,
        "work_content_raw": work_content,
        "work_content_summary": work_intel.get("work_content_summary", ""),
        "work_areas": work_intel.get("work_areas", []),
        "work_actions": work_intel.get("work_actions", []),
        "equipment_targets": work_intel.get("equipment_targets", []),
        "special_operations": work_intel.get("special_operations", []),
        "construction_plan_name": _extract_construction_plan(text),
        "requires_power_outage": power_outage,
        "in_running_area_or_near_electric": running_area,
        "main_hazards": hazards,
        "required_tools": tools,
        "medium_high_risk_items": medium_high_risk_items,
        "risk_control_section": risk_control_section,
        "risk_control_measures": _extract_risk_measures(text),
        "site_assessment_items": site_assessment_items,
        "supplemental_controls": supplemental_controls,
        "personnel_approval": personnel_approval,
        "work_scope": _extract_work_scope(text),
        "person_count": int(person_match.group(1)) if person_match else None,
        "source_type": state.get("source_type", "text"),
    }
    state["ticket_fact"] = ticket_fact
    return state


def content_split(state: ParseState) -> ParseState:
    state["work_content_items"] = _split_work_items(state["raw_text"])
    return state


def normalize_types(state: ParseState) -> ParseState:
    normalized = _normalize_work_types(state.get("work_content_items", []))
    state["normalized_work_types"] = normalized
    state["ticket_fact"]["normalized_work_types"] = normalized
    state["ticket_fact"]["scene_tags"] = _infer_scene_tags(state["raw_text"], normalized)
    return state


def validate_fields(state: ParseState) -> ParseState:
    fact = state["ticket_fact"]
    required = ["project_name", "work_location", "work_content_raw", "plan_status"]
    missing = [field for field in required if not fact.get(field) or fact.get(field) == "待补充"]
    warnings = []
    if "无相关作业计划" in state.get("raw_text", ""):
        warnings.append("输入内容包含现场巡查线索但缺少计划侧作业票，需补充作业票后再进行计划-现场一致性判定。")
    if not fact.get("work_leader") or fact.get("work_leader") == "无":
        warnings.append("作业票未识别到工作负责人字段，后续应结合原票或业务系统补齐责任人信息。")
    if not fact.get("video_control_enabled"):
        warnings.append("未纳入视频管控或字段缺失，建议优先匹配固定监控并准备无人机补拍。")
    confidence = max(0.55, 0.96 - 0.12 * len(missing) - 0.05 * len(warnings))
    state["validation_result"] = {
        "missing_fields": missing,
        "warnings": warnings,
        "requires_human_review": False,
        "confidence": round(confidence, 2),
    }
    return state


def build_media_task(state: ParseState) -> ParseState:
    fact = state["ticket_fact"]
    mapping = _match_camera_mapping(fact)
    media_type = ["image", "video"]
    cameras = mapping["cameras"] if mapping else []
    state["media_query_task"] = {
        "task_type": "MEDIA_RETRIEVAL",
        "tool_name": "get_site_media",
        "trigger_mode": "manual_or_scheduled",
        "trigger_interval_minutes": 30,
        "arguments": {
            "plan_id": fact.get("plan_id"),
            "project_name": fact.get("project_name"),
            "work_location": fact.get("work_location"),
            "work_scope_keywords": list(dict.fromkeys([*fact.get("work_scope", []), fact.get("district", ""), *fact.get("main_hazards", [])]))[:20],
            "query_window": {"mode": "latest", "duration_minutes": 30},
            "media_type": media_type,
            "image_sample_interval_seconds": 10,
            "camera_selection_strategy": "project_tower_section_nearest",
            "candidate_cameras": cameras,
            "uav_route": mapping.get("uav_route") if mapping else None,
            "inspection_focus": ["计划时间窗口", "作业地点", "现场人员与装备", "作业类型", "安全措施落实"],
            "return_fields": ["media_id", "camera_id", "camera_name", "capture_time", "file_path", "thumbnail_path"],
        },
        "mapping_confidence": 0.84 if mapping else 0.31,
    }
    state["media_manifest"] = _media_manifest(mapping, media_type)
    return state


def _build_graph():
    if StateGraph is None:
        return None
    workflow = StateGraph(ParseState)
    workflow.add_node("input_adapter", input_adapter)
    workflow.add_node("field_extract", field_extract)
    workflow.add_node("content_split", content_split)
    workflow.add_node("normalize_types", normalize_types)
    workflow.add_node("validate_fields", validate_fields)
    workflow.add_node("build_media_task", build_media_task)
    workflow.set_entry_point("input_adapter")
    workflow.add_edge("input_adapter", "field_extract")
    workflow.add_edge("field_extract", "content_split")
    workflow.add_edge("content_split", "normalize_types")
    workflow.add_edge("normalize_types", "validate_fields")
    workflow.add_edge("validate_fields", "build_media_task")
    workflow.add_edge("build_media_task", END)
    return workflow.compile()


GRAPH = _build_graph()


def parse_ticket(raw_text: str, source_type: str = "text") -> dict[str, Any]:
    initial: ParseState = {"raw_text": raw_text, "source_type": source_type}
    if GRAPH is not None:
        result = GRAPH.invoke(initial)
    else:  # pragma: no cover
        result = initial
        for node in [input_adapter, field_extract, content_split, normalize_types, validate_fields, build_media_task]:
            result = node(result)
    return {
        "ticket_fact": result["ticket_fact"],
        "work_content_items": result["work_content_items"],
        "normalized_work_types": result["normalized_work_types"],
        "validation_result": result["validation_result"],
        "media_query_task": result["media_query_task"],
        "media_manifest": result["media_manifest"],
        "agent_trace": [
            {"node": "input_adapter", "name": "输入适配", "status": "done"},
            {"node": "field_extract", "name": "字段抽取", "status": "done"},
            {"node": "content_split", "name": "作业内容拆分", "status": "done"},
            {"node": "normalize_types", "name": "作业类型归一化", "status": "done"},
            {"node": "validate_fields", "name": "字段校验", "status": "done"},
            {"node": "build_media_task", "name": "媒体调取任务生成", "status": "done"},
        ],
    }
