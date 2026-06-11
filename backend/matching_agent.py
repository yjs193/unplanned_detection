from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from .model_api import (
    call_meta_chat as call_chat,
    call_meta_chat_with_logprobs as call_chat_with_logprobs,
    public_meta_model_status as public_model_status,
)
from .prompt_settings import get_agent_prompt


MATCH_RESULT_VALUES = {"未发现明显异常", "需持续观察", "疑似不一致", "明显不一致"}
WORK_KEYWORDS = [
    "钢筋绑扎",
    "模板安装",
    "混凝土浇筑",
    "混凝土浇筑准备",
    "电缆沟开挖",
    "沟槽开挖",
    "接地焊接",
    "接地网敷设",
    "材料转运",
    "塔材转运",
    "构件吊装",
    "吊装",
    "动火",
    "焊接",
    "展放导地线",
    "紧线",
    "压接",
    "附件安装",
    "跨越架搭设",
    "封网施工",
    "现场警戒",
    "支护",
    "预埋件安装",
    "场地清理",
    "螺栓复紧",
]


def build_ticket_task_text(ticket_fact: dict[str, Any]) -> str:
    parts: list[str] = []
    work_content_items = ticket_fact.get("work_content_items") or []
    if isinstance(work_content_items, list) and work_content_items:
        parts.append("；".join(str(item) for item in work_content_items if item))
    for key in ["work_content_raw", "work_content_summary"]:
        value = ticket_fact.get(key)
        if value:
            parts.append(str(value))
    for key in ["work_actions", "normalized_work_types", "equipment_targets", "special_operations"]:
        values = ticket_fact.get(key) or []
        if isinstance(values, list) and values:
            parts.append("、".join(str(item) for item in values if item))
    return "\n".join(part for part in parts if part).strip()


