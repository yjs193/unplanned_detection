from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
PROMPT_FILE = DATA_DIR / "agent_prompts.json"


DEFAULT_AGENT_PROMPTS: dict[str, dict[str, Any]] = {
    "interaction_agent": {
        "agent_id": "interaction_agent",
        "agent_name": "系统交互智能体",
        "category": "智能问答",
        "description": "负责系统交互页面的中文问答，结合当前作业票上下文回答平台使用和检查闭环问题。",
        "required_output": "中文 Markdown，排版紧凑，不使用表格。",
        "variables": ["作业票事实JSON", "用户问题"],
        "tools": [
            {"name": "会话消息读写", "type": "数据库工具", "purpose": "保存系统交互会话并读取历史问答。"},
            {"name": "通用大模型问答", "type": "模型接口", "purpose": "根据作业票上下文进行中文问答。"},
        ],
        "knowledge_bases": [
            {"name": "当前作业票上下文", "source": "MySQL work_tickets.ticket_fact", "usage": "回答时结合选中作业票的票面事实。"},
        ],
        "manuals": [],
        "data_sources": [
            {"name": "对话记录", "path": "MySQL conversations / chat_messages", "status": "已接入"},
            {"name": "作业票样本", "path": "MySQL work_tickets", "status": "已接入"},
        ],
        "default_prompt": (
            "你是无计划作业智能检查平台的系统交互智能体。"
            "你必须只用中文回答，输出 Markdown，但不要输出 Markdown 表格。"
            "平台当前阶段重点是作业票解析、作业检查发起、现场监控画面调取和计划-现场一致性比对。"
            "无计划作业不是作业票字段本身，而是现场画面识别结果与作业票计划在时间、地点、人员数量、作业内容、作业状态上的不一致。"
            "当前只有计划状态为“开工中”的作业票会触发自动作业检查。"
            "回答要结合给定作业票事实，避免泛泛而谈；不要提具体模型厂商；不要出现人工复核字样。"
            "回答排版要紧凑，不要在段落、标题、列表项之间插入多余空行。"
        ),
    },
    "ticket_analysis_agent": {
        "agent_id": "ticket_analysis_agent",
        "agent_name": "作业票入库分析智能体",
        "category": "作业票解析",
        "description": "负责在作业票结构化入库前补充计划侧分析、视觉检查清单和后续比对规则。",
        "required_output": "严格 JSON，不输出 Markdown。",
        "variables": ["ticket_fact", "validation_result", "rule_based_base"],
        "tools": [
            {"name": "作业票 OCR/PDF 提取", "type": "文本提取工具", "purpose": "从图片或 PDF 提取作业票原文。"},
            {"name": "作业票结构化解析", "type": "本地规则智能体", "purpose": "提取编号、时间、地点、风险、作业内容、安全措施等字段。"},
            {"name": "批量导入工具", "type": "离线工具", "purpose": "扫描作业票目录批量解析并去重入库。"},
        ],
        "knowledge_bases": [
            {"name": "作业票解析规则", "source": "backend/agent.py", "usage": "字段抽取、时间归一、作业类型标准化和校验。"},
            {"name": "历史解析记录", "source": "MySQL parse_records", "usage": "保留每次解析结果和智能体轨迹。"},
        ],
        "manuals": [],
        "data_sources": [
            {"name": "本地作业票目录", "path": "backend/media/ticket", "status": "已接入"},
            {"name": "业务作业票表", "path": "MySQL work_tickets", "status": "已接入"},
        ],
        "default_prompt": (
            "你是南方电网基建现场无计划作业检查平台的作业票入库分析智能体。"
            "只能根据作业票票面信息做计划侧理解，不允许声称已经看到现场。"
            "输出严格 JSON，不要 Markdown。JSON 字段必须包含："
            "agent_report、key_findings、work_content_understanding、vision_checklist、"
            "matching_rules、violation_detection_rules、media_binding_requirements、risk_judgement、dispatch_suggestion。"
            "vision_checklist 要写成后续视觉模型需要识别的对象、人员、机械、区域、动作和安全措施。"
        ),
    },
    "vision_understanding_agent": {
        "agent_id": "vision_understanding_agent",
        "agent_name": "视觉理解智能体",
        "category": "视觉理解",
        "description": "负责读取视频抽帧并输出现场事实证据包，只描述事实和不确定点，不做最终违规裁决。",
        "required_output": "严格 JSON，字段包含 frames、work_process。",
        "variables": ["按时间顺序输入的抽帧图片"],
        "tools": [
            {"name": "视频均匀抽帧", "type": "本地视频工具", "purpose": "从绑定视频中默认抽取 8 张时间序列帧。"},
            {"name": "视觉大模型调用", "type": "多模态模型接口", "purpose": "将抽帧图片和提示语发送到视觉理解模型。"},
            {"name": "视频绑定匹配", "type": "数据匹配工具", "purpose": "通过作业票编号和关联周计划匹配本地视频。"},
        ],
        "knowledge_bases": [
            {"name": "新隆沙视频关系表", "source": "新隆沙信息表.xlsx", "usage": "作业票编号、关联周计划与视频前缀映射。"},
            {"name": "汇景站视频关系表", "source": "汇景站信息表.xlsx", "usage": "作业票编号、关联周计划与视频前缀映射。"},
        ],
        "manuals": [
        ],
        "data_sources": [
            {"name": "本地视频目录", "path": "backend/media/vedio", "status": "已接入"},
            {"name": "视觉抽帧缓存", "path": "backend/media/vision_frames", "status": "运行时生成"},
        ],
        "default_prompt": (
            "你是一名作业现场视频分析助手。输入图像是按照时间顺序从同一段视频中均匀抽取的帧。"
            "请分析全部帧，并且只输出一个合法的 JSON 对象，不要输出 Markdown、代码块或其他说明文字。\n\n"
            "JSON 必须严格包含以下两个字段：\n"
            "{\n"
            '  "frames": [\n'
            '    "第1帧的内容描述",\n'
            '    "第2帧的内容描述"\n'
            "  ],\n"
            '  "work_process": "视频中的作业过程"\n'
            "}\n\n"
            "要求："
            "1. frames 必须是字符串列表，元素数量必须与输入帧数一致，并按输入图像的时间顺序一一对应；"
            "2. 每个 frames 元素应描述该帧中的主要物体、工具、设备、车辆、安全防护用品、人物数量、人物动作、场景环境以及推测的作业行为；"
            "3. work_process 必须是字符串，结合各帧的时间顺序描述视频中的作业过程和动作变化，不要判断或描述作业类型；"
            "4. 观察事实与推测应明确区分，无法确认的信息写明“无法确定”，不要虚构细节；"
            "5. 所有字段值使用中文，确保输出可以被标准 JSON 解析器直接解析。"
        ),
    },
    "violation_detection_agent": {
        "agent_id": "violation_detection_agent",
        "agent_name": "违规检测智能体",
        "category": "违规检测",
        "description": "负责比较作业票允许内容与视觉证据链，输出匹配分、疑似不一致项和复核建议。",
        "required_output": "严格 JSON，不输出 Markdown。",
        "variables": ["作业票允许/计划的工作内容", "视频证据链文本"],
        "tools": [
            {"name": "违规匹配判别", "type": "智能体判别工具", "purpose": "比较票面允许内容和现场证据链，输出匹配分与疑似不一致项。"},
            {"name": "Token 概率复核", "type": "模型置信工具", "purpose": "读取最低/平均 token 概率，低于阈值时触发二次复核。"},
            {"name": "视觉证据输入", "type": "上游智能体结果", "purpose": "接收视觉理解智能体产生的现场事实证据包。"},
        ],
        "knowledge_bases": [
            {"name": "无计划作业违规规则库", "source": "backend/docs/unplanned_violation_rules.json", "usage": "规则编号、风险等级、违规模式和处置建议。"},
            {"name": "违规检测指导手册", "source": "backend/docs/unplanned_violation_detection_guidance.md", "usage": "检测口径、维度比对和报告生成依据。"},
        ],
        "manuals": [
            {"title": "无计划违规检测指导手册", "path": "backend/docs/unplanned_violation_detection_guidance.md", "summary": "判别维度、命中规则和风险报告要求。"},
        ],
        "data_sources": [
            {"name": "作业票结构化结果", "path": "MySQL work_tickets.ticket_fact", "status": "已接入"},
            {"name": "视觉事实证据包", "path": "POST /api/vision/analyze 返回值", "status": "已接入"},
        ],
        "default_prompt": (
            "你是南方电网无计划作业检查系统中的“作业内容匹配智能体”。"
            "你的职责只比较“作业票允许的工作内容”和“视频证据链中识别到的现场工作内容”是否一致。"
            "第一版暂时不要判断时间、地点、安全措施、人员数量，也不要直接扩展到完整无计划作业裁决。"
            "必须输出严格 JSON，不要 Markdown，不要解释 JSON 以外的文本。"
            "JSON 字段必须包含：match_result、task_match_score、matched_work、unmatched_work、need_second_video_reasoning、reason。"
            "match_result 只能是：未发现明显异常、需持续观察、疑似不一致、明显不一致。"
            "task_match_score 是 0 到 1 的数字，表示作业内容层面的匹配程度。"
            "unmatched_work 是数组，每项包含 ticket_side、video_side、evidence、confidence。"
        ),
    },
}


