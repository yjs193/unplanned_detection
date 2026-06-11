from __future__ import annotations

import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .prompt_settings import get_agent_prompt
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = Path(__file__).resolve().parent / "media" / "vedio"
VISION_FRAME_DIR = Path(__file__).resolve().parent / "media" / "vision_frames"
WORKBOOKS = [
    ("新隆沙", PROJECT_ROOT / "新隆沙信息表.xlsx"),
    ("汇景站", PROJECT_ROOT / "汇景站信息表.xlsx"),
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _json_from_model_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _video_files() -> list[Path]:
    if not VIDEO_DIR.exists():
        return []
    return sorted(path for path in VIDEO_DIR.iterdir() if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"})


def _video_prefix_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in _video_files():
        prefix = path.name.split("_", 1)[0]
        index.setdefault(prefix, []).append(path)
    return index


def load_ticket_video_bindings() -> list[dict[str, Any]]:
    video_index = _video_prefix_index()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for project_label, workbook_path in WORKBOOKS:
        if not workbook_path.exists():
            continue
        values = _read_xlsx_rows(workbook_path)
        if not values:
            continue
        headers = [_clean(item) for item in values[0]]
        header_index = {name: index for index, name in enumerate(headers) if name}
        ticket_col = header_index.get("作业票编号")
        plan_col = header_index.get("关联周计划")
        if ticket_col is None or plan_col is None:
            continue
        for row in values[1:]:
            ticket_no = _clean(row[ticket_col] if ticket_col < len(row) else "")
            weekly_plan = _clean(row[plan_col] if plan_col < len(row) else "")
            if not ticket_no:
                continue
            videos = video_index.get(weekly_plan, [])
            key = (project_label, ticket_no, weekly_plan)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "project_label": project_label,
                    "workbook": workbook_path.name,
                    "ticket_no": ticket_no,
                    "weekly_plan": weekly_plan,
                    "ticket_name": _clean(row[header_index.get("作业票名称", -1)]) if header_index.get("作业票名称", -1) >= 0 else "",
                    "plan_time_range": _clean(row[header_index.get("计划时间段", -1)]) if header_index.get("计划时间段", -1) >= 0 else "",
                    "execution_status": _clean(row[header_index.get("执行状态", -1)]) if header_index.get("执行状态", -1) >= 0 else "",
                    "risk_level": _clean(row[header_index.get("风险等级", -1)]) if header_index.get("风险等级", -1) >= 0 else "",
                    "task_category": _clean(row[header_index.get("施工任务专业分类", -1)]) if header_index.get("施工任务专业分类", -1) >= 0 else "",
                    "task_name": _clean(row[header_index.get("三级作业任务", -1)]) if header_index.get("三级作业任务", -1) >= 0 else "",
                    "site_leader": _clean(row[header_index.get("现场作业负责人", -1)]) if header_index.get("现场作业负责人", -1) >= 0 else "",
                    "matched": bool(videos),
                    "video_count": len(videos),
                    "videos": [_video_meta(path) for path in videos],
                }
            )
    return rows


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(".//x:si", ns):
                texts = [node.text or "" for node in item.findall(".//x:t", ns)]
                shared.append("".join(texts))
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in archive.namelist():
            candidates = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            if not candidates:
                return []
            sheet_name = sorted(candidates)[0]
        root = ElementTree.fromstring(archive.read(sheet_name))
    rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values: list[str] = []
        for cell in row.findall("x:c", ns):
            ref = cell.attrib.get("r", "")
            col_index = _excel_col_index(ref)
            while len(values) < col_index:
                values.append("")
            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", ns)
            inline_node = cell.find("x:is/x:t", ns)
            raw = value_node.text if value_node is not None else inline_node.text if inline_node is not None else ""
            if cell_type == "s":
                try:
                    raw = shared[int(raw)]
                except Exception:
                    raw = ""
            values.append(_clean(raw))
        rows.append(values)
    return rows


def _excel_col_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    if not letters:
        return 0
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value - 1


def find_ticket_video_binding(ticket: dict[str, Any] | None = None, ticket_id_or_no: str | None = None) -> dict[str, Any] | None:
    keys = {
        _clean(ticket_id_or_no),
        _clean((ticket or {}).get("plan_id")),
        _clean((ticket or {}).get("ticket_no")),
        _clean(((ticket or {}).get("ticket_fact") or {}).get("plan_id")),
        _clean(((ticket or {}).get("ticket_fact") or {}).get("ticket_no")),
    }
    keys.discard("")
    for row in load_ticket_video_bindings():
        if row.get("ticket_no") in keys:
            return row
    return None


def _video_meta(path: Path) -> dict[str, Any]:
    stat = path.stat()
    name = path.name
    parts = name.rsplit(".", 1)[0].split("_")
    return {
        "filename": name,
        "weekly_plan": parts[0] if parts else name.split("_", 1)[0],
        "camera_id": parts[1] if len(parts) > 1 else "",
        "start_token": parts[2] if len(parts) > 2 else "",
        "end_token": parts[3] if len(parts) > 3 else "",
        "size_mb": round(stat.st_size / 1024 / 1024, 1),
        "url": f"/api/media/vedio/{name}",
    }