def run_task_video_matching(
    ticket_task_text: str,
    video_evidence_text: str,
    ticket_id: str | None = None,
    probability_threshold: float = 0.35,
    enable_second_video_reasoning: bool = True,
    risk_level: str | None = None,
) -> dict[str, Any]:
    task_text = (ticket_task_text or "").strip()
    evidence_text = (video_evidence_text or "").strip()
    probability_threshold = _safe_float(probability_threshold, 0.35)
    thresholds = _dynamic_thresholds(risk_level, probability_threshold)
    match_id = f"match_{uuid.uuid4().hex[:10]}"
    if not task_text:
        return _error(match_id, "缺少作业票任务文本：请传 ticket_task_text，或传 ticket_id 让接口从工单库读取。")
    if not evidence_text:
        return _error(match_id, "缺少视频证据链文本：请传 video_evidence_text。")

    status = public_model_status()
    if not status.get("available"):
        result = _rule_based_match(task_text, evidence_text)
        return _wrap_result(
            match_id,
            ticket_id,
            result,
            "rules",
            "rule-fallback",
            llm_used=False,
            probability_threshold=probability_threshold,
            probability_thresholds=thresholds,
            risk_level=thresholds["risk_level"],
            second_pass={"triggered": False, "reason": "模型 API 未配置，无法执行 token probability 与二次视频重查。"},
            final_decision_source="rule_fallback",
            manual_review_required=False,
            auto_flow_stopped=False,
            review_trace={
                "review_triggered": False,
                "reason": "规则兜底链路直接禁用二次复核，避免无效执行。",
                "thresholds": thresholds,
            },
            metrics=_review_metrics({"triggered": False}, {"result_conflict": False, "manual_review_required": False}),
            llm_error="模型 API 未配置，已使用规则兜底。",
        )

    first = _run_llm_match(task_text, evidence_text)
    if not first.get("ok"):
        result = _rule_based_match(task_text, evidence_text)
        return _wrap_result(
            match_id,
            ticket_id,
            result,
            status.get("provider") or "未配置",
            status.get("model") or "",
            probability_threshold=probability_threshold,
            probability_thresholds=thresholds,
            risk_level=thresholds["risk_level"],
            second_pass={"triggered": False, "reason": "第一次匹配模型调用失败，已使用规则兜底。"},
            final_decision_source="rule_fallback_after_llm_error",
            manual_review_required=False,
            auto_flow_stopped=False,
            review_trace={
                "review_triggered": False,
                "reason": "第一次匹配模型调用失败，规则兜底链路禁用二次复核。",
                "thresholds": thresholds,
            },
            metrics=_review_metrics({"triggered": False}, {"result_conflict": False, "manual_review_required": False}),
            llm_used=False,
            llm_error=first.get("error", "模型 API 调用失败，已使用规则兜底。"),
        )

    if not first.get("parsed"):
        result = _rule_based_match(task_text, evidence_text)
        return _wrap_result(
            match_id,
            ticket_id,
            result,
            first.get("provider") or status.get("provider") or "",
            first.get("model") or status.get("model") or "",
            probability_threshold=probability_threshold,
            probability_thresholds=thresholds,
            risk_level=thresholds["risk_level"],
            token_probability=first.get("token_probability"),
            avg_token_probability=first.get("avg_token_probability"),
            token_probability_count=first.get("token_probability_count"),
            token_probability_available=first.get("token_probability_available", False),
            first_pass=first,
            second_pass={"triggered": False, "reason": "第一次匹配模型返回内容不是可解析 JSON，已使用规则兜底。"},
            final_decision_source="rule_fallback_after_unparsed_llm",
            manual_review_required=False,
            auto_flow_stopped=False,
            review_trace={
                "review_triggered": False,
                "reason": "第一次匹配模型返回内容不可解析，规则兜底链路禁用二次复核。",
                "thresholds": thresholds,
            },
            metrics=_review_metrics({"triggered": False}, {"result_conflict": False, "manual_review_required": False}),
            llm_used=False,
            llm_error="模型返回内容不是可解析 JSON，已使用规则兜底。",
            llm_raw_excerpt=(first.get("content") or "")[:500],
        )

    first_result = _normalize_result(first["parsed"])
    trigger = _should_trigger_second_pass(first_result, first, thresholds, enable_second_video_reasoning)
    second_pass: dict[str, Any] = {
        "triggered": False,
        "reason": trigger["reason"],
        "trigger_reasons": trigger["trigger_reasons"],
        "thresholds": thresholds,
    }
    second_match: dict[str, Any] | None = None
    second_result: dict[str, Any] | None = None

    if trigger["triggered"]:
        second_pass = _run_second_pass(task_text, evidence_text, first_result, first, thresholds, trigger["trigger_reasons"])
        second_match = second_pass.get("second_match") if isinstance(second_pass.get("second_match"), dict) else None
        if second_match and second_match.get("ok") and second_match.get("parsed"):
            second_result = _normalize_result(second_match["parsed"])

    fusion = _fuse_results(first_result, second_result, first, second_match, second_pass, thresholds)
    final_match = fusion.get("final_match") if isinstance(fusion.get("final_match"), dict) else first
    review_trace = _build_review_trace(first, second_match, second_pass, fusion, thresholds)
    metrics = _review_metrics(second_pass, fusion)

    return _wrap_result(
        match_id,
        ticket_id,
        fusion["result"],
        first.get("provider") or status.get("provider") or "",
        first.get("model") or status.get("model") or "",
        llm_used=True,
        probability_threshold=probability_threshold,
        probability_thresholds=thresholds,
        risk_level=thresholds["risk_level"],
        token_probability=final_match.get("token_probability"),
        avg_token_probability=final_match.get("avg_token_probability"),
        token_probability_count=final_match.get("token_probability_count"),
        token_probability_available=bool(final_match.get("token_probability_available")),
        first_pass=first,
        second_pass=second_pass,
        final_decision_source=fusion["final_decision_source"],
        result_conflict=fusion["result_conflict"],
        manual_review_required=fusion["manual_review_required"],
        auto_flow_stopped=fusion["auto_flow_stopped"],
        manual_review_reason=fusion["manual_review_reason"],
        review_trace=review_trace,
        metrics=metrics,
    )


