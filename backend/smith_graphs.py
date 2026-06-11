from __future__ import annotations

from typing import Any, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = None
    StateGraph = None

from .db import get_ticket
from .agent import parse_ticket
from .matching_agent import build_ticket_task_text, run_task_video_matching


class ViolationDetectionState(TypedDict, total=False):
    ticket_id: str
    ticket_task_text: str
    video_evidence_text: str
    risk_level: str
    probability_threshold: float
    enable_second_video_reasoning: bool
    ticket_summary: dict[str, Any]
    result: dict[str, Any]
    error: str


def prepare_violation_input(state: ViolationDetectionState) -> ViolationDetectionState:
    ticket_id = (state.get("ticket_id") or "").strip()
    task_text = (state.get("ticket_task_text") or "").strip()
    ticket = get_ticket(ticket_id) if ticket_id else None
    if not task_text and ticket:
        task_text = build_ticket_task_text(ticket.get("ticket_fact") or {}) or str(ticket.get("work_content_raw") or "").strip()
    if ticket:
        state["ticket_summary"] = {
            "id": ticket.get("id"),
            "plan_id": ticket.get("plan_id"),
            "project_name": ticket.get("project_name"),
            "work_location": ticket.get("work_location"),
            "risk_level": ticket.get("risk_level"),
            "plan_status": ticket.get("plan_status"),
        }
        if not state.get("risk_level"):
            state["risk_level"] = str(ticket.get("risk_level") or "")
    state["ticket_task_text"] = task_text
    return state


def run_violation_match(state: ViolationDetectionState) -> ViolationDetectionState:
    task_text = (state.get("ticket_task_text") or "").strip()
    evidence_text = (state.get("video_evidence_text") or "").strip()
    if not task_text:
        state["error"] = "缺少作业票任务文本：请传 ticket_task_text，或传 ticket_id 从数据库读取。"
        return state
    if not evidence_text:
        state["error"] = "缺少现场证据链文本：请传 video_evidence_text。"
        return state
    result = run_task_video_matching(
        ticket_task_text=task_text,
        video_evidence_text=evidence_text,
        ticket_id=state.get("ticket_id"),
        probability_threshold=float(state.get("probability_threshold") or 0.35),
        enable_second_video_reasoning=bool(state.get("enable_second_video_reasoning", True)),
        risk_level=state.get("risk_level"),
    )
    state["result"] = result
    state.pop("error", None)
    return state


def _build_violation_graph():
    if StateGraph is None:
        return None
    workflow = StateGraph(ViolationDetectionState)
    workflow.add_node("prepare_violation_input", prepare_violation_input)
    workflow.add_node("run_violation_match", run_violation_match)
    workflow.set_entry_point("prepare_violation_input")
    workflow.add_edge("prepare_violation_input", "run_violation_match")
    workflow.add_edge("run_violation_match", END)
    return workflow.compile()


VIOLATION_DETECTION_GRAPH = _build_violation_graph()


class InspectionWorkflowState(TypedDict, total=False):
    raw_text: str
    source_type: str
    ticket_id: str
    ticket_task_text: str
    ticket_fact: dict[str, Any]
    ticket_summary: dict[str, Any]
    video_evidence_text: str
    visual_evidence_package: dict[str, Any]
    visual_review_requested: bool
    visual_review_round: int
    risk_level: str
    probability_threshold: float
    enable_second_video_reasoning: bool
    violation_result: dict[str, Any]
    error: str


def _workflow_ticket_text(fact: dict[str, Any], fallback: str = "") -> str:
    return build_ticket_task_text(fact) or fallback.strip()


def parse_work_ticket_for_workflow(state: InspectionWorkflowState) -> InspectionWorkflowState:
    raw_text = (state.get("raw_text") or "").strip()
    ticket_id = (state.get("ticket_id") or "").strip()
    if raw_text:
        parsed = parse_ticket(raw_text, source_type=state.get("source_type") or "smith_workflow")
        fact = parsed.get("ticket_fact") or {}
        state["ticket_fact"] = fact
        state["ticket_task_text"] = _workflow_ticket_text(fact)
    elif ticket_id:
        ticket = get_ticket(ticket_id)
        if not ticket:
            state["error"] = f"未找到作业票：{ticket_id}"
            return state
        fact = ticket.get("ticket_fact") or {}
        state["ticket_fact"] = fact
        state["ticket_task_text"] = _workflow_ticket_text(fact, str(ticket.get("work_content_raw") or ""))
        state["ticket_summary"] = {
            "id": ticket.get("id"),
            "plan_id": ticket.get("plan_id"),
            "project_name": ticket.get("project_name"),
            "work_location": ticket.get("work_location"),
            "risk_level": ticket.get("risk_level"),
            "plan_status": ticket.get("plan_status"),
        }
        if not state.get("risk_level"):
            state["risk_level"] = str(ticket.get("risk_level") or "")
    elif state.get("ticket_task_text"):
        state["ticket_fact"] = {"work_content_raw": state.get("ticket_task_text")}
    else:
        state["error"] = "缺少作业票输入：请传 raw_text、ticket_id 或 ticket_task_text。"
    return state