def list_vision_bindings(ticket: dict[str, Any] | None = None, keyword: str | None = None) -> dict[str, Any]:
    rows = load_ticket_video_bindings()
    if ticket:
        row = find_ticket_video_binding(ticket)
        rows = [row] if row else []
    text = _clean(keyword)
    if text:
        rows = [
            row
            for row in rows
            if any(text in _clean(row.get(key)) for key in ["ticket_no", "weekly_plan", "ticket_name", "task_name", "project_label"])
        ]
    return {
        "total": len(rows),
        "bound_count": sum(1 for row in rows if row.get("matched")),
        "items": rows,
    }


def _select_video(binding: dict[str, Any] | None, filename: str | None = None) -> Path | None:
    safe_name = Path(filename or "").name
    if safe_name:
        candidate = VIDEO_DIR / safe_name
        if candidate.exists() and candidate.is_file():
            return candidate
    for item in (binding or {}).get("videos") or []:
        candidate = VIDEO_DIR / Path(item.get("filename") or "").name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _configure_external_agent() -> Any:
    import vision_agent as external_agent

    external_agent.API_KEY = (
        os.getenv("VISION_API_KEY")
        or os.getenv("API_KEY")
        or os.getenv("META_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or external_agent.API_KEY
    )
    external_agent.BASE_URL = os.getenv("VISION_BASE_URL") or os.getenv("BASE_URL") or os.getenv("META_BASE_URL") or external_agent.BASE_URL
    external_agent.VLM_MODEL = os.getenv("VISION_MODEL") or os.getenv("VLM_MODEL") or "qwen-vl-max"
    return external_agent


def analyze_ticket_video(
    ticket: dict[str, Any],
    video_filename: str | None = None,
    frame_count: int = 8,
    use_model: bool = True,
) -> dict[str, Any]:
    binding = find_ticket_video_binding(ticket)
    video_path = _select_video(binding, video_filename)
    if not video_path:
        return _fallback_result(ticket, binding, None, [], "未找到与该作业票绑定的本地视频。")

    analysis_id = f"vision_{uuid.uuid4().hex[:10]}"
    frame_count = max(1, min(int(frame_count or 8), 12))
    frame_urls: list[str] = []
    frame_files: list[Path] = []
    model_payload: dict[str, Any] = {}
    fallback_reason = ""

    try:
        external_agent = _configure_external_agent()
        temp_frames = external_agent.extract_evenly_spaced_frames(video_path, frame_count)
        VISION_FRAME_DIR.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(temp_frames, start=1):
            target = VISION_FRAME_DIR / f"{analysis_id}_frame_{index:02d}.jpg"
            shutil.copyfile(frame, target)
            frame_files.append(target)
            frame_urls.append(f"/api/media/vision-frame/{target.name}")
        if use_model:
            model_text = external_agent.chat_with_vlm(get_agent_prompt("vision_understanding_agent"), temp_frames)
            model_payload = _json_from_model_text(model_text)
            if not model_payload:
                fallback_reason = "视觉模型返回内容未能解析为 JSON，已保留抽帧并生成兜底证据链。"
        else:
            fallback_reason = "本次未启用云端视觉模型，已基于抽帧生成兜底证据链。"
    except Exception as exc:
        fallback_reason = f"视觉理解调用失败，已使用兜底证据链：{exc}"
    finally:
        try:
            if "temp_frames" in locals() and temp_frames:
                temp_dir = temp_frames[0].parent
                for frame in temp_frames:
                    frame.unlink(missing_ok=True)
                temp_dir.rmdir()
        except Exception:
            pass

    if not model_payload:
        return _fallback_result(ticket, binding, video_path, frame_urls, fallback_reason)
    return _normalize_model_result(ticket, binding, video_path, frame_urls, model_payload, fallback_reason)


def _fallback_result(
    ticket: dict[str, Any],
    binding: dict[str, Any] | None,
    video_path: Path | None,
    frame_urls: list[str],
    reason: str,
) -> dict[str, Any]:
    fact = ticket.get("ticket_fact") or {}
    work_content = fact.get("work_content_raw") or ticket.get("work_content_raw") or "票面作业内容待补充"
    frames = []
    for index, url in enumerate(frame_urls or [], start=1):
        text = f"第{index:02d}帧已从绑定视频抽取，需由视觉模型进一步识别；当前票面允许作业内容为：{work_content[:80]}。"
        frames.append(_frame_row(index, url, text))
    evidence_lines = [row["evidence_text"] for row in frames]
    if not evidence_lines:
        if video_path:
            video = _video_meta(video_path)
            evidence_lines.extend(
                [
                    f"视频来源：作业票已通过信息表关联周计划 {video.get('weekly_plan') or '待补充'} 匹配到本地视频 {video.get('filename')}。",
                    f"摄像头编号：{video.get('camera_id') or '待补充'}；视频片段标识：{video.get('start_token') or '-'} 至 {video.get('end_token') or '-'}。",
                    f"票面允许作业内容：{work_content[:160]}。",
                    "当前服务器缺少视频抽帧解码组件，尚未形成逐帧画面事实；该证据链只证明作业票与现场视频来源已绑定，后续需安装抽帧组件后复核画面内容。",
                ]
            )
        else:
            evidence_lines.append(reason or "未取得现场视频帧，无法生成有效现场证据链。")
    return {
        "success": bool(frame_urls or video_path),
        "analysis_id": f"vision_{uuid.uuid4().hex[:10]}",
        "source": "local_video_fallback",
        "model_name": "本地视频抽帧兜底",
        "fallback_reason": reason,
        "final_decision_allowed": False,
        "output_boundary": "现场事实证据包，不直接作最终违规裁决",
        "ticket_summary": _ticket_summary(ticket),
        "binding": binding,
        "video": _video_meta(video_path) if video_path else None,
        "frame_count": len(frames),
        "frames": frames,
        "aggregates": {"work_process": "；".join(evidence_lines[:4]), "activities": [], "unmatched_frames": [], "uncertain_frames": []},
        "evidence_text": "\n".join(evidence_lines),
        "media_manifest": _frame_media_manifest(frames, video_path),
    }


def _normalize_model_result(
    ticket: dict[str, Any],
    binding: dict[str, Any] | None,
    video_path: Path,
    frame_urls: list[str],
    payload: dict[str, Any],
    fallback_reason: str,
) -> dict[str, Any]:
    frame_texts = payload.get("frames") if isinstance(payload.get("frames"), list) else []
    rows = []
    for index, url in enumerate(frame_urls, start=1):
        text = _clean(frame_texts[index - 1] if index - 1 < len(frame_texts) else "")
        if not text:
            text = f"第{index:02d}帧已抽取，模型未返回该帧描述。"
        rows.append(_frame_row(index, url, text))
    process = _clean(payload.get("work_process"))
    evidence_lines = [row["evidence_text"] for row in rows]
    if process:
        evidence_lines.append(f"连续过程：{process}")
    return {
        "success": True,
        "analysis_id": f"vision_{uuid.uuid4().hex[:10]}",
        "source": "local_vision_agent",
        "model_name": os.getenv("VISION_MODEL") or os.getenv("VLM_MODEL") or "qwen-vl-max",
        "fallback_reason": fallback_reason,
        "final_decision_allowed": False,
        "output_boundary": "现场事实证据包，不直接作最终违规裁决",
        "ticket_summary": _ticket_summary(ticket),
        "binding": binding,
        "video": _video_meta(video_path),
        "frame_count": len(rows),
        "frames": rows,
        "aggregates": {"work_process": process, "activities": _extract_activity_words(evidence_lines), "unmatched_frames": [], "uncertain_frames": []},
        "raw_model_output": payload,
        "evidence_text": "\n".join(evidence_lines),
        "media_manifest": _frame_media_manifest(rows, video_path),
    }


def _frame_row(index: int, image_url: str, text: str) -> dict[str, Any]:
    return {
        "frame_index": index,
        "display_label": f"第{index:02d}帧",
        "image_url": image_url,
        "evidence_text": text,
        "facts": [{"category": "现场事实", "evidence_text": text, "confidence": 0.72}],
    }


def _frame_media_manifest(frames: list[dict[str, Any]], video_path: Path | None) -> list[dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return [
        {
            "media_id": f"vision_frame_{row['frame_index']:02d}",
            "display_label": row["display_label"],
            "media_type": "视频抽帧",
            "camera_id": (_video_meta(video_path).get("camera_id") if video_path else "") or "本地视频",
            "camera_name": "本地绑定视频抽帧",
            "capture_time": now,
            "file_path": row["image_url"],
            "thumbnail_path": row["image_url"],
            "status": "已抽帧",
            "minute_index": row["frame_index"],
        }
        for row in frames
    ]


def _ticket_summary(ticket: dict[str, Any]) -> dict[str, Any]:
    fact = ticket.get("ticket_fact") or {}
    return {
        "id": ticket.get("id"),
        "plan_id": ticket.get("plan_id") or fact.get("plan_id"),
        "ticket_no": ticket.get("ticket_no") or fact.get("ticket_no"),
        "project_name": ticket.get("project_name") or fact.get("project_name"),
        "work_location": ticket.get("work_location") or fact.get("work_location"),
        "work_content_raw": ticket.get("work_content_raw") or fact.get("work_content_raw"),
        "plan_status": ticket.get("plan_status") or fact.get("plan_status"),
        "risk_level": ticket.get("risk_level") or fact.get("risk_level"),
    }


def _extract_activity_words(lines: list[str]) -> list[tuple[str, int]]:
    keywords = ["基础施工", "电缆施工", "设备安装", "拆除", "开挖", "回填", "吊装", "围挡", "材料转运", "巡视", "清理"]
    text = "\n".join(lines)
    return [(word, text.count(word)) for word in keywords if word in text]