def _run_llm_match(ticket_task_text: str, video_evidence_text: str) -> dict[str, Any]:
    messages = _build_messages(ticket_task_text, video_evidence_text)
    llm = call_chat_with_logprobs(messages, temperature=0.0, timeout=90, top_logprobs=1, seed=42)
    if not llm.get("ok"):
        return llm
    parsed = _extract_json_object(llm.get("content", ""))
    probability_count = int(llm.get("token_probability_count") or 0)
    return {
        "ok": True,
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "content": llm.get("content", ""),
        "parsed": parsed,
        "token_probability": _safe_float(llm.get("min_token_probability"), 0.0),
        "avg_token_probability": _safe_float(llm.get("avg_token_probability"), 0.0),
        "token_probability_count": probability_count,
        "token_probability_available": probability_count > 0,
    }


def _run_second_pass(
    ticket_task_text: str,
    original_video_evidence_text: str,
    first_result: dict[str, Any],
    first_match: dict[str, Any],
    thresholds: dict[str, Any],
    trigger_reasons: list[str],
) -> dict[str, Any]:
    review = _run_video_evidence_review(ticket_task_text, original_video_evidence_text, first_result)
    second_pass: dict[str, Any] = {
        "triggered": True,
        "trigger_reason": "、".join(trigger_reasons),
        "trigger_reasons": trigger_reasons,
        "first_token_probability": first_match.get("token_probability"),
        "first_avg_token_probability": first_match.get("avg_token_probability"),
        "first_token_probability_count": first_match.get("token_probability_count"),
        "thresholds": thresholds,
        "review": review,
    }
    if not review.get("ok"):
        second_pass["success"] = False
        second_pass["reason"] = review.get("error", "二次视频证据复核失败。")
        return second_pass
    revised_text = (review.get("revised_video_evidence_text") or "").strip()
    if not revised_text:
        second_pass["success"] = False
        second_pass["reason"] = "二次视频证据复核未返回 revised_video_evidence_text。"
        return second_pass
    second_match = _run_llm_match(ticket_task_text, revised_text)
    second_pass["second_match"] = second_match
    second_pass["success"] = bool(second_match.get("ok") and second_match.get("parsed"))
    second_pass["reason"] = "已完成二次视频证据复核和第二次匹配。" if second_pass["success"] else "第二次匹配失败或返回不可解析 JSON。"
    return second_pass


def _run_video_evidence_review(ticket_task_text: str, video_evidence_text: str, first_result: dict[str, Any]) -> dict[str, Any]:
    suspicions = _review_suspicions(first_result)
    messages = [
        {
            "role": "system",
            "content": (
                "你是视频证据链二次复核智能体。你不会做最终违规裁决，只负责核验首轮 unmatched_work 疑点。"
                "不要全量重排视频证据链，不要引入无关维度，不要判断时间、地点、安全措施。"
                "必须输出严格 JSON，不要 Markdown。JSON 字段包含："
                "revised_video_evidence_text、focus_points、verified_suspicions、rejected_suspicions、remaining_uncertainties。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请只围绕首轮疑点做二次视频证据文本整理。\n\n"
                "【作业票任务文本】\n"
                f"{ticket_task_text}\n\n"
                "【需要核验的首轮疑点】\n"
                f"{json.dumps(suspicions, ensure_ascii=False)}\n\n"
                "【原始视频证据链文本，仅作为核验依据】\n"
                f"{video_evidence_text}\n\n"
                "请输出 JSON，其中 revised_video_evidence_text 要面向再次匹配，"
                "只包含与上述疑点相关的现场动作、对象、证据帧和不确定点。"
            ),
        },
    ]
    llm = call_chat(messages, temperature=0.0, timeout=90)
    if not llm.get("ok"):
        return {"ok": False, "error": llm.get("error", "视频证据链复核模型调用失败。")}
    parsed = _extract_json_object(llm.get("content", ""))
    if not parsed:
        return {"ok": False, "error": "视频证据链复核返回内容不是可解析 JSON。", "raw_excerpt": (llm.get("content") or "")[:500]}
    revised = str(parsed.get("revised_video_evidence_text") or "").strip()
    return {
        "ok": True,
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "revised_video_evidence_text": revised,
        "focus_points": parsed.get("focus_points") if isinstance(parsed.get("focus_points"), list) else [],
        "verified_suspicions": parsed.get("verified_suspicions") if isinstance(parsed.get("verified_suspicions"), list) else [],
        "rejected_suspicions": parsed.get("rejected_suspicions") if isinstance(parsed.get("rejected_suspicions"), list) else [],
        "remaining_uncertainties": parsed.get("remaining_uncertainties") if isinstance(parsed.get("remaining_uncertainties"), list) else [],
    }


