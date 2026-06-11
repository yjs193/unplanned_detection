
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests


def load_env_files() -> None:
    roots = [Path(__file__).resolve().parent.parent / ".env"]
    for env_path in roots:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


load_env_files()

QWEN_API_KEY = os.getenv("META_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
QWEN_BASE_URL = os.getenv("META_BASE_URL") or os.getenv("QWEN_BASE_URL", "")
QWEN_MODEL = os.getenv("META_MODEL_NAME") or os.getenv("QWEN_MODEL", "qwen-plus-latest")


def _chat_url() -> str:
    base = QWEN_BASE_URL.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def minimax_available() -> bool:
    return bool(QWEN_API_KEY)


def call_minimax(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 45) -> dict[str, Any]:
    if not QWEN_API_KEY:
        return {"ok": False, "content": "", "error": "未配置 META_API_KEY、QWEN_API_KEY 或 DASHSCOPE_API_KEY"}
    try:
        resp = requests.post(
            _chat_url(),
            headers={"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"},
            json={"model": QWEN_MODEL, "messages": messages, "temperature": temperature},
            timeout=timeout,
        )
        if resp.status_code >= 400:
            return {"ok": False, "content": "", "error": f"Qwen API HTTP {resp.status_code}: {resp.text[:300]}"}
        payload = resp.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "content": content, "provider": "Qwen", "model": QWEN_MODEL, "raw": payload}
    except Exception as exc:
        return {"ok": False, "content": "", "error": f"Qwen API 调用失败：{exc}"}


def extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def build_agent_analysis(ticket_fact: dict[str, Any], validation_result: dict[str, Any], use_llm: bool = False) -> dict[str, Any]:
    attention = ticket_fact.get("plan_status") == "开工中" or ticket_fact.get("risk_level") == "高"
    base = {
        "agent_name": "作业票入库分析智能体",
        "risk_judgement": "重点跟踪" if attention else "常规检查",
        "key_findings": [],
        "dispatch_suggestion": "按作业地点匹配固定监控，必要时派发无人机补拍。",
        "review_required": False,
        "model_provider": "rules",
    }
    base["key_findings"].append(
        f"作业票覆盖{ticket_fact.get('district', '广州')}{ticket_fact.get('work_location', '作业地点')}，计划状态为{ticket_fact.get('plan_status', '待确认')}。"
    )
    base["key_findings"].append(
        f"计划作业内容为{ticket_fact.get('work_content_raw', '待补充')}，后续需与现场识别到的时间、地点、人员和作业类型进行一致性比对。"
    )
    if not ticket_fact.get("video_control_enabled"):
        base["key_findings"].append("未纳入视频管控，自动检查时应优先匹配周边固定监控，必要时补充无人机画面。")
    if not ticket_fact.get("work_leader") or ticket_fact.get("work_leader") == "无":
        base["key_findings"].append("工作负责人字段缺失，后续一致性比对时应同步校验现场管控责任信息。")
    if not use_llm or not minimax_available():
        return base

    prompt = (
        "你是电网基建无计划作业检查平台中的作业票入库分析智能体。"
        "请只输出JSON，不要输出Markdown。字段包括：risk_judgement、key_findings、dispatch_suggestion、review_required。review_required默认false，只有现场与计划比对异常时才进入问题确认。"
        "所有内容必须是中文。\n"
        f"作业票事实：{json.dumps(ticket_fact, ensure_ascii=False)}\n"
        f"校验结果：{json.dumps(validation_result, ensure_ascii=False)}"
    )
    result = call_minimax([
        {"role": "system", "content": "你负责电网基建作业票结构化入库前的风险分析。"},
        {"role": "user", "content": prompt},
    ], temperature=0.1, timeout=35)
    if not result["ok"]:
        base["model_provider"] = "rules_qwen_failed"
        base["llm_error"] = result["error"]
        return base
    parsed = extract_json_object(result["content"])
    if not parsed:
        base["model_provider"] = "qwen_text"
        base["key_findings"] = [result["content"][:500]]
        return base
    base.update({k: parsed[k] for k in ["risk_judgement", "key_findings", "dispatch_suggestion", "review_required"] if k in parsed})
    base["model_provider"] = "qwen"
    return base


def clean_minimax_answer(content: str) -> str:
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.I).strip()
    content = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()



def call_minimax_stream(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 60):
    if not QWEN_API_KEY:
        yield {"ok": False, "content": "", "error": "未配置 META_API_KEY、QWEN_API_KEY 或 DASHSCOPE_API_KEY"}
        return
    try:
        resp = requests.post(
            _chat_url(),
            headers={"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"},
            json={"model": QWEN_MODEL, "messages": messages, "temperature": temperature, "stream": True},
            timeout=timeout,
            stream=True,
        )
        if resp.status_code >= 400:
            yield {"ok": False, "content": "", "error": f"Qwen API HTTP {resp.status_code}: {resp.text[:300]}"}
            return
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8", errors="ignore")
            if not decoded.startswith("data: "):
                continue
            payload = decoded[6:].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
            except Exception:
                continue
            delta = data.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                yield {"ok": True, "content": content, "provider": "Qwen", "model": QWEN_MODEL}
    except Exception as exc:
        yield {"ok": False, "content": "", "error": f"Qwen API 调用失败：{exc}"}