def visual_understanding_for_workflow(state: InspectionWorkflowState) -> InspectionWorkflowState:
    if state.get("error"):
        return state
    fact = state.get("ticket_fact") or {}
    location = fact.get("work_location") or (state.get("ticket_summary") or {}).get("work_location") or "作业票绑定区域"
    actions = fact.get("work_actions") if isinstance(fact.get("work_actions"), list) else []
    if not actions:
        raw = str(fact.get("work_content_raw") or state.get("ticket_task_text") or "")
        actions = [item.strip() for item in raw.replace("；", "、").replace("，", "、").split("、") if item.strip()][:4]
    if not actions:
        actions = ["现场围蔽检查", "材料转运", "基础施工作业"]

    review_round = int(state.get("visual_review_round") or 0)
    review_requested = bool(state.get("visual_review_requested"))
    base_text = (state.get("video_evidence_text") or "").strip()
    if base_text and not review_requested:
        evidence_text = base_text
    else:
        prefix = "二次复核补充：" if review_requested else "初次视觉理解："
        lines = [
            f"{prefix}证据来源为近30分钟监控抽帧形成的现场事实证据包。",
            f"第01帧 作业区域位于{location}，现场可见施工围蔽和人员进场。",
            f"第08帧 现场识别到{'、'.join(actions[:4])}，与票面作业内容存在对应关系。",
            f"第16帧 作业对象集中在{location}，未见明显跨区域施工迹象。",
        ]
        if review_requested:
            lines.append("第18帧 复核重点为首轮疑点相关动作、设备对象和人员接近情况，需重新确认是否存在票面未授权作业。")
            review_round += 1
        evidence_text = "\n".join([base_text, *lines]).strip() if base_text else "\n".join(lines)

    state["video_evidence_text"] = evidence_text
    state["visual_evidence_package"] = {
        "source": "视觉理解智能体",
        "review_round": review_round,
        "work_location": location,
        "observed_actions": actions[:6],
        "evidence_text": evidence_text,
        "note": "当前为流程编排图中的视觉事实证据包；真实视觉模型接入后替换该节点输出。",
    }
    state["visual_review_round"] = review_round
    state["visual_review_requested"] = False
    return state


def violation_detection_for_workflow(state: InspectionWorkflowState) -> InspectionWorkflowState:
    if state.get("error"):
        return state
    task_text = (state.get("ticket_task_text") or "").strip()
    evidence_text = (state.get("video_evidence_text") or "").strip()
    if not task_text:
        state["error"] = "作业票解析后仍缺少任务文本，无法执行违规检测。"
        return state
    if not evidence_text:
        state["error"] = "视觉理解后仍缺少现场证据链，无法执行违规检测。"
        return state
    state["violation_result"] = run_task_video_matching(
        ticket_task_text=task_text,
        video_evidence_text=evidence_text,
        ticket_id=state.get("ticket_id"),
        probability_threshold=float(state.get("probability_threshold") or 0.35),
        enable_second_video_reasoning=bool(state.get("enable_second_video_reasoning", True)),
        risk_level=state.get("risk_level") or (state.get("ticket_fact") or {}).get("risk_level"),
    )
    result = state["violation_result"]
    inner = result.get("result") if isinstance(result.get("result"), dict) else {}
    second_pass = result.get("second_pass") if isinstance(result.get("second_pass"), dict) else {}
    state["visual_review_requested"] = bool(
        int(state.get("visual_review_round") or 0) < 1
        and (
            inner.get("need_second_video_reasoning")
            or second_pass.get("triggered")
            or result.get("manual_review_required")
        )
    )
    return state


def route_after_violation(state: InspectionWorkflowState) -> str:
    if state.get("visual_review_requested"):
        return "视觉理解智能体"
    return END


def _build_inspection_workflow_graph():
    if StateGraph is None:
        return None
    workflow = StateGraph(InspectionWorkflowState)
    workflow.add_node("作业票解析智能体", parse_work_ticket_for_workflow)
    workflow.add_node("视觉理解智能体", visual_understanding_for_workflow)
    workflow.add_node("违规检测智能体", violation_detection_for_workflow)
    workflow.set_entry_point("作业票解析智能体")
    workflow.add_edge("作业票解析智能体", "视觉理解智能体")
    workflow.add_edge("视觉理解智能体", "违规检测智能体")
    workflow.add_conditional_edges(
        "违规检测智能体",
        route_after_violation,
        {"视觉理解智能体": "视觉理解智能体", END: END},
    )
    return workflow.compile()


INSPECTION_WORKFLOW_GRAPH = _build_inspection_workflow_graph()