def _dynamic_thresholds(risk_level: str | None, default_min_threshold: float) -> dict[str, Any]:
    normalized = _normalize_risk_level(risk_level)
    if normalized == "高危":
        min_threshold = max(_safe_float(default_min_threshold, 0.35), 0.45)
        avg_threshold = 0.7
    else:
        min_threshold = _safe_float(default_min_threshold, 0.35)
        avg_threshold = 0.6
    return {
        "risk_level": normalized,
        "min": round(min_threshold, 4),
        "avg": round(avg_threshold, 4),
    }


def _normalize_risk_level(risk_level: str | None) -> str:
    text = str(risk_level or "").strip()
    if not text:
        return "常规"
    high_markers = ["高危", "高风险", "重大", "一级", "高"]
    return "高危" if any(marker in text for marker in high_markers) else "常规"


def _should_trigger_second_pass(
    first_result: dict[str, Any],
    first_match: dict[str, Any],
    thresholds: dict[str, Any],
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {"triggered": False, "trigger_reasons": [], "reason": "调用方关闭了二次视频复核。"}

    reasons: list[str] = []
    if first_match.get("token_probability_available"):
        min_probability = _safe_float(first_match.get("token_probability"), 0.0)
        avg_probability = _safe_float(first_match.get("avg_token_probability"), 0.0)
        if min_probability < _safe_float(thresholds.get("min"), 0.35):
            reasons.append("min_token_probability_below_threshold")
        if avg_probability < _safe_float(thresholds.get("avg"), 0.6):
            reasons.append("avg_token_probability_below_threshold")

    if first_result.get("need_second_video_reasoning") or first_result.get("match_result") in {"需持续观察", "疑似不一致"}:
        reasons.append("model_marked_suspicious")

    if reasons:
        return {
            "triggered": True,
            "trigger_reasons": reasons,
            "reason": "触发二次复核：" + "、".join(reasons),
        }
    if not first_match.get("token_probability_available"):
        return {
            "triggered": False,
            "trigger_reasons": [],
            "reason": "模型未返回 logprobs，且首轮结果未标记存疑，不触发二次复核。",
        }
    return {
        "triggered": False,
        "trigger_reasons": [],
        "reason": "首轮最小/平均 token 概率均达标，且模型未标记存疑。",
    }


def _review_suspicions(first_result: dict[str, Any]) -> list[dict[str, Any]]:
    unmatched = first_result.get("unmatched_work") if isinstance(first_result.get("unmatched_work"), list) else []
    suspicions = [item for item in unmatched if isinstance(item, dict)]
    if suspicions:
        return suspicions
    return [
        {
            "ticket_side": "首轮未给出具体 unmatched_work",
            "video_side": first_result.get("match_result") or "需持续观察",
            "evidence": first_result.get("reason") or "首轮结果标记需要二次视频理解。",
            "confidence": 0.5,
        }
    ]


def _fuse_results(
    first_result: dict[str, Any],
    second_result: dict[str, Any] | None,
    first_match: dict[str, Any],
    second_match: dict[str, Any] | None,
    second_pass: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    if not second_pass.get("triggered"):
        return {
            "result": first_result,
            "final_match": first_match,
            "final_decision_source": "first_pass",
            "result_conflict": False,
            "manual_review_required": False,
            "auto_flow_stopped": False,
            "manual_review_reason": "",
        }

    if not second_result or not second_match:
        return {
            "result": first_result,
            "final_match": first_match,
            "final_decision_source": "second_pass_failed",
            "result_conflict": False,
            "manual_review_required": True,
            "auto_flow_stopped": True,
            "manual_review_reason": "二次复核触发后未形成有效第二轮匹配结果，自动流程终止并转人工审核。",
        }

    conflict = first_result.get("match_result") != second_result.get("match_result")
    second_low_confidence = _match_confidence_low(second_match, thresholds)
    second_still_doubtful = _result_still_doubtful(second_result)
    if not conflict:
        manual_review = second_low_confidence or second_still_doubtful
        return {
            "result": second_result,
            "final_match": second_match,
            "final_decision_source": "second_pass_confirmed",
            "result_conflict": False,
            "manual_review_required": manual_review,
            "auto_flow_stopped": manual_review,
            "manual_review_reason": "二次复核后仍存在低置信或存疑标记，转人工审核。" if manual_review else "",
        }

    review = second_pass.get("review") if isinstance(second_pass.get("review"), dict) else {}
    rejected_suspicions = review.get("rejected_suspicions") if isinstance(review.get("rejected_suspicions"), list) else []
    remaining_uncertainties = review.get("remaining_uncertainties") if isinstance(review.get("remaining_uncertainties"), list) else []
    second_can_correct = (
        bool(rejected_suspicions)
        and not remaining_uncertainties
        and not second_low_confidence
        and not second_still_doubtful
    )
    if second_can_correct:
        return {
            "result": second_result,
            "final_match": second_match,
            "final_decision_source": "second_pass_corrected",
            "result_conflict": True,
            "manual_review_required": False,
            "auto_flow_stopped": False,
            "manual_review_reason": "",
        }

    conservative = _conservative_conflict_result(first_result, second_result)
    return {
        "result": conservative,
        "final_match": second_match if _severity(second_result) >= _severity(first_result) else first_match,
        "final_decision_source": "conflict_requires_manual_review",
        "result_conflict": True,
        "manual_review_required": True,
        "auto_flow_stopped": True,
        "manual_review_reason": "两轮匹配结论冲突，且二次复核未能高置信排除首轮疑点，自动流程终止并转人工审核。",
    }


def _result_still_doubtful(result: dict[str, Any]) -> bool:
    return bool(result.get("need_second_video_reasoning")) or result.get("match_result") in {"需持续观察", "疑似不一致"}


def _match_confidence_low(match: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    if not match.get("token_probability_available"):
        return False
    min_probability = _safe_float(match.get("token_probability"), 0.0)
    avg_probability = _safe_float(match.get("avg_token_probability"), 0.0)
    return min_probability < _safe_float(thresholds.get("min"), 0.35) or avg_probability < _safe_float(thresholds.get("avg"), 0.6)


def _conservative_conflict_result(first_result: dict[str, Any], second_result: dict[str, Any]) -> dict[str, Any]:
    chosen = second_result if _severity(second_result) >= _severity(first_result) else first_result
    merged = dict(chosen)
    merged["need_second_video_reasoning"] = True
    merged["reason"] = (
        "两轮自动匹配结论存在冲突，已保留更保守的风险结论并转人工审核。"
        f"首轮结论：{first_result.get('match_result')}；二轮结论：{second_result.get('match_result')}。"
        f"保守结论原因：{chosen.get('reason') or '无'}"
    )
    return _normalize_result(merged)


def _severity(result: dict[str, Any] | None) -> int:
    if not result:
        return -1
    order = {"未发现明显异常": 0, "需持续观察": 1, "疑似不一致": 2, "明显不一致": 3}
    return order.get(str(result.get("match_result") or ""), 1)


def _build_review_trace(
    first_match: dict[str, Any],
    second_match: dict[str, Any] | None,
    second_pass: dict[str, Any],
    fusion: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    return {
        "review_triggered": bool(second_pass.get("triggered")),
        "trigger_reasons": second_pass.get("trigger_reasons") if isinstance(second_pass.get("trigger_reasons"), list) else [],
        "thresholds": thresholds,
        "first_probability": _probability_snapshot(first_match),
        "second_probability": _probability_snapshot(second_match) if second_match else None,
        "review_success": bool(second_pass.get("success")) if second_pass.get("triggered") else False,
        "result_conflict": bool(fusion.get("result_conflict")),
        "final_decision_source": fusion.get("final_decision_source"),
        "manual_review_required": bool(fusion.get("manual_review_required")),
        "manual_review_reason": fusion.get("manual_review_reason") or "",
    }


def _probability_snapshot(match: dict[str, Any] | None) -> dict[str, Any] | None:
    if not match:
        return None
    return {
        "available": bool(match.get("token_probability_available")),
        "min": match.get("token_probability"),
        "avg": match.get("avg_token_probability"),
        "count": match.get("token_probability_count"),
    }


def _review_metrics(second_pass: dict[str, Any], fusion: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_triggered": bool(second_pass.get("triggered")),
        "review_success": bool(second_pass.get("success")) if second_pass.get("triggered") else False,
        "review_trigger_reason_count": len(second_pass.get("trigger_reasons") or []),
        "result_conflict": bool(fusion.get("result_conflict")),
        "manual_review_required": bool(fusion.get("manual_review_required")),
        "auto_flow_stopped": bool(fusion.get("auto_flow_stopped")),
    }


def _build_messages(ticket_task_text: str, video_evidence_text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": get_agent_prompt("violation_detection_agent"),
        },
        {
            "role": "user",
            "content": (
                "请完成作业内容匹配判别。\n\n"
                "【作业票允许/计划的工作内容】\n"
                f"{ticket_task_text}\n\n"
                "【视频证据链文本】\n"
                f"{video_evidence_text}\n\n"
                "请只输出 JSON。"
            ),
        },
    ]


def _extract_json_object(content: str) -> dict[str, Any] | None:
    cleaned = (content or "").strip()
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


def _normalize_result(value: dict[str, Any]) -> dict[str, Any]:
    match_result = str(value.get("match_result") or "需持续观察").strip()
    if match_result not in MATCH_RESULT_VALUES:
        match_result = "需持续观察"
    try:
        task_match_score = float(value.get("task_match_score", 0.5))
    except Exception:
        task_match_score = 0.5
    task_match_score = max(0.0, min(1.0, task_match_score))
    matched_work = value.get("matched_work") if isinstance(value.get("matched_work"), list) else []
    unmatched_work = value.get("unmatched_work") if isinstance(value.get("unmatched_work"), list) else []
    normalized_unmatched = []
    for item in unmatched_work:
        if isinstance(item, dict):
            normalized_unmatched.append(
                {
                    "ticket_side": str(item.get("ticket_side") or ""),
                    "video_side": str(item.get("video_side") or ""),
                    "evidence": str(item.get("evidence") or ""),
                    "confidence": _safe_float(item.get("confidence"), 0.5),
                }
            )
        elif item:
            normalized_unmatched.append({"ticket_side": "", "video_side": str(item), "evidence": str(item), "confidence": 0.5})
    return {
        "match_result": match_result,
        "task_match_score": round(task_match_score, 4),
        "matched_work": [str(item) for item in matched_work if item],
        "unmatched_work": normalized_unmatched,
        "need_second_video_reasoning": _safe_bool(value.get("need_second_video_reasoning")),
        "reason": str(value.get("reason") or ""),
    }


def _rule_based_match(ticket_task_text: str, video_evidence_text: str) -> dict[str, Any]:
    task_items = _extract_work_items(ticket_task_text)
    evidence_items = _extract_work_items(video_evidence_text)
    matched = [item for item in task_items if item and item in video_evidence_text]
    unexpected = [item for item in evidence_items if item and item not in ticket_task_text]
    if not task_items and not evidence_items:
        score = 0.0
    elif not task_items:
        score = 0.25
    else:
        score = len(matched) / max(len(task_items), 1)
        if unexpected:
            score = max(0.0, score - min(0.35, 0.12 * len(unexpected)))

    if unexpected and score < 0.5:
        match_result = "明显不一致"
    elif unexpected:
        match_result = "疑似不一致"
    elif score >= 0.8:
        match_result = "未发现明显异常"
    elif score >= 0.4:
        match_result = "需持续观察"
    else:
        match_result = "疑似不一致"

    unmatched_work = [
        {
            "ticket_side": "作业票任务文本中未明确该现场作业内容",
            "video_side": item,
            "evidence": f"视频证据链文本中出现“{item}”。",
            "confidence": 0.55,
        }
        for item in unexpected
    ]
    need_second = match_result in {"疑似不一致", "明显不一致"} or score < 0.65
    reason = _rule_reason(match_result, matched, unexpected, score)
    return {
        "match_result": match_result,
        "task_match_score": round(score, 4),
        "matched_work": matched,
        "unmatched_work": unmatched_work,
        "need_second_video_reasoning": need_second,
        "reason": reason,
    }


def _extract_work_items(text: str) -> list[str]:
    found: list[str] = []
    for keyword in WORK_KEYWORDS:
        if keyword in text and keyword not in found:
            found.append(keyword)
    if found:
        return found
    pieces = [piece.strip(" ，,。；;、\n\t") for piece in re.split(r"[，,。；;、\n]+", text or "")]
    return [piece for piece in pieces if 2 <= len(piece) <= 24][:12]


def _rule_reason(match_result: str, matched: list[str], unexpected: list[str], score: float) -> str:
    if unexpected:
        return (
            f"作业内容匹配结果为{match_result}，匹配分数{score:.2f}。"
            f"已匹配内容：{'、'.join(matched) or '无'}；"
            f"视频证据链出现票面未明确内容：{'、'.join(unexpected)}。建议对相关帧进行二次视频理解。"
        )
    return f"作业内容匹配结果为{match_result}，匹配分数{score:.2f}。已匹配内容：{'、'.join(matched) or '无明显关键词匹配'}。"


def _safe_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return round(max(0.0, min(1.0, parsed)), 4)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "是", "需要", "需"}
    return bool(value)


def _wrap_result(
    match_id: str,
    ticket_id: str | None,
    result: dict[str, Any],
    provider: str,
    model: str,
    llm_used: bool,
    probability_threshold: float,
    probability_thresholds: dict[str, Any] | None = None,
    risk_level: str = "常规",
    token_probability: float | None = None,
    avg_token_probability: float | None = None,
    token_probability_count: int | None = None,
    token_probability_available: bool = False,
    first_pass: dict[str, Any] | None = None,
    second_pass: dict[str, Any] | None = None,
    final_decision_source: str = "first_pass",
    result_conflict: bool = False,
    manual_review_required: bool = False,
    auto_flow_stopped: bool = False,
    manual_review_reason: str = "",
    review_trace: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    llm_error: str = "",
    llm_raw_excerpt: str = "",
) -> dict[str, Any]:
    first_pass_summary = _pass_summary(first_pass) if first_pass else None
    if probability_thresholds is None:
        probability_thresholds = {"risk_level": risk_level, "min": probability_threshold, "avg": 0.6}
    payload = {
        "success": True,
        "match_id": match_id,
        "ticket_id": ticket_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": provider,
        "model": model,
        "llm_used": llm_used,
        "risk_level": risk_level,
        "token_probability": token_probability,
        "avg_token_probability": avg_token_probability,
        "token_probability_count": token_probability_count,
        "token_probability_available": token_probability_available,
        "probability_threshold": probability_threshold,
        "probability_thresholds": probability_thresholds,
        "result": _normalize_result(result),
        "first_pass": first_pass_summary,
        "second_pass": _sanitize_second_pass(second_pass or {"triggered": False}),
        "final_decision_source": final_decision_source,
        "result_conflict": result_conflict,
        "manual_review_required": manual_review_required,
        "auto_flow_stopped": auto_flow_stopped,
        "manual_review_reason": manual_review_reason,
        "review_trace": review_trace or {},
        "metrics": metrics or {},
    }
    if llm_error:
        payload["llm_error"] = llm_error
    if llm_raw_excerpt:
        payload["llm_raw_excerpt"] = llm_raw_excerpt
    return payload


def _pass_summary(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": match.get("provider"),
        "model": match.get("model"),
        "token_probability": match.get("token_probability"),
        "avg_token_probability": match.get("avg_token_probability"),
        "token_probability_count": match.get("token_probability_count"),
        "token_probability_available": bool(match.get("token_probability_available")),
        "result": _normalize_result(match.get("parsed") or {}) if match.get("parsed") else None,
    }


def _sanitize_second_pass(second_pass: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(second_pass)
    second_match = cleaned.get("second_match")
    if isinstance(second_match, dict):
        cleaned["second_match"] = _pass_summary(second_match)
    return cleaned


def _error(match_id: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "match_id": match_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": message,
    }
