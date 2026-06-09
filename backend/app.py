
from __future__ import annotations

import json
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .agent import parse_ticket
from .db import (
    dashboard_data,
    ensure_conversation,
    get_ticket,
    import_parse_record_as_ticket,
    init_db,
    list_conversation_messages,
    list_conversations,
    list_inspections,
    list_parse_records,
    list_tickets,
    save_chat_message,
    save_inspection,
    save_parse_record,
)
from .sample_data import SAMPLE_TICKETS
from .model_api import call_chat, call_chat_stream, public_model_status
from .ocr import extract_text_from_image
from .pdf_ticket import extract_text_from_pdf


app = FastAPI(title="无计划作业智能检查平台 API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_DIR = Path(__file__).resolve().parent / "media" / "site_images"
PILOT_IMAGE_DIR = Path(__file__).resolve().parent / "media" / "pilot_images"
PILOT_FRAME_DIR = Path(__file__).resolve().parent / "media" / "pilot_frames"
DOCS_DIR = Path(__file__).resolve().parent / "docs"


class InspectionRequest(BaseModel):
    ticket_id: str | None = None
    ticket_fact: dict[str, Any] | None = None
    media_query_task: dict[str, Any] | None = None
    operator: str = "系统自动检查"
    mode: str = "manual"


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None
    conversation_id: str | None = None


class ImportTicketRequest(BaseModel):
    record: dict[str, Any]


class FullInspectionRequest(BaseModel):
    ticket_id: str | None = None
    record: dict[str, Any] | None = None
    operator: str = "系统自动检查"
    mode: str = "full_closed_loop"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "unplanned-work-inspection", "time": datetime.now().isoformat()}


@app.get("/api/assets/logo/{name}")
def logo(name: str) -> FileResponse:
    allowed = {"nfdw": "nfdw_logo.png"}
    if name not in allowed:
        name = "nfdw"
    path = Path(__file__).resolve().parent.parent / "fig" / allowed[name]
    return FileResponse(path)