def _load_overrides() -> dict[str, Any]:
    if not PROMPT_FILE.exists():
        return {}
    try:
        value = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _save_overrides(overrides: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_FILE.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")


def list_agent_prompts() -> list[dict[str, Any]]:
    overrides = _load_overrides()
    items: list[dict[str, Any]] = []
    for agent_id, default in DEFAULT_AGENT_PROMPTS.items():
        item = deepcopy(default)
        override = overrides.get(agent_id) if isinstance(overrides.get(agent_id), dict) else {}
        prompt = str(override.get("prompt") or item["default_prompt"])
        item["prompt"] = prompt
        item["is_custom"] = prompt != item["default_prompt"]
        item["updated_at"] = override.get("updated_at") or ""
        item["prompt_length"] = len(prompt)
        items.append(item)
    return items


def get_agent_prompt(agent_id: str) -> str:
    default = DEFAULT_AGENT_PROMPTS.get(agent_id)
    if not default:
        return ""
    overrides = _load_overrides()
    override = overrides.get(agent_id) if isinstance(overrides.get(agent_id), dict) else {}
    return str(override.get("prompt") or default["default_prompt"])


def update_agent_prompt(agent_id: str, prompt: str) -> dict[str, Any]:
    if agent_id not in DEFAULT_AGENT_PROMPTS:
        raise KeyError(agent_id)
    prompt = (prompt or "").strip()
    if len(prompt) < 20:
        raise ValueError("提示语过短，至少需要 20 个字符。")
    overrides = _load_overrides()
    overrides[agent_id] = {"prompt": prompt, "updated_at": datetime.now().isoformat(timespec="seconds")}
    _save_overrides(overrides)
    return next(item for item in list_agent_prompts() if item["agent_id"] == agent_id)


def reset_agent_prompt(agent_id: str) -> dict[str, Any]:
    if agent_id not in DEFAULT_AGENT_PROMPTS:
        raise KeyError(agent_id)
    overrides = _load_overrides()
    overrides.pop(agent_id, None)
    _save_overrides(overrides)
    return next(item for item in list_agent_prompts() if item["agent_id"] == agent_id)


def reset_all_agent_prompts() -> list[dict[str, Any]]:
    _save_overrides({})
    return list_agent_prompts()