@app.get("/api/media/site/{filename}")
def site_media(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = MEDIA_DIR / safe_name
    if not path.exists():
        files = _site_media_files()
        path = files[0] if files else MEDIA_DIR / "missing.jpg"
    return FileResponse(path)


@app.get("/api/media/pilot/{filename}")
def pilot_media(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = PILOT_IMAGE_DIR / safe_name
    if not path.exists():
        manifest = _pilot_image_manifest()
        if manifest:
            path = PILOT_IMAGE_DIR / manifest[0]["filename"]
    return FileResponse(path)


@app.get("/api/media/pilot-frame/{filename}")
def pilot_frame_media(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = PILOT_FRAME_DIR / safe_name
    if not path.exists():
        path = PILOT_IMAGE_DIR / "pilot_001.jpg"
    return FileResponse(path)


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return dashboard_data()


@app.get("/api/work-tickets")
def work_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = "",
    keyword: str | None = "",
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    return list_tickets(limit=page_size, offset=offset, status=status or None, keyword=keyword or None)


@app.get("/api/work-tickets/samples")
def samples() -> dict[str, Any]:
    tickets = list_tickets(limit=120)["items"]
    return {
        "samples": [
            {
                "id": item["id"],
                "name": f"{item['plan_id']}｜{item['district']}｜{item['work_location']}",
                "source_type": "database",
                "raw_text": item["raw_text"],
                "ticket": item,
            }
            for item in tickets
        ]
    }


@app.get("/api/work-tickets/history")
def parse_history() -> dict[str, Any]:
    return {"items": list_parse_records(20)}


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"




def _load_violation_rulebook() -> dict[str, Any]:
    path = DOCS_DIR / "unplanned_violation_rules.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": "fallback",
            "name": "内置基础规则",
            "manual_path": "backend/docs/unplanned_violation_detection_guidance.md",
            "source_stats": {},
            "general_rules": [
                {"id": "G02", "name": "状态不符", "severity": "高", "condition": "非开工中作业票出现现场施工"},
                {"id": "G05", "name": "作业动作不符", "severity": "高", "condition": "现场动作不属于票面允许内容"},
                {"id": "G10", "name": "安全措施缺失", "severity": "中", "condition": "风险控制措施缺少视觉证据"},
            ],
            "work_type_rules": [],
        }


def _rule_index(rulebook: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule.get("id", ""): rule for rule in rulebook.get("general_rules", []) if rule.get("id")}




def _extract_json_object(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _llm_ticket_analysis(ticket_fact: dict[str, Any], validation_result: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    status = public_model_status()
    if not status.get("available"):
        return {"model_provider": status.get("provider") or "未配置", "model_name": status.get("model") or "", "llm_error": "模型 API 未配置，已使用规则智能体兜底。"}
    if status.get("provider") != "Local":
        return {"model_provider": status.get("provider"), "model_name": status.get("model") or "", "llm_error": "当前模型 API 为外部服务，真实作业票内容未外发；已使用本地规则智能体兜底。"}
    prompt_payload = {
        "ticket_fact": ticket_fact,
        "validation_result": validation_result,
        "rule_based_base": {
            "field_quality": base.get("field_quality"),
            "work_content_understanding": base.get("work_content_understanding"),
            "inspection_rules": base.get("inspection_rules"),
        },
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是南方电网基建现场无计划作业检查平台的作业票入库分析智能体。"
                "只能根据作业票票面信息做计划侧理解，不允许声称已经看到现场。"
                "输出严格 JSON，不要 Markdown。JSON 字段必须包含："
                "agent_report、key_findings、work_content_understanding、vision_checklist、"
                "matching_rules、violation_detection_rules、media_binding_requirements、risk_judgement、dispatch_suggestion。"
                "vision_checklist 要写成后续视觉模型需要识别的对象、人员、机械、区域、动作和安全措施。"
            ),
        },
        {
            "role": "user",
            "content": "请基于以下作业票解析结果生成更具体的入库分析 JSON：\n" + json.dumps(prompt_payload, ensure_ascii=False),
        },
    ]
    result = call_chat(messages, temperature=0.15, timeout=90)
    if not result.get("ok"):
        return {
            "model_provider": public_model_status().get("provider") or "未配置",
            "model_name": public_model_status().get("model") or "",
            "llm_error": result.get("error", "模型 API 调用失败"),
        }
    parsed = _extract_json_object(result.get("content", ""))
    if not parsed:
        return {
            "model_provider": result.get("provider") or public_model_status().get("provider"),
            "model_name": result.get("model") or public_model_status().get("model"),
            "llm_error": "模型返回内容不是可解析 JSON",
            "llm_raw_excerpt": (result.get("content") or "")[:500],
        }
    parsed["model_provider"] = result.get("provider") or public_model_status().get("provider")
    parsed["model_name"] = result.get("model") or public_model_status().get("model")
    return parsed


def build_agent_analysis(ticket_fact: dict[str, Any], validation_result: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
    risk = ticket_fact.get("risk_level") or "待确认"
    status = ticket_fact.get("plan_status") or "待确认"
    hazards = ticket_fact.get("main_hazards") or []
    measures = ticket_fact.get("risk_control_measures") or []
    missing = validation_result.get("missing_fields", []) if validation_result else []
    work_areas = ticket_fact.get("work_areas") or []
    work_actions = ticket_fact.get("work_actions") or []
    equipment_targets = ticket_fact.get("equipment_targets") or []
    special_operations = ticket_fact.get("special_operations") or []
    site_assessment_items = ticket_fact.get("site_assessment_items") or []
    supplemental_controls = ticket_fact.get("supplemental_controls") or {}
    personnel_approval = ticket_fact.get("personnel_approval") or {}
    focus = status == "开工中" or risk in {"高", "中高", "较高"} or bool(special_operations)
    field_quality = {
        "completeness": "完整" if not missing else "需补充",
        "missing_fields": missing,
        "recognized_sections": [
            name for name, value in [
                ("基础信息", ticket_fact.get("ticket_no") or ticket_fact.get("plan_id")),
                ("计划时间", (ticket_fact.get("plan_time_range") or {}).get("start")),
                ("作业地点", ticket_fact.get("work_location")),
                ("作业内容", ticket_fact.get("work_content_raw")),
                ("作业区域", work_areas),
                ("作业动作", work_actions),
                ("风险等级", risk if risk != "待确认" else ""),
                ("风险控制措施", ticket_fact.get("risk_control_section") or measures),
                ("现场勘察", site_assessment_items),
                ("现场人员", personnel_approval),
            ] if value
        ],
    }
    findings = [
        f"作业票编号为{ticket_fact.get('ticket_no') or ticket_fact.get('plan_id', '待补充')}，工程为{ticket_fact.get('project_name', '待补充')}。",
        f"票面计划状态为{status}，计划作业地点为{ticket_fact.get('work_location') or '待补充'}，计划时间为{(ticket_fact.get('plan_time_range') or {}).get('start') or '待补充'}至{(ticket_fact.get('plan_time_range') or {}).get('end') or '待补充'}。",
    ]
    if ticket_fact.get("work_content_summary"):
        findings.append(f"作业内容理解：{ticket_fact.get('work_content_summary')}。")
    else:
        findings.append("作业内容已从票面抽取，后续检查应围绕票面列明的作业区域、作业动作和设备对象建立比对项。")
    if hazards:
        findings.append(f"票面主要危害包含{'、'.join(hazards[:6])}，检查任务应据此关注安全措施配置与作业风险控制。")
    if site_assessment_items:
        yes_count = sum(1 for item in site_assessment_items if item.get("answer") == "是")
        no_count = sum(1 for item in site_assessment_items if item.get("answer") == "否")
        findings.append(f"现场勘察（场景式评估）共识别{len(site_assessment_items)}项，其中“是”{yes_count}项、“否”{no_count}项；这些是票面勘察记录，应作为后续检查的约束条件而不是现场识别结论。")
    if supplemental_controls.get("change_description") or supplemental_controls.get("supplemental_measure"):
        findings.append(f"补充控制措施记录为：变化情况{supplemental_controls.get('change_description') or '未填写'}，补充措施{supplemental_controls.get('supplemental_measure') or '未填写'}。")
    if ticket_fact.get("requires_power_outage") is True:
        findings.append("票面显示需要停电配合，应把停电许可、隔离范围和作业时间窗口纳入后续一致性检查。")
    if ticket_fact.get("in_running_area_or_near_electric") is True:
        findings.append("票面显示涉及运行区域或邻电作业，应作为媒体调取和视觉比对的重点作业票。")
    control_focus = [item.get("risk_name") or item.get("control_measure") for item in measures[:6]] or hazards[:6]
    vision_checklist = [
        {"category": "人员", "items": ["现场人数", "作业人员是否进入票面作业区域", "个体防护装备：安全帽、反光衣、安全带、绝缘手套"]},
        {"category": "作业区域", "items": [*work_areas[:6], ticket_fact.get("work_location") or "票面作业地点"]},
        {"category": "作业动作", "items": work_actions[:10] or ["封堵", "拆除", "新建", "安装", "迁移", "加固", "动火"]},
        {"category": "设备材料", "items": equipment_targets[:10] or ["主变基础", "GIS室", "电缆沟", "接地网", "端子箱", "风冷箱"]},
        {"category": "安全措施", "items": control_focus[:8] or ["围蔽警示", "临边防护", "灭火器", "隔离措施", "监护到位"]},
    ]
    inspection_focus = [
        "现场作业时间必须落在票面计划时间窗口内",
        "现场作业区域必须属于票面列明的地点、房间、设备间隔或施工区域",
        "现场作业动作必须属于票面列明的封堵、拆除、新建、迁移、加固、安装、回填、动火等内容",
        "现场出现的设备对象、材料和工器具必须与票面列明内容相符",
        "票面主要危害对应的安全措施必须具备可见证据",
    ]
    base = {
        "agent_name": "作业票入库分析智能体",
        "risk_judgement": "重点跟踪" if focus else "常规检查",
        "agent_report": "已完成票面结构化解析，并生成后续现场媒体调取与视觉一致性检查要素。该报告只代表计划侧理解，不代表现场实际情况。",
        "key_findings": findings,
        "field_quality": field_quality,
        "work_content_understanding": {
            "work_areas": work_areas,
            "work_actions": work_actions,
            "equipment_targets": equipment_targets,
            "special_operations": special_operations,
            "summary": ticket_fact.get("work_content_summary") or "待模型进一步归纳",
        },
        "site_assessment_summary": {
            "total_items": len(site_assessment_items),
            "yes_items": sum(1 for item in site_assessment_items if item.get("answer") == "是"),
            "no_items": sum(1 for item in site_assessment_items if item.get("answer") == "否"),
            "supplemental_controls": supplemental_controls,
            "site_work_leader": personnel_approval.get("site_work_leader"),
            "safety_guardian": personnel_approval.get("safety_guardian"),
        },
        "control_focus": control_focus,
        "vision_checklist": vision_checklist,
        "media_binding_requirements": {
            "query_window_minutes": 30,
            "location_keywords": [item for item in [ticket_fact.get("district"), ticket_fact.get("work_location"), *work_areas[:8], *ticket_fact.get("work_scope", [])] if item],
            "preferred_media": ["固定监控图片", "固定监控视频", "无人机补拍"],
        },
        "inspection_rules": inspection_focus,
        "matching_rules": inspection_focus,
        "violation_detection_rules": [
            "计划状态不是开工中时，系统不触发现场画面比对",
            "作业时间、地点、人员数量、作业动作、设备对象任一关键维度不一致，标记为疑似无计划作业片段",
            "现场出现票面未授权的动火、吊装、开挖、拆除、带电邻近作业，标记为高风险异常",
            "安全措施缺失或个体防护装备明显不足，作为安全违规项输出",
        ],
        "dispatch_suggestion": f"若该票处于开工中，优先按{ticket_fact.get('work_location', '作业地点')}及票面作业区域调取近30分钟现场画面；固定监控不可覆盖时再派发无人机补拍。",
        "review_required": False,
        "model_provider": "rules",
        "model_name": "rule-fallback",
        "llm_used": False,
    }
    if use_llm:
        llm = _llm_ticket_analysis(ticket_fact, validation_result or {}, base)
        merged = deepcopy(base)
        for key, value in llm.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        merged["llm_used"] = not bool(llm.get("llm_error"))
        if not merged.get("key_findings"):
            merged["key_findings"] = findings
        return merged
    return base

def _extract_upload_text(content: bytes, filename: str, user_text: str = "") -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        pdf_result = extract_text_from_pdf(content, filename=filename)
        file_text = pdf_result.get("text", "").strip()
        raw_text = "\n".join(part for part in [user_text.strip(), file_text] if part).strip()
        if not raw_text:
            raw_text = f"PDF文件：{filename}\n未识别到有效文字。"
        return raw_text, "pdf", None, pdf_result, {"type": "pdf", "text": file_text, "pdf_result": pdf_result}
    ocr_result = extract_text_from_image(content, filename=filename)
    ocr_text = ocr_result.get("text", "").strip()
    raw_text = "\n".join(part for part in [user_text.strip(), ocr_text] if part).strip()
    if not raw_text:
        raw_text = f"图片文件：{filename}\nOCR未识别到有效文字。"
    return raw_text, "image_ocr", ocr_result, None, {"type": "ocr", "text": ocr_text, "ocr_result": ocr_result}


def _normalize_name_for_compare(value: str) -> str:
    value = Path(value or "").stem
    return re.sub(r"[\s（）()0-9一二三四五六七八九十、_.-]+", "", value)


def _attach_source_consistency(record_payload: dict[str, Any], pdf_result: dict[str, Any] | None, ocr_result: dict[str, Any] | None) -> None:
    fact = record_payload.get("ticket_fact") or {}
    source_name = (pdf_result or ocr_result or {}).get("filename", "")
    ticket_title = fact.get("ticket_title") or ""
    if source_name:
        fact["source_file_name"] = source_name
    if not source_name or not ticket_title:
        return
    normalized_file = _normalize_name_for_compare(source_name)
    normalized_title = _normalize_name_for_compare(ticket_title)
    if normalized_file and normalized_title and normalized_file not in normalized_title and normalized_title not in normalized_file:
        consistency = {
            "matched": False,
            "source_file_name": source_name,
            "ticket_title": ticket_title,
            "message": f"上传文件名为“{source_name}”，但PDF票面标题识别为“{ticket_title}”，请确认是否上传了重命名或同名不同项目的作业票。",
        }
        fact["source_consistency"] = consistency
        validation = record_payload.get("validation_result") or {}
        warnings = validation.setdefault("warnings", [])
        warnings.append(consistency["message"])
    else:
        fact["source_consistency"] = {"matched": True, "source_file_name": source_name, "ticket_title": ticket_title}


def _site_media_files() -> list[Path]:
    if not MEDIA_DIR.exists():
        return []
    files = [path for path in MEDIA_DIR.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    return sorted(files)


def _make_parse_record(raw_text: str, sample_id: str = "", source_type: str = "text", ocr_result: dict[str, Any] | None = None, pdf_result: dict[str, Any] | None = None) -> dict[str, Any]:
    ticket_id = None
    ticket = None
    if sample_id:
        ticket = get_ticket(sample_id)
        if ticket:
            ticket_id = ticket["id"]
            raw_text = ticket["raw_text"]
            source_type = "database"
        else:
            sample = next((item for item in SAMPLE_TICKETS if item["id"] == sample_id), None)
            if sample:
                raw_text = sample["raw_text"]
                source_type = sample["source_type"]

    if ticket and source_type == "database":
        record_payload = {
            "ticket_fact": ticket["ticket_fact"],
            "work_content_items": [part.strip(" 。") for part in ticket["work_content_raw"].replace("、", "，").split("，") if part.strip()],
            "normalized_work_types": ticket["ticket_fact"].get("normalized_work_types", []),
            "validation_result": ticket["validation_result"],
            "media_query_task": ticket["media_query_task"],
            "media_manifest": [],
            "agent_analysis": ticket.get("agent_analysis", {}),
            "agent_trace": [
                {"node": "database_load", "name": "数据库读取", "status": "done"},
                {"node": "field_extract", "name": "字段结构化", "status": "done"},
                {"node": "build_media_task", "name": "媒体任务生成", "status": "done"},
            ],
        }
        if not record_payload.get("agent_analysis"):
            record_payload["agent_analysis"] = build_agent_analysis(record_payload["ticket_fact"], record_payload["validation_result"], use_llm=True)
    else:
        record_payload = parse_ticket(raw_text, source_type=source_type)
        _attach_source_consistency(record_payload, pdf_result, ocr_result)
        record_payload["agent_analysis"] = build_agent_analysis(record_payload["ticket_fact"], record_payload["validation_result"], use_llm=True)

    record = {
        "id": f"parse_{uuid.uuid4().hex[:8]}",
        "ticket_id": ticket_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_type": source_type,
        "summary": record_payload["ticket_fact"].get("project_name") or record_payload["ticket_fact"].get("plan_id"),
        "raw_text": raw_text,
        "ocr_result": ocr_result or {},
        "pdf_result": pdf_result or {},
        **record_payload,
    }
    save_parse_record(record, ticket_id=ticket_id)
    return record




def _pilot_image_manifest() -> list[dict[str, Any]]:
    path = PILOT_IMAGE_DIR / "manifest.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _pilot_ticket_raw_text() -> str:
    today = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    start = today.strftime("%Y-%m-%d %H:%M:%S")
    end = (today + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    return (
        "地基与电气安装综合作业安全施工作业票\n"
        "工程名称：220千伏合景输变电工程在线试点\n"
        "编号：2026060100002201\n"
        "初勘风险等级\n中\n复测后风险等级\n中\n"
        "涉及中高风险作业þ其他：运行站邻近区域土建与电气交叉作业\n"
        "工作地点\n广州市黄埔区合景变电站站区北侧主变基础及GIS室电缆沟区域\n"
        "作业部位及内容\n"
        "1、#3主变基础钢筋绑扎、模板安装、混凝土浇筑准备；"
        "2、GIS室新增电缆沟开挖、支护、预埋件安装；"
        "3、站区接地网敷设、接地扁钢焊接及防腐处理；"
        "4、设备物资进场、工器具材料转运；"
        "5、动火作业及临边安全防护布置。\n"
        f"计划开始时间\n{start}\n计划结束时间\n{end}\n"
        "执行的施工方案名称\n220千伏合景输变电工程主变基础及GIS电缆沟施工方案.pdf\n"
        "作业是否需要停电配合\n否\n是否在运行区域或邻电作业\n是\n"
        "主要危害\n物体打击、触电、机械伤害、坍塌、动火火灾、临边坠落\n"
        "施工必备工器具\n挖掘机、吊车、电焊机、切割机、安全带、临边围栏、灭火器、接地线\n"
        "一、施工风险控制措施\n风险名称\n主要控制措施\n"
        "无证上岗\n特种作业人员必须持证上岗，作业前完成安全交底。\n"
        "临边防护不足\n电缆沟和基坑周边设置硬质围栏、警示标识和夜间警示灯。\n"
        "动火管控不到位\n动火前确认审批、清理周边可燃物并配置灭火器。\n"
        "机械伤害\n机械作业半径设置警戒区，非作业人员不得进入。\n"
        "二、现场勘察（场景式评估）情况及补充控制措施\n"
        "作业人员\n1.作业人员是否配备检验合格、齐全、完好的个人安全防护用品\nþ是¨否\n"
        "施工机械\n1.施工机械设备是否已通过报审\nþ是¨否\n"
        "作业环境\n1.作业点是否邻近带电体、边坡、深坑等危险环境\nþ是¨否\n"
        "控制措施\n变化情况描述\n无\n控制措施\n按方案执行，重点关注临边防护、动火作业和个体防护装备。\n"
        "现场作业人员\n班长（现场作业负责人）\n张志强\n安全监护人\n李安全\n"
        "特种作业人员\n王焊工、赵电工\n一般施工人员\n陈建、刘工、黄工、周工\n审核意见\n同意\n签发意见\n同意\n"
    )


def _make_pilot_parse_record() -> dict[str, Any]:
    raw_text = _pilot_ticket_raw_text()
    payload = parse_ticket(raw_text, source_type="pilot_text")
    payload["agent_analysis"] = build_agent_analysis(payload["ticket_fact"], payload["validation_result"], use_llm=True)
    record = {
        "id": f"parse_{uuid.uuid4().hex[:8]}",
        "ticket_id": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_type": "pilot_text",
        "summary": payload["ticket_fact"].get("project_name") or payload["ticket_fact"].get("plan_id"),
        "raw_text": raw_text,
        "ocr_result": {},
        "pdf_result": {},
        **payload,
    }
    save_parse_record(record)
    return record


def _ensure_pilot_ticket() -> tuple[dict[str, Any], dict[str, Any], bool]:
    existing = get_ticket("2026060100002201")
    if existing:
        analysis = build_agent_analysis(existing["ticket_fact"], existing["validation_result"], use_llm=True)
        parse_record = {
            "ticket_fact": existing["ticket_fact"],
            "validation_result": existing["validation_result"],
            "agent_analysis": analysis,
            "source_type": "database",
            "summary": existing.get("project_name") or existing.get("plan_id"),
        }
        return existing, parse_record, False
    record = _make_pilot_parse_record()
    result = import_parse_record_as_ticket(record)
    ticket = result.get("ticket") or get_ticket("2026060100002201")
    return ticket, record, bool(result.get("created"))




def _ensure_ticket_for_full_inspection(payload: FullInspectionRequest) -> tuple[dict[str, Any], dict[str, Any], bool]:
    if payload.ticket_id:
        ticket = get_ticket(payload.ticket_id)
        if not ticket:
            raise ValueError("未找到指定作业票")
        parse_record = {
            "ticket_id": ticket.get("id"),
            "source_type": "database",
            "summary": ticket.get("project_name") or ticket.get("plan_id"),
            "ticket_fact": ticket.get("ticket_fact", {}),
            "validation_result": ticket.get("validation_result", {}),
            "media_query_task": ticket.get("media_query_task", {}),
            "agent_analysis": ticket.get("agent_analysis", {}),
        }
        return ticket, parse_record, False
    record = payload.record or {}
    if not record:
        raise ValueError("请先提供作业票解析结果或作业票ID")
    if record.get("ticket_id"):
        ticket = get_ticket(record["ticket_id"])
        if ticket:
            return ticket, record, False
    result = import_parse_record_as_ticket(record)
    ticket = result.get("ticket") or get_ticket((record.get("ticket_fact") or {}).get("plan_id"))
    if not ticket:
        raise ValueError("作业票入库失败，无法发起检查")
    return ticket, record, bool(result.get("created"))


def _run_full_inspection(ticket: dict[str, Any], parse_record: dict[str, Any], created: bool, project_name: str | None = None) -> dict[str, Any]:
    frames = _build_pilot_frames(ticket)
    vision = _pilot_visual_understanding(frames, ticket)
    detection = _pilot_violation_detection(ticket, vision)
    inspection = _save_pilot_inspection(ticket, frames, vision, detection)
    return {
        "success": True,
        "project": project_name or ticket.get("project_name") or (ticket.get("ticket_fact") or {}).get("project_name") or "无计划作业智能检查",
        "ticket_created": created,
        "parse_record": parse_record,
        "ticket": ticket,
        "media_manifest": frames,
        "vision_result": vision,
        "violation_result": detection,
        "inspection": inspection,
        "data_sources": [{"title": item.get("title"), "source_page": item.get("source_page"), "filename": item.get("filename")} for item in _pilot_asset_pool()],
    }


def _pilot_expected_profile(ticket: dict[str, Any]) -> dict[str, Any]:
    fact = ticket.get("ticket_fact", {}) if ticket else {}
    work_content = fact.get("work_content_raw") or ticket.get("work_content_raw") or ""
    expected_actions = fact.get("work_actions") or ["基础施工", "接地施工", "电缆沟施工", "设备基础安装", "材料转运"]
    expected_objects = fact.get("equipment_targets") or ["主变基础", "GIS室", "电缆沟", "接地网", "端子箱", "消防管道"]
    expected_areas = fact.get("work_areas") or [ticket.get("work_location") or fact.get("work_location") or "合景站施工区域"]
    return {
        "plan_id": fact.get("plan_id") or ticket.get("plan_id"),
        "project_name": fact.get("project_name") or ticket.get("project_name"),
        "plan_status": fact.get("plan_status") or ticket.get("plan_status"),
        "plan_time_range": fact.get("plan_time_range") or {"start": ticket.get("plan_start"), "end": ticket.get("plan_end")},
        "expected_areas": expected_areas,
        "expected_actions": expected_actions,
        "expected_objects": expected_objects,
        "expected_safety": ["安全帽", "反光衣", "临边防护", "围蔽警示", "动火隔离", "灭火器"],
        "work_content_excerpt": work_content[:600],
    }



def _pilot_asset_pool() -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for item in _pilot_image_manifest():
        copied = dict(item)
        copied["asset_dir"] = str(PILOT_IMAGE_DIR)
        assets.append(copied)
    source_meta: dict[str, dict[str, Any]] = {}
    try:
        for item in json.loads((MEDIA_DIR / "sources.json").read_text(encoding="utf-8")):
            file_name = item.get("file") or item.get("filename")
            if file_name:
                source_meta[file_name] = item
    except Exception:
        source_meta = {}

    def _site_profile(category: str, title: str) -> tuple[list[str], str, list[str], list[str], str, int, str, list[str]]:
        label = f"{category or '施工现场'}"
        title_text = f"{category} {title}"
        if any(word in title_text for word in ["变电站", "substation", "Substation", "电力", "Power", "Electrical"]):
            return [label, "电力设施"], "电力设施或变电站相关施工画面，适合作为合景试点计划侧匹配样本", ["变电设备", "构架", "开关设备"], ["设备区施工", "电力设施作业"], "部分匹配", 0, "无法判断", []
        if any(word in title_text for word in ["沟槽", "trench", "excavat", "Excavat", "开挖"]):
            return [label, "沟槽开挖"], "沟槽或基坑开挖施工画面，可用于比对GIS室电缆沟开挖作业", ["沟槽", "土方", "支护区域"], ["沟槽开挖", "土方作业"], "匹配", 1, "远景无法确认", ["临边防护需结合目标检测确认"]
        if any(word in title_text for word in ["混凝土", "concrete", "Concrete", "Rebar", "rebar", "钢筋", "基础"]):
            return [label, "基础施工"], "钢筋、模板或混凝土基础施工画面，可用于比对主变基础作业", ["钢筋", "模板", "混凝土结构"], ["钢筋绑扎", "模板安装", "混凝土施工"], "匹配", 1, "远景无法确认", ["临边防护和个体防护装备需结合目标检测确认"]
        if any(word in title_text for word in ["worker", "Worker", "hard", "施工人员", "安全帽"]):
            return [label, "人员作业"], "现场人员作业画面，重点用于个体防护装备和作业动作识别", ["作业人员", "安全帽"], ["现场作业"], "需确认", 2, "远景无法确认", ["个体防护装备需结合目标检测确认"]
        if any(word in title_text for word in ["excavator", "Excavator", "机械"]):
            return [label, "机械作业"], "施工机械作业画面，需确认是否属于票面授权机械和区域", ["施工机械", "土方区域"], ["机械作业"], "部分匹配", 1, "远景无法确认", ["机械作业半径和警戒区需确认"]
        return [label, "施工现场"], "公开施工现场样本，需结合摄像头点位和作业票内容进行一致性比对", ["施工区域"], ["现场施工"], "需确认", 0, "无法判断", []

    site_files = sorted(path for path in MEDIA_DIR.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}) if MEDIA_DIR.exists() else []
    for idx, path in enumerate(site_files):
        meta = source_meta.get(path.name, {})
        category = meta.get("category") or "本地公开施工图片"
        title = meta.get("title") or path.stem
        tags, scene, equipment, activities, match, workers, protection, issues = _site_profile(category, title)
        assets.append({
            "id": f"site_{idx + 1:02d}",
            "title": title,
            "filename": path.name,
            "asset_dir": str(MEDIA_DIR),
            "url": f"/api/media/site/{path.name}",
            "source_page": meta.get("source") or meta.get("source_page") or "本地公开施工图片样本库",
            "tags": tags,
            "vision": {
                "scene": scene,
                "workers": workers,
                "ppe": protection,
                "equipment": equipment,
                "activities": activities,
                "issues": issues,
                "planned_match": match,
            },
        })
    return assets


def _ensure_pilot_frame_asset(src: dict[str, Any], idx: int, capture: datetime, camera_name: str, secondary: dict[str, Any] | None = None) -> str:
    PILOT_FRAME_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"hj_snapshot_v2_{idx + 1:02d}.jpg"
    target = PILOT_FRAME_DIR / filename
    source_name = src.get("filename") or "pilot_001.jpg"
    source_dir = Path(src.get("asset_dir") or PILOT_IMAGE_DIR)
    source_path = source_dir / source_name
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

        image = Image.open(source_path).convert("RGB")
        width, height = image.size
        crop_ratio = 0.72 + (idx % 5) * 0.04
        crop_w = max(1, int(width * min(crop_ratio, 0.9)))
        crop_h = max(1, int(height * min(crop_ratio, 0.9)))
        left = int((width - crop_w) * ((idx * 3 % 11) / 10 if width > crop_w else 0))
        top = int((height - crop_h) * ((idx * 5 % 11) / 10 if height > crop_h else 0))
        image = image.crop((left, top, left + crop_w, top + crop_h)).resize((960, 540))
        if idx % 2:
            image = ImageOps.mirror(image)
        image = ImageEnhance.Color(image).enhance(0.88 + (idx % 7) * 0.035)
        image = ImageEnhance.Contrast(image).enhance(0.94 + (idx % 6) * 0.025)

        if secondary:
            secondary_path = Path(secondary.get("asset_dir") or PILOT_IMAGE_DIR) / (secondary.get("filename") or "pilot_001.jpg")
            if secondary_path.exists():
                inset = Image.open(secondary_path).convert("RGB")
                inset = ImageOps.fit(inset, (268, 152), method=Image.Resampling.LANCZOS)
                inset = ImageEnhance.Color(inset).enhance(0.9 + (idx % 4) * 0.05)
                image.paste(inset, (672, 366))

        draw = ImageDraw.Draw(image, "RGBA")
        font = ImageFont.load_default()
        draw.rectangle((0, 0, 960, 54), fill=(7, 19, 35, 178))
        draw.text((18, 16), f"{camera_name}  {capture:%Y-%m-%d %H:%M}", fill=(255, 255, 255, 245), font=font)
        draw.rectangle((18, 486, 420, 526), fill=(7, 19, 35, 160))
        draw.text((30, 500), f"220千伏合景输变电工程 | 第{idx + 1:02d}帧", fill=(226, 246, 255, 245), font=font)
        if idx in {7, 8, 9, 21, 22}:
            draw.rectangle((625, 348, 910, 506), outline=(255, 86, 86, 230), width=4)
            draw.text((635, 360), "疑似异常区域", fill=(255, 235, 235, 245), font=font)
        else:
            draw.rectangle((626, 348, 910, 506), outline=(34, 211, 238, 210), width=3)
            draw.text((636, 360), "计划作业区域", fill=(224, 252, 255, 245), font=font)
        image.save(target, quality=88)
    except Exception:
        return src.get("url", "")
    return f"/api/media/pilot-frame/{filename}"


def _build_pilot_frames(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    assets = _pilot_asset_pool()
    now = datetime.now().replace(second=0, microsecond=0)
    frames = []
    for idx in range(30):
        src = assets[(idx * 7) % len(assets)] if assets else {}
        secondary = assets[(idx * 11 + 5) % len(assets)] if assets else None
        if secondary and secondary.get("filename") == src.get("filename"):
            secondary = assets[(idx * 11 + 6) % len(assets)]
        capture = now - timedelta(minutes=29 - idx)
        camera_id = "HJ-CAM-NORTH-01" if idx < 18 else "HJ-CAM-GIS-02"
        camera_name = "合景站北侧主变基础固定监控" if idx < 18 else "合景站GIS室电缆沟固定监控"
        snapshot_url = _ensure_pilot_frame_asset(src, idx, capture, camera_name, secondary)
        source_assets = [src.get("filename", "")]
        if secondary:
            source_assets.append(secondary.get("filename", ""))
        frames.append({
            "media_id": f"hj_frame_{idx + 1:02d}",
            "display_label": f"第{idx + 1:02d}帧",
            "media_type": "现场图片",
            "camera_id": camera_id,
            "camera_name": camera_name,
            "capture_time": capture.strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": snapshot_url,
            "thumbnail_path": snapshot_url,
            "minute_index": idx + 1,
            "status": "已绑定",
            "work_location": ticket.get("work_location"),
            "source_asset": " + ".join(item for item in source_assets if item),
            "source_page": src.get("source_page", ""),
            "source_title": src.get("title", ""),
            "tags": src.get("tags", []),
            "vision_seed": src.get("vision", {}),
            "dedupe_key": f"{camera_id}-{capture:%Y%m%d%H%M}-{idx + 1:02d}",
        })
    return frames

def _pilot_visual_understanding(frames: list[dict[str, Any]], ticket: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = _pilot_expected_profile(ticket or {})
    frame_results = []
    tag_counts: dict[str, int] = {}
    activity_counts: dict[str, int] = {}
    total_workers = 0
    detector_names = ["人员检测", "安全帽检测", "反光衣检测", "施工机械检测", "作业区域分割", "场景-作业类型分类"]
    for frame in frames:
        seed = frame.get("vision_seed", {})
        minute = int(frame.get("minute_index") or 0)
        activities = list(seed.get("activities", []))
        equipment = list(seed.get("equipment", []))
        issues = list(seed.get("issues", []))
        match = seed.get("planned_match", "待判断")
        if 8 <= minute <= 10:
            match = "不匹配"
            activities = ["墙面抹灰", "室内装修"]
            equipment = ["手工工具", "脚手凳"]
            issues = ["作业类型不在票面范围", "作业区域疑似不属于合景站计划区域", "个体防护装备疑似不完整"]
        elif 22 <= minute <= 23:
            match = "需确认"
            issues = ["临边防护目标置信度偏低", "灭火器目标未检出"]
        elif match == "部分匹配":
            issues = [issue.replace("PPE", "个体防护装备") for issue in issues]
        for tag in frame.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for act in activities:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        workers = int(seed.get("workers") or 0)
        if 8 <= minute <= 10:
            workers = max(workers, 2)
        total_workers += workers
        location_score = 0.92 if match in {"匹配", "部分匹配"} else 0.38 if match == "不匹配" else 0.66
        activity_score = 0.9 if match == "匹配" else 0.72 if match == "部分匹配" else 0.28 if match == "不匹配" else 0.58
        safety_score = 0.86 if not issues else 0.55 if match != "不匹配" else 0.34
        frame_results.append({
            "media_id": frame["media_id"],
            "display_label": frame.get("display_label") or f"第{minute:02d}帧",
            "capture_time": frame["capture_time"],
            "camera_name": frame.get("camera_name"),
            "scene": seed.get("scene", "施工现场画面"),
            "scene_source": "假设多模态视觉模型已完成画面描述、目标检测和作业类型分类",
            "workers": workers,
            "personal_protection": (seed.get("ppe") or "无法判断").replace("PPE", "个体防护装备"),
            "objects": [{"name": item, "confidence": round(0.68 + ((minute + i) % 7) * 0.04, 2)} for i, item in enumerate([*equipment, *activities][:6])],
            "equipment": equipment,
            "activities": activities,
            "planned_match": match,
            "match_scores": {"地点": round(location_score, 2), "作业内容": round(activity_score, 2), "安全措施": round(safety_score, 2)},
            "issues": [issue.replace("PPE", "个体防护装备") for issue in issues],
            "evidence": f"模型在{frame.get('camera_name')}第{minute:02d}分钟快照中识别到：{('、'.join(activities) or '施工现场')}；目标：{('、'.join(equipment) or '待确认')}。",
        })
    return {
        "model_name": "合景试点视觉理解模型（原型二版）",
        "model_assumption": "原型阶段假设视觉/多模态模型已经接入；当前返回的是按公开图片样本和规则生成的可替换结构化推理结果。",
        "inference_pipeline": [
            {"stage": "目标检测", "output": "人员、施工机械、安全帽、反光衣、临边防护、灭火器等目标框和置信度"},
            {"stage": "场景理解", "output": "判断是否为变电站土建、GIS室电缆沟、室内装修等场景"},
            {"stage": "作业动作识别", "output": "识别基础施工、材料转运、机械作业、装修抹灰等动作"},
            {"stage": "计划一致性比对", "output": "与作业票时间、地点、作业内容、安全措施进行逐帧打分"},
        ],
        "detectors": detector_names,
        "expected_profile": expected,
        "frame_count": len(frames),
        "aggregates": {
            "total_worker_observations": total_workers,
            "scene_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True),
            "activities": sorted(activity_counts.items(), key=lambda x: x[1], reverse=True),
            "unmatched_frames": [row.get("display_label") or row["media_id"] for row in frame_results if row.get("planned_match") == "不匹配"],
            "uncertain_frames": [row.get("display_label") or row["media_id"] for row in frame_results if row.get("planned_match") == "需确认"],
        },
        "frames": frame_results,
    }



def _pilot_report_markdown(ticket: dict[str, Any], vision: dict[str, Any], detection: dict[str, Any]) -> str:
    fact = ticket.get("ticket_fact", {}) if ticket else {}
    comparison = detection.get("dimension_comparison") or []
    alerts = detection.get("anomalies") or []
    lines = [
        "## 无计划作业检测报告",
        "",
        "### 一、作业票计划侧事实",
        f"- 计划编号：{fact.get('plan_id') or ticket.get('plan_id')}",
        f"- 工程名称：{fact.get('project_name') or ticket.get('project_name')}",
        f"- 计划状态：{fact.get('plan_status') or ticket.get('plan_status')}",
        f"- 计划时间：{(fact.get('plan_time_range') or {}).get('start') or ticket.get('plan_start')} 至 {(fact.get('plan_time_range') or {}).get('end') or ticket.get('plan_end')}",
        f"- 作业地点：{fact.get('work_location') or ticket.get('work_location')}",
        f"- 允许作业内容：{fact.get('work_content_raw') or ticket.get('work_content_raw')}",
        f"- 允许作业动作：{'、'.join(fact.get('work_actions') or []) or '待识别'}",
        f"- 允许设备对象：{'、'.join(fact.get('equipment_targets') or []) or '待识别'}",
        "",
        "### 二、现场视觉理解摘要",
        f"- 调取媒体：近30分钟图片，共{vision.get('frame_count')}帧",
        f"- 识别活动：{'、'.join(name for name, _ in (vision.get('aggregates') or {}).get('activities', [])[:8]) or '待识别'}",
        f"- 不一致帧：{'、'.join((vision.get('aggregates') or {}).get('unmatched_frames', [])[:8]) or '无'}",
        "",
        "### 三、一致性比对",
        "| 维度 | 票面要求 | 现场识别 | 结论 | 证据 |",
        "|---|---|---|---|---|",
    ]
    for row in comparison:
        lines.append(f"| {row.get('dimension')} | {row.get('plan')} | {row.get('vision')} | {row.get('result')} | {row.get('evidence')} |")
    lines.extend([
        "",
        "### 四、检测结论",
        f"- 风险等级：{detection.get('risk_level')}",
        f"- 结论：{detection.get('conclusion')}",
        f"- 命中规则：{'、'.join(rule.get('id') + rule.get('name', '') for rule in detection.get('matched_rules', [])[:8]) or '未命中高风险规则'}",
        f"- 异常事件：{len(alerts)}项",
    ])
    for item in alerts[:5]:
        lines.append(f"- {item.get('level')}｜{item.get('type')}｜{item.get('frame_range') or '全局'}：{item.get('description')}")
    lines.append("")
    lines.append("建议动作：系统自动保存作业票、现场图片、视觉理解文本、命中规则和异常事件，进入异常清单；对证据不足项继续调取相邻机位或派发无人机补拍。")
    return "\n".join(lines)


def _pilot_violation_detection(ticket: dict[str, Any], vision: dict[str, Any]) -> dict[str, Any]:
    fact = ticket.get("ticket_fact", {}) if ticket else {}
    rulebook = _load_violation_rulebook()
    rules_by_id = _rule_index(rulebook)
    frame_issues = vision.get("frames", [])
    anomaly_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    matched_rule_ids: set[str] = set()

    def rule_name(rule_id: str) -> str:
        rule = rules_by_id.get(rule_id, {})
        return f"{rule_id} {rule.get('name', '')}".strip()

    def add_anomaly(rule_id: str, level: str, type_name: str, frame: dict[str, Any] | None, description: str, evidence: str, suggestion: str, score: dict[str, Any] | None = None) -> None:
        matched_rule_ids.add(rule_id)
        key = (rule_id, level, type_name)
        label = frame.get("display_label") if frame else "全局"
        media_id = frame.get("media_id") if frame else "-"
        current = anomaly_map.get(key)
        if not current:
            current = {
                "rule_id": rule_id,
                "rule_name": rule_name(rule_id),
                "level": level,
                "type": type_name,
                "media_id": media_id,
                "display_label": label,
                "frame_labels": [] if label == "全局" else [label],
                "frame_range": label,
                "description": description,
                "evidence": evidence,
                "evidence_samples": [evidence] if evidence else [],
                "score": score or {},
                "suggestion": suggestion,
                "count": 1,
            }
            anomaly_map[key] = current
            return
        current["count"] += 1
        if label != "全局" and label not in current["frame_labels"]:
            current["frame_labels"].append(label)
        if evidence and evidence not in current["evidence_samples"] and len(current["evidence_samples"]) < 4:
            current["evidence_samples"].append(evidence)
        labels = current.get("frame_labels") or []
        current["frame_range"] = "、".join(labels[:5]) + (f"等{len(labels)}帧" if len(labels) > 5 else "") if labels else "全局"
        current["evidence"] = "；".join(current["evidence_samples"][:3])

    for frame in frame_issues:
        match = frame.get("planned_match")
        scores = frame.get("match_scores") or {}
        issues = frame.get("issues", [])
        actions = "、".join(frame.get("activities") or [])
        objects = "、".join(frame.get("equipment") or [])
        if match == "不匹配":
            add_anomaly(
                "G05", "高", "疑似无计划作业", frame,
                "现场作业动作与作业票允许内容不一致。",
                frame.get("evidence") or f"现场识别动作：{actions}",
                "系统自动纳入异常片段清单，保留图片、时间、摄像头、视觉文本和票面比对依据。",
                scores,
            )
            add_anomaly(
                "G06", "高", "设备对象或场景不符", frame,
                "现场设备对象或场景与票面主变基础、GIS室、电缆沟等对象不一致。",
                f"识别对象：{objects or '待确认'}；场景：{frame.get('scene')}",
                "继续调取相邻机位，确认是否为同一作业票覆盖区域。",
                scores,
            )
        if any("个体防护装备" in issue or "安全帽" in issue or "反光" in issue for issue in issues):
            add_anomaly(
                "G10", "中", "个体防护装备疑似不足", frame,
                "安全帽、反光衣或其他个体防护装备疑似缺失或置信度不足。",
                "；".join(issues),
                "后续真实模型接入后保留目标框、置信度和裁剪图作为证据。",
                scores,
            )
        if any("灭火器" in issue or "临边防护" in issue for issue in issues):
            add_anomaly(
                "G10", "中", "安全措施可见证据不足", frame,
                "票面风险控制要求对应的现场安全措施未被模型稳定检出。",
                "；".join(issues),
                "系统继续调取相邻时间片和其他机位画面补强证据。",
                scores,
            )
    if fact.get("plan_status") != "开工中":
        add_anomaly(
            "G02", "高", "计划状态不允许检查", None,
            f"票面状态为{fact.get('plan_status')}，不应触发开工中现场检查。",
            fact.get("plan_id") or "计划编号待确认",
            "仅对开工中作业票触发闭环检查。",
        )

    anomalies = sorted(anomaly_map.values(), key=lambda item: (0 if item["level"] == "高" else 1, item["rule_id"]))
    high = sum(1 for item in anomalies if item["level"] == "高")
    medium = sum(1 for item in anomalies if item["level"] == "中")
    matched_rules = [rules_by_id[rule_id] for rule_id in sorted(matched_rule_ids) if rule_id in rules_by_id]
    unmatched_frames = (vision.get("aggregates") or {}).get("unmatched_frames", [])
    uncertain_frames = (vision.get("aggregates") or {}).get("uncertain_frames", [])
    activities = [name for name, _ in (vision.get("aggregates") or {}).get("activities", [])[:8]]
    expected = vision.get("expected_profile") or {}
    dimension_comparison = [
        {"dimension": "作业状态", "plan": fact.get("plan_status") or "待确认", "vision": "现场存在施工活动" if frame_issues else "未获取画面", "result": "匹配" if fact.get("plan_status") == "开工中" else "不匹配", "evidence": "状态门控规则 G02"},
        {"dimension": "时间", "plan": f"{(fact.get('plan_time_range') or {}).get('start')} 至 {(fact.get('plan_time_range') or {}).get('end')}", "vision": "近30分钟连续快照", "result": "匹配", "evidence": "媒体调取窗口与当前检查时间一致"},
        {"dimension": "地点", "plan": fact.get("work_location") or ticket.get("work_location"), "vision": "合景站北侧主变基础固定监控、GIS室电缆沟固定监控", "result": "需确认" if uncertain_frames else "匹配", "evidence": "摄像头点位已绑定作业票"},
        {"dimension": "作业内容", "plan": "、".join(expected.get("expected_actions") or fact.get("work_actions") or []), "vision": "、".join(activities) or "待识别", "result": "不匹配" if unmatched_frames else "匹配", "evidence": "规则 G05：作业动作比对"},
        {"dimension": "设备对象", "plan": "、".join(expected.get("expected_objects") or fact.get("equipment_targets") or []), "vision": "逐帧目标检测结果", "result": "不匹配" if any(item.get("rule_id") == "G06" for item in anomalies) else "匹配", "evidence": "规则 G06：设备对象比对"},
        {"dimension": "安全措施", "plan": "、".join(expected.get("expected_safety") or ["安全帽", "反光衣", "临边防护", "灭火器"]), "vision": "防护装备、临边防护、灭火器等目标检测", "result": "需确认" if any(item.get("rule_id") == "G10" for item in anomalies) else "匹配", "evidence": "规则 G10：安全措施可见证据"},
    ]
    workflow_stages = [
        {"name": "作业票解析入库", "status": "完成", "detail": f"计划编号 {fact.get('plan_id') or ticket.get('plan_id')}，计划状态 {fact.get('plan_status') or ticket.get('plan_status')}"},
        {"name": "现场图片调取", "status": "完成", "detail": f"近30分钟逐分钟快照 {vision.get('frame_count')} 张，已绑定作业票和摄像头"},
        {"name": "视觉理解", "status": "完成", "detail": "假设视觉模型输出目标检测、场景分类、作业动作识别和逐帧一致性评分"},
        {"name": "规则手册检索", "status": "完成", "detail": f"加载{len(rulebook.get('general_rules', []))}条通用规则、{len(rulebook.get('work_type_rules', []))}类作业类型规则"},
        {"name": "违规检测", "status": "完成", "detail": f"高风险 {high} 类，中风险 {medium} 类，命中规则 {len(matched_rules)} 条"},
    ]
    result = {
        "conclusion": "发现疑似无计划/不一致片段" if high else "未发现高等级不一致，存在待模型确认项" if medium else "未发现明显违规",
        "risk_level": "高" if high else "中" if medium else "低",
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "matched_rules": matched_rules,
        "dimension_comparison": dimension_comparison,
        "workflow_stages": workflow_stages,
        "rulebook_summary": {
            "name": rulebook.get("name"),
            "version": rulebook.get("version"),
            "manual_path": rulebook.get("manual_path"),
            "source_stats": rulebook.get("source_stats", {}),
            "general_rule_count": len(rulebook.get("general_rules", [])),
            "work_type_rule_count": len(rulebook.get("work_type_rules", [])),
        },
        "rules": [f"{rule.get('id')} {rule.get('name')}：{rule.get('condition')}" for rule in rulebook.get("general_rules", [])[:12]],
    }
    result["report_md"] = _pilot_report_markdown(ticket, vision, result)
    return result

def _save_pilot_inspection(ticket: dict[str, Any], frames: list[dict[str, Any]], vision: dict[str, Any], detection: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fact = ticket.get("ticket_fact", {})
    record = {
        "id": f"pilot_{uuid.uuid4().hex[:8]}",
        "ticket_id": ticket.get("id"),
        "created_at": now,
        "operator": "合景在线试点",
        "mode": "pilot_closed_loop",
        "ticket": ticket.get("plan_id"),
        "location": ticket.get("work_location"),
        "status": "发现异常" if detection.get("risk_level") in {"高", "中"} else "自动通过",
        "risk": detection.get("risk_level"),
        "updated_at": now,
        "ticket_fact": fact,
        "media_manifest": frames,
        "vision_result": vision,
        "violation_result": detection,
        "report": {
            "conclusion": detection.get("conclusion"),
            "risk_level": detection.get("risk_level"),
            "evidence": [f"绑定现场图片：{len(frames)}张", f"视觉理解帧：{vision.get('frame_count')}帧", f"异常事件：{detection.get('anomaly_count')}类", f"命中规则：{len(detection.get('matched_rules') or [])}条"],
            "next_actions": ["保存作业票计划侧事实", "调取近30分钟现场图片", "执行视觉理解", "检索违规检测指导手册", "输出异常片段清单和检测报告"],
            "report_md": detection.get("report_md", ""),
        },
        "timeline": [
            {"time": datetime.now().strftime("%H:%M:%S"), "event": "作业票解析并入库"},
            {"time": datetime.now().strftime("%H:%M:%S"), "event": f"绑定现场图片{len(frames)}张"},
            {"time": datetime.now().strftime("%H:%M:%S"), "event": "完成视觉理解模拟"},
            {"time": datetime.now().strftime("%H:%M:%S"), "event": f"完成违规检测：{detection.get('conclusion')}"},
        ],
    }
    save_inspection(record)
    return record


@app.post("/api/work-tickets/import")
def import_work_ticket(payload: ImportTicketRequest) -> dict[str, Any]:
    record = payload.record or {}
    if record.get("source_type") == "database":
        return {"success": True, "created": False, "ticket": None, "message": "数据库作业票已在库中，无需重复入库。"}
    result = import_parse_record_as_ticket(record)
    return {"success": True, **result}


@app.get("/api/pilot/hj")
def pilot_hj_status() -> dict[str, Any]:
    ticket, parse_record, created = _ensure_pilot_ticket()
    assets = _pilot_asset_pool()
    return {
        "success": True,
        "project": "220千伏合景输变电工程在线试点",
        "ticket": ticket,
        "parse_record": parse_record,
        "ticket_created": created,
        "image_count": len(assets),
        "image_sources": [{"title": item.get("title"), "source_page": item.get("source_page"), "filename": item.get("filename")} for item in assets],
    }


@app.post("/api/pilot/hj/run")
def run_pilot_hj() -> dict[str, Any]:
    ticket, parse_record, created = _ensure_pilot_ticket()
    return _run_full_inspection(ticket, parse_record, created, project_name="220千伏合景输变电工程在线试点")


@app.post("/api/inspection/run-full")
def run_full_inspection(payload: FullInspectionRequest) -> dict[str, Any]:
    ticket, parse_record, created = _ensure_ticket_for_full_inspection(payload)
    return _run_full_inspection(ticket, parse_record, created)


@app.post("/api/work-tickets/parse")
async def parse_work_ticket(
    text: str = Form(""),
    sample_id: str = Form(""),
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    source_type = "text"
    raw_text = text.strip()
    ocr_result: dict[str, Any] | None = None
    pdf_result: dict[str, Any] | None = None
    if file is not None and file.filename:
        content = await file.read()
        raw_text, source_type, ocr_result, pdf_result, _ = _extract_upload_text(content, file.filename, raw_text)
    record = _make_parse_record(raw_text=raw_text, sample_id=sample_id, source_type=source_type, ocr_result=ocr_result, pdf_result=pdf_result)
    return {"success": True, "record": record}


@app.post("/api/work-tickets/parse/stream")
async def parse_work_ticket_stream(
    text: str = Form(""),
    sample_id: str = Form(""),
    file: UploadFile | None = File(None),
) -> StreamingResponse:
    source_type = "text"
    raw_text = text.strip()
    file_content: bytes | None = None
    file_name = ""
    if file is not None and file.filename:
        file_name = file.filename
        file_content = await file.read()

    def generate():
        steps = ["接收作业票输入"]
        if file_content is not None:
            steps.append("抽取PDF文本" if Path(file_name).suffix.lower() == ".pdf" else "执行图片OCR识别")
        steps.extend([
            "识别基础字段",
            "拆分作业内容",
            "生成媒体调取任务",
            "执行入库分析智能体",
            "保存解析记录",
        ])
        for idx, step in enumerate(steps[:-1]):
            yield _sse({"type": "step", "index": idx, "title": step, "status": "running"})
            time.sleep(0.16)
            yield _sse({"type": "step", "index": idx, "title": step, "status": "done"})
        try:
            parse_text = raw_text
            current_source_type = source_type
            ocr_result: dict[str, Any] | None = None
            pdf_result: dict[str, Any] | None = None
            if file_content is not None:
                parse_text, current_source_type, ocr_result, pdf_result, file_event = _extract_upload_text(file_content, file_name, raw_text)
                yield _sse(file_event)
            record = _make_parse_record(raw_text=parse_text, sample_id=sample_id, source_type=current_source_type, ocr_result=ocr_result, pdf_result=pdf_result)
            yield _sse({"type": "step", "index": len(steps) - 1, "title": steps[-1], "status": "done"})
            yield _sse({"type": "final", "record": record})
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _build_inspection_media(fact: dict[str, Any], media_task: dict[str, Any]) -> list[dict[str, Any]]:
    files = _site_media_files()
    args = media_task.get("arguments", {}) if media_task else {}
    cameras = args.get("candidate_cameras") or [{"camera_id": "CAM_GZ_AUTO", "camera_name": f"{fact.get('work_location') or '作业现场'}固定监控"}]
    main_camera = cameras[0]
    now = datetime.now().replace(second=0, microsecond=0)
    manifest = []
    for idx in range(30):
        source = files[idx % len(files)] if files else None
        capture = now - timedelta(minutes=29 - idx)
        url = f"/api/media/site/{source.name}" if source else ""
        manifest.append(
            {
                "media_id": f"frame_{idx + 1:02d}",
                "media_type": "现场图片",
                "camera_id": main_camera.get("camera_id", "CAM_GZ_AUTO"),
                "camera_name": main_camera.get("camera_name", "固定监控"),
                "capture_time": capture.strftime("%Y-%m-%d %H:%M:%S"),
                "file_path": url,
                "thumbnail_path": url,
                "status": "已绑定",
                "minute_index": idx + 1,
                "work_location": fact.get("work_location"),
                "source_asset": source.name if source else "",
            }
        )
    return manifest


@app.post("/api/interaction/start-inspection")
def start_inspection(payload: InspectionRequest) -> dict[str, Any]:
    try:
        if payload.ticket_id:
            ticket = get_ticket(payload.ticket_id)
            if ticket:
                result = _run_full_inspection(
                    ticket,
                    {
                        "ticket_id": ticket.get("id"),
                        "source_type": "database",
                        "summary": ticket.get("project_name") or ticket.get("plan_id"),
                        "ticket_fact": ticket.get("ticket_fact", {}),
                        "validation_result": ticket.get("validation_result", {}),
                        "media_query_task": ticket.get("media_query_task", {}),
                        "agent_analysis": ticket.get("agent_analysis", {}),
                    },
                    False,
                )
                return {"success": True, "inspection": result["inspection"], "result": result}
    except Exception:
        pass
    ticket = get_ticket(payload.ticket_id) if payload.ticket_id else None
    fact = ticket["ticket_fact"] if ticket else (payload.ticket_fact or {})
    media_task = ticket["media_query_task"] if ticket else (payload.media_query_task or {})
    if fact:
        pseudo_ticket = {
            "id": payload.ticket_id,
            "plan_id": fact.get("plan_id"),
            "project_name": fact.get("project_name"),
            "work_location": fact.get("work_location"),
            "work_content_raw": fact.get("work_content_raw"),
            "plan_status": fact.get("plan_status"),
            "risk_level": fact.get("risk_level"),
            "plan_start": (fact.get("plan_time_range") or {}).get("start"),
            "plan_end": (fact.get("plan_time_range") or {}).get("end"),
            "ticket_fact": fact,
            "media_query_task": media_task,
            "validation_result": {},
        }
        result = _run_full_inspection(pseudo_ticket, {"ticket_fact": fact, "media_query_task": media_task}, False)
        return {"success": True, "inspection": result["inspection"], "result": result}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "id": f"insp_{uuid.uuid4().hex[:8]}",
        "ticket_id": payload.ticket_id,
        "created_at": now,
        "operator": payload.operator,
        "mode": payload.mode,
        "ticket": "待补充",
        "location": "待补充",
        "status": "未触发检查",
        "risk": "待确认",
        "updated_at": now,
        "ticket_fact": {},
        "media_manifest": [],
        "report": {"conclusion": "未提供作业票，无法发起检查。", "risk_level": "待确认", "evidence": [], "next_actions": ["先完成作业票解析"]},
        "timeline": [{"time": datetime.now().strftime("%H:%M:%S"), "event": "检查未启动"}],
    }
    save_inspection(record)
    return {"success": True, "inspection": record}


@app.get("/api/interaction/inspections")
def inspections() -> dict[str, Any]:
    return {"items": list_inspections(50)}


@app.get("/api/interaction/llm-status")
def llm_status() -> dict[str, Any]:
    return public_model_status()


@app.get("/api/interaction/conversations")
def conversations() -> dict[str, Any]:
    return {"items": list_conversations(30)}


@app.get("/api/interaction/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str) -> dict[str, Any]:
    return {"items": list_conversation_messages(conversation_id)}



def _chat_messages(message: str, fact: dict[str, Any]) -> list[dict[str, str]]:
    ticket_context = json.dumps(fact or {}, ensure_ascii=False)
    return [
        {
            "role": "system",
            "content": (
                "你是无计划作业智能检查平台的系统交互智能体。"
                "你必须只用中文回答，输出 Markdown，但不要输出 Markdown 表格。"
                "平台当前阶段重点是作业票解析、作业检查发起、现场监控画面调取和计划-现场一致性比对。"
                "无计划作业不是作业票字段本身，而是现场画面识别结果与作业票计划在时间、地点、人员数量、作业内容、作业状态上的不一致。"
                "当前只有计划状态为“开工中”的作业票会触发自动作业检查。"
                "回答要结合给定作业票事实，避免泛泛而谈；不要提具体模型厂商；不要出现人工复核字样。"
            ),
        },
        {
            "role": "user",
            "content": f"作业票事实JSON：{ticket_context}\n\n用户问题：{message}",
        },
    ]


def _fallback_answer(message: str, fact: dict[str, Any], error: str) -> str:
    plan_status = fact.get("plan_status") or "未选择作业票"
    plan_id = fact.get("plan_id") or "待补充"
    location = fact.get("work_location") or "待补充"
    return (
        f"### 模型 API 暂不可用\n"
        f"{error}\n\n"
        f"### 当前作业票\n"
        f"- 计划编号：{plan_id}\n"
        f"- 计划状态：{plan_status}\n"
        f"- 作业地点：{location}\n\n"
        f"系统已保留本次问题，模型 API 恢复后可继续基于该作业票上下文交互。"
    )


@app.post("/api/interaction/chat/stream")
def interaction_chat_stream(payload: ChatRequest) -> StreamingResponse:
    message = payload.message.strip()
    context = payload.context or {}
    fact = context.get("ticket_fact", {})
    title = fact.get("project_name") or message[:30] or "系统交互"
    conversation_id = ensure_conversation(payload.conversation_id, title=title, ticket_id=context.get("ticket_id"))
    save_chat_message(conversation_id, "user", message, {"ticket_fact": fact})
    messages = _chat_messages(message, fact)

    def generate():
        yield _sse({"type": "conversation", "conversation_id": conversation_id})
        chunks: list[str] = []
        provider = public_model_status()
        yielded_error = False
        for event in call_chat_stream(messages, temperature=0.2, timeout=90):
            if not event.get("ok"):
                yielded_error = True
                answer = _fallback_answer(message, fact, event.get("error", "模型 API 调用失败"))
                save_chat_message(conversation_id, "assistant", answer, {"provider": provider.get("provider"), "model": provider.get("model"), "success": False, "error": event.get("error")})
                yield _sse({"type": "error", "message": event.get("error", "模型 API 调用失败")})
                yield _sse({"type": "final", "conversation_id": conversation_id, "answer": answer, "provider": provider.get("provider"), "model": provider.get("model")})
                break
            content = event.get("content", "")
            if not content:
                continue
            chunks.append(content)
            yield _sse({"type": "delta", "content": content, "provider": event.get("provider"), "model": event.get("model")})
        if not yielded_error:
            answer = "".join(chunks).strip()
            save_chat_message(conversation_id, "assistant", answer, {"provider": provider.get("provider"), "model": provider.get("model"), "success": True})
            yield _sse({"type": "final", "conversation_id": conversation_id, "answer": answer, "provider": provider.get("provider"), "model": provider.get("model")})
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/interaction/chat")
def interaction_chat(payload: ChatRequest) -> dict[str, Any]:
    message = payload.message.strip()
    context = payload.context or {}
    fact = context.get("ticket_fact", {})
    conversation_id = ensure_conversation(payload.conversation_id, title=fact.get("project_name") or message[:30] or "系统交互", ticket_id=context.get("ticket_id"))
    save_chat_message(conversation_id, "user", message, {"ticket_fact": fact})
    provider = public_model_status()
    result = call_chat(_chat_messages(message, fact), temperature=0.2, timeout=60)
    if not result.get("ok"):
        answer = _fallback_answer(message, fact, result.get("error", "模型 API 调用失败"))
        save_chat_message(conversation_id, "assistant", answer, {"provider": provider.get("provider"), "model": provider.get("model"), "success": False, "error": result.get("error")})
        return {"success": False, "provider": provider.get("provider"), "model": provider.get("model"), "conversation_id": conversation_id, "answer": answer, "suggested_actions": ["检查模型 API 配置", "确认服务器网络可访问模型服务"]}
    answer = result.get("content", "")
    save_chat_message(conversation_id, "assistant", answer, {"provider": result.get("provider"), "model": result.get("model"), "success": True})
    return {
        "success": True,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "conversation_id": conversation_id,
        "answer": answer,
        "suggested_actions": ["发起作业检查", "绑定现场画面", "等待视觉比对"],
    }
