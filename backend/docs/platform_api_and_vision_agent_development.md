# 无计划作业智能检查平台接口与视觉理解智能体开发文档

更新时间：2026-06-10

## 1. 服务入口

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端平台 | `<FRONTEND_URL>` | Vite 前端服务 |
| 接口文档页 | `<FRONTEND_URL>/docx` | 本文档线上页面 |
| 后端 API | `<BACKEND_API_URL>/api` | FastAPI 业务接口 |
| LangGraph 本地服务 | `<LANGGRAPH_URL>` | Smith/Studio 可通过 SSH 隧道访问 |
| LangGraph tunnel | `<LANGGRAPH_TUNNEL_URL>` | Cloudflare quick tunnel 运行端口 |

## 2. 后端 REST API 总览

### 基础与静态资源

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 服务健康检查 |
| GET | `/api/assets/logo/{name}` | 读取平台 logo |
| GET | `/api/media/site/{filename}` | 读取现场图片资源 |
| GET | `/api/media/pilot/{filename}` | 读取试点图片资源 |
| GET | `/api/media/pilot-frame/{filename}` | 读取试点抽帧资源 |

### 仪表盘与作业票

| 方法 | 路径 | 入参 | 返回 |
| --- | --- | --- | --- |
| GET | `/api/dashboard` | 无 | 统计数据、风险分布、近期作业票 |
| GET | `/api/work-tickets` | `page,page_size,status,keyword` | `{total, items}` |
| GET | `/api/work-tickets/samples` | 无 | `{samples}`，用于前端选择作业票 |
| GET | `/api/work-tickets/history` | 无 | 最近解析记录 |
| POST | `/api/work-tickets/parse` | `multipart/form-data`: `text,sample_id,file` | 作业票解析结果 |
| POST | `/api/work-tickets/parse/stream` | 同上 | SSE 流式解析进度 |
| POST | `/api/work-tickets/import` | `{record}` | 将解析结果入库 |

### 系统交互与检查

| 方法 | 路径 | 入参 | 用途 |
| --- | --- | --- | --- |
| POST | `/api/interaction/start-inspection` | `InspectionRequest` | 发起作业检查闭环 |
| GET | `/api/interaction/inspections` | 无 | 检查记录 |
| GET | `/api/interaction/llm-status` | 无 | 当前通用模型状态，当前为 Qwen |
| GET | `/api/interaction/conversations` | 无 | 对话列表 |
| GET | `/api/interaction/conversations/{conversation_id}/messages` | path | 对话消息 |
| POST | `/api/interaction/chat` | `ChatRequest` | 非流式智能问答 |
| POST | `/api/interaction/chat/stream` | `ChatRequest` | SSE 流式智能问答 |

### 试点与全流程检查

| 方法 | 路径 | 入参 | 用途 |
| --- | --- | --- | --- |
| GET | `/api/pilot/hj` | 无 | 合景试点状态 |
| POST | `/api/pilot/hj/run` | 无 | 运行合景试点闭环 |
| POST | `/api/inspection/run-full` | `FullInspectionRequest` | 作业票解析/入库/抽帧/视觉理解/违规检测闭环 |

### 违规检测

| 方法 | 路径 | 模型 | 用途 |
| --- | --- | --- | --- |
| POST | `/api/violation-detection/run` | Qwen `qwen-plus-latest` | 作业票任务文本与现场证据链一致性判别 |

请求体：

```json
{
  "ticket_id": "ticket_import_459c942591",
  "ticket_task_text": "可选；不传时从 ticket_id 查询作业票生成",
  "video_evidence_text": "现场证据链文本",
  "video_evidence_package": {},
  "probability_threshold": 0.35,
  "enable_second_video_reasoning": true,
  "risk_level": "高"
}
```

核心返回字段：

```json
{
  "success": true,
  "provider": "Qwen",
  "model": "qwen-plus-latest",
  "token_probability_available": true,
  "token_probability": 0.3034,
  "avg_token_probability": 0.9342,
  "result": {
    "match_result": "疑似不一致",
    "task_match_score": 0.35,
    "matched_work": [],
    "unmatched_work": [
      {
        "ticket_side": "作业票未明确吊装作业",
        "video_side": "现场出现构件吊装",
        "evidence": "第18帧出现构件吊装和大型机械配合作业",
        "confidence": 0.9
      }
    ],
    "need_second_video_reasoning": true,
    "reason": "..."
  },
  "second_pass": {
    "triggered": true,
    "trigger_reasons": ["model_marked_suspicious"]
  },
  "manual_review_required": true
}
```

### REST API 字段明细

#### GET `/api/health`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ok` | boolean | 是 | 服务是否正常 |
| `service` | string | 是 | 服务标识 |
| `time` | string | 是 | 服务器当前时间 ISO 字符串 |

#### GET `/api/assets/logo/{name}`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | path string | 否 | logo 名称，目前非法值自动回退为 `nfdw` |

输出字段：图片文件响应，`Content-Type` 为 `image/*`。

#### GET `/api/media/site/{filename}`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | path string | 是 | 现场图片文件名，只取安全文件名 |

输出字段：图片文件响应；文件不存在时回退到默认演示图片。

#### GET `/api/media/pilot/{filename}`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | path string | 是 | 合景试点图片文件名 |

输出字段：图片文件响应。

#### GET `/api/media/pilot-frame/{filename}`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `filename` | path string | 是 | 合景试点抽帧图片文件名 |

输出字段：图片文件响应。

#### GET `/api/dashboard`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stats.total_tickets` | number | 是 | 作业票总数 |
| `stats.active_tickets` | number | 是 | 开工中作业票数量 |
| `stats.pending_match_tickets` | number | 是 | 待匹配作业票数量 |
| `stats.high_risk_tickets` | number | 是 | 高风险作业票数量 |
| `stats.video_control_tickets` | number | 是 | 纳入视频管控数量 |
| `by_status` | array | 是 | 按计划状态统计，元素为 `{name,value}` |
| `by_risk` | array | 是 | 按风险等级统计，元素为 `{name,value}` |
| `by_district` | array | 是 | 按区域统计，元素为 `{name,value}` |
| `recent_tickets` | WorkTicket[] | 是 | 近期作业票 |

#### GET `/api/work-tickets`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | query integer | 否 | 页码，默认 1，最小 1 |
| `page_size` | query integer | 否 | 每页数量，默认 20，最大 100 |
| `status` | query string | 否 | 计划状态过滤，如 `开工中`、`待开工`、`已完工` |
| `keyword` | query string | 否 | 按编号、工程名、地点等关键字查询 |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `total` | number | 是 | 符合条件的总数 |
| `items` | WorkTicket[] | 是 | 作业票列表 |
| `items[].id` | string | 是 | 平台内部作业票 ID |
| `items[].plan_id` | string | 是 | 作业票编号 |
| `items[].ticket_fact` | TicketFact | 是 | 结构化票面事实，视觉理解 `ticket_context` 主要来源 |
| `items[].media_query_task` | object | 是 | 媒体调取任务，含候选摄像头和时间窗口 |

#### GET `/api/work-tickets/samples`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `samples` | SampleTicket[] | 是 | 前端选择器样本列表 |
| `samples[].id` | string | 是 | 样本 ID |
| `samples[].name` | string | 是 | 样本名称 |
| `samples[].source_type` | string | 是 | 来源类型 |
| `samples[].raw_text` | string | 是 | 作业票文本 |
| `samples[].ticket` | WorkTicket | 否 | 已入库作业票对象 |

#### GET `/api/work-tickets/history`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items` | ParseRecord[] | 是 | 最近 20 条解析记录 |

#### POST `/api/work-tickets/parse`

输入参数为 `multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `text` | form string | 否 | 作业票文本；上传文件时可为空 |
| `sample_id` | form string | 否 | 样本 ID |
| `file` | form File | 否 | PDF 或图片文件 |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 是否解析成功 |
| `record.id` | string | 是 | 解析记录 ID |
| `record.source_type` | string | 是 | 来源类型 |
| `record.summary` | string | 是 | 中文摘要 |
| `record.raw_text` | string | 是 | 提取或输入的原文 |
| `record.pdf_result` | object | 否 | PDF 文本提取结果 |
| `record.ocr_result` | object | 否 | OCR 提取结果 |
| `record.ticket_fact` | TicketFact | 是 | 作业票结构化结果 |
| `record.work_content_items` | string[] | 是 | 拆分后的作业内容 |
| `record.media_query_task` | object | 是 | 媒体调取任务 |
| `record.agent_analysis` | object | 否 | 作业票解析智能体分析结果 |

#### POST `/api/work-tickets/parse/stream`

输入参数同 `/api/work-tickets/parse`。

输出为 SSE：

| 事件 | 类型 | 说明 |
| --- | --- | --- |
| `type=step` | JSON | `{index,title,status}`，解析进度 |
| `type=final` | JSON | `{record}`，最终解析记录 |
| `type=error` | JSON | `{message}`，错误信息 |
| `type=done` | JSON | 流结束 |

#### POST `/api/work-tickets/import`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `record` | ParseRecord | 是 | 作业票解析记录 |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 接口是否处理成功 |
| `created` | boolean | 是 | 是否新建入库 |
| `ticket` | WorkTicket | 否 | 入库后的作业票 |
| `message` | string | 是 | 处理说明 |

#### POST `/api/interaction/start-inspection`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ticket_id` | string | 否 | 作业票内部 ID 或 `plan_id` |
| `ticket_fact` | TicketFact | 否 | 不传 `ticket_id` 时可直接传票面事实 |
| `media_query_task` | object | 否 | 媒体调取任务 |
| `operator` | string | 否 | 操作人，默认 `系统自动检查` |
| `mode` | string | 否 | 检查模式，默认 `manual` |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 是否发起成功 |
| `inspection` | InspectionRecord | 是 | 检查记录 |
| `result` | PilotWorkflowResult | 否 | 完整闭环结果 |

#### GET `/api/interaction/inspections`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items` | InspectionRecord[] | 是 | 最近 50 条检查记录 |

#### GET `/api/interaction/llm-status`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | 是 | 模型供应商 |
| `model` | string | 是 | 模型名称 |
| `available` | boolean | 是 | 是否配置可用 |
| `api_format` | string | 否 | 接口格式，如 `anthropic` 或 `openai` |

#### GET `/api/interaction/conversations`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items` | array | 是 | 会话列表 |
| `items[].id` | string | 是 | 会话 ID |
| `items[].title` | string | 是 | 会话标题 |
| `items[].ticket_id` | string | 否 | 关联作业票 ID |
| `items[].created_at` | string | 是 | 创建时间 |
| `items[].updated_at` | string | 是 | 更新时间 |

#### GET `/api/interaction/conversations/{conversation_id}/messages`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `conversation_id` | path string | 是 | 会话 ID |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items` | array | 是 | 消息列表 |
| `items[].role` | string | 是 | `user` 或 `assistant` |
| `items[].content` | string | 是 | 中文消息正文 |
| `items[].created_at` | string | 是 | 创建时间 |

#### POST `/api/interaction/chat`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | 是 | 用户问题 |
| `context.ticket_fact` | TicketFact | 否 | 作业票上下文 |
| `context.ticket_id` | string | 否 | 作业票 ID |
| `conversation_id` | string | 否 | 已有会话 ID |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 模型调用是否成功 |
| `provider` | string | 是 | 模型供应商 |
| `model` | string | 是 | 模型名称 |
| `conversation_id` | string | 是 | 会话 ID |
| `answer` | string | 是 | 中文 Markdown 回答 |
| `suggested_actions` | string[] | 是 | 建议动作 |

#### POST `/api/interaction/chat/stream`

输入参数同 `/api/interaction/chat`。

输出为 SSE：

| 事件 | 类型 | 说明 |
| --- | --- | --- |
| `type=conversation` | JSON | `{conversation_id}` |
| `type=delta` | JSON | `{content,provider,model}` |
| `type=final` | JSON | `{answer,conversation_id,provider,model}` |
| `type=error` | JSON | `{message}` |
| `type=done` | JSON | 流结束 |

#### GET `/api/pilot/hj`

输入参数：无。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 试点状态 |
| `project` | string | 是 | 试点项目名 |
| `ticket` | WorkTicket | 是 | 试点作业票 |
| `parse_record` | ParseRecord | 是 | 解析记录 |
| `image_count` | number | 是 | 可用图片数量 |
| `image_sources` | array | 是 | 图片资源列表 |

#### POST `/api/pilot/hj/run`

输入参数：无。

输出字段为 `PilotWorkflowResult`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 闭环是否成功 |
| `ticket` | WorkTicket | 是 | 作业票 |
| `media_manifest` | SiteMediaFrame[] | 是 | 抽帧或兜底帧列表 |
| `vision_result` | object | 是 | 视觉事实证据包 |
| `violation_result` | object | 是 | 违规检测结果 |
| `inspection` | InspectionRecord | 是 | 检查记录 |

#### POST `/api/inspection/run-full`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ticket_id` | string | 否 | 作业票 ID 或 `plan_id` |
| `record` | ParseRecord | 否 | 未入库解析记录 |
| `operator` | string | 否 | 操作人 |
| `mode` | string | 否 | 默认 `full_closed_loop` |

输出字段同 `PilotWorkflowResult`。

#### POST `/api/violation-detection/run`

输入参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ticket_id` | string | 否 | 作业票 ID 或 `plan_id`；传入后自动生成 `ticket_task_text` |
| `ticket_task_text` | string | 否 | 票面允许或计划作业内容；无 `ticket_id` 时必填 |
| `video_evidence_text` | string | 否 | 视觉理解输出的现场事实证据链文本 |
| `video_evidence_package` | object | 否 | 视觉事实证据包；无 `video_evidence_text` 时转 JSON 文本传给智能体 |
| `probability_threshold` | number | 否 | 低置信复核阈值，默认 0.35；高危会至少提升到 0.45 |
| `enable_second_video_reasoning` | boolean | 否 | 是否允许二次视频证据复核，默认 true |
| `risk_level` | string | 否 | 风险口径，如 `常规`、`低`、`中`、`高`、`高危` |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 是否成功 |
| `match_id` | string | 是 | 匹配任务 ID |
| `created_at` | string | 是 | 结果创建时间 |
| `provider` | string | 是 | `Qwen` |
| `model` | string | 是 | `qwen-plus-latest` |
| `token_probability_available` | boolean | 是 | Qwen 是否返回 token 概率 |
| `token_probability` | number | 否 | 最低 token 概率 |
| `avg_token_probability` | number | 否 | 平均 token 概率 |
| `token_probability_count` | number | 否 | token 概率样本数 |
| `result.match_result` | enum | 是 | `未发现明显异常`、`需持续观察`、`疑似不一致`、`明显不一致` |
| `result.task_match_score` | number | 是 | 作业内容匹配分 |
| `result.matched_work` | string[] | 是 | 已匹配作业内容 |
| `result.unmatched_work[]` | array | 是 | 疑似不一致项 |
| `result.unmatched_work[].ticket_side` | string | 是 | 票面侧描述 |
| `result.unmatched_work[].video_side` | string | 是 | 现场侧描述 |
| `result.unmatched_work[].evidence` | string | 是 | 证据说明 |
| `result.unmatched_work[].confidence` | number | 是 | 疑点置信度 |
| `result.need_second_video_reasoning` | boolean | 是 | 是否建议二次视频复核 |
| `result.reason` | string | 是 | 判别理由 |
| `second_pass.triggered` | boolean | 是 | 是否触发二次复核 |
| `second_pass.trigger_reasons` | string[] | 是 | 复核触发原因 |
| `second_pass.result` | object | 否 | 二次复核结果 |
| `manual_review_required` | boolean | 是 | 是否建议人工复核 |
| `ticket_summary` | object | 否 | 平台补充票面摘要 |
| `ticket_task_text` | string | 否 | 实际送入智能体的票面任务文本 |
| `video_evidence_text` | string | 否 | 实际送入智能体的现场证据链文本 |

## 3. LangGraph / Smith graph

`langgraph.json` 当前暴露 3 个 graph：

| Graph | 说明 |
| --- | --- |
| `work_ticket_parse_agent` | 单独作业票解析智能体 |
| `violation_detection_agent` | 单独违规检测智能体 |
| `unplanned_work_inspection_workflow` | 完整流程编排图：作业票解析 -> 视觉理解 -> 违规检测，并支持违规检测回到视觉理解复核 |

完整流程图的节点：

```text
作业票解析智能体 -> 视觉理解智能体 -> 违规检测智能体
                                     ^           |
                                     |-----------|
```

回边规则：违规检测发现低置信、存疑、触发二次复核或要求人工复核时，回到视觉理解智能体补充证据包；当前最多回查 1 次，避免循环。

完整流程 graph 输入示例：

```json
{
  "raw_text": "工程名称：测试工程\n编号：FLOW-001\n工作地点：广州测试站区\n作业部位及内容：主变室高大支模施工\n计划开始时间：2026-06-10 09:00:00\n计划结束时间：2026-06-10 18:00:00\n风险等级：高\n计划状态：开工中",
  "video_evidence_text": "第01帧 现场识别到高大支模作业。\n第18帧 现场额外出现构件吊装和大型机械配合作业。",
  "risk_level": "高",
  "probability_threshold": 0.35,
  "enable_second_video_reasoning": true
}
```

## 4. 内网集成客户端

### 监控抽帧接口

环境变量：

```env
CAMERA_API_URL=
CAMERA_API_TOKEN=
CAMERA_API_TIMEOUT=20
CAMERA_API_MOCK_FALLBACK=1
CAMERA_DEFAULT_WINDOW_MINUTES=30
CAMERA_DEFAULT_INTERVAL_MINUTES=1
```

平台调用请求：

```json
{
  "plan_id": "082100WS22200001-0068",
  "project_name": "110千伏新隆沙输变电工程（土建分册）",
  "work_location": "广东省广州市荔湾区芳村大道中万科海上传奇",
  "camera_ids": ["CAM_L13_01", "CAM_L13_02"],
  "start_time": "2026-06-10 13:00:00",
  "end_time": "2026-06-10 13:30:00",
  "interval_seconds": 60,
  "count": 30,
  "ticket_context": {}
}
```

期望返回：

```json
{
  "frames": [
    {
      "media_id": "frame_001",
      "camera_id": "CAM_L13_01",
      "camera_name": "L13塔固定枪机",
      "capture_time": "2026-06-10 13:01:00",
      "image_url": "http://...",
      "thumbnail_url": "http://...",
      "work_location": "..."
    }
  ]
}
```

### 作业票业务接口

环境变量：

```env
TICKET_API_URL=
TICKET_API_TOKEN=
TICKET_API_TIMEOUT=30
```

约定：

- `GET {TICKET_API_URL}/{plan_id}` 获取作业票。
- `POST {TICKET_API_URL}` 回传解析结果。

## 5. 视觉理解智能体接口开发模板

### 目标边界

视觉理解智能体只输出现场事实证据包，不直接输出最终违规裁决。最终裁决由违规检测智能体完成。

### 环境变量

```env
VISION_API_URL=http://vision-service/api/site-evidence/analyze
VISION_API_TOKEN=
VISION_API_TIMEOUT=90
VISION_API_MOCK_FALLBACK=1
```

### 推荐接口

`POST /api/site-evidence/analyze`

请求头：

```http
Content-Type: application/json
Authorization: Bearer <VISION_API_TOKEN>
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `task` | string | 是 | 任务名称，首轮为 `现场事实证据提取`，复核为 `现场事实证据复核` |
| `instruction` | string | 是 | 边界提示，必须强调只输出事实证据包 |
| `request_id` | string | 是 | 平台生成的视觉请求 ID，用于链路追踪 |
| `ticket_context.plan_id` | string | 否 | 作业票编号 |
| `ticket_context.project_name` | string | 否 | 工程名称 |
| `ticket_context.work_location` | string | 否 | 票面工作地点，用于区域一致性描述 |
| `ticket_context.work_content_raw` | string | 否 | 票面原始作业内容 |
| `ticket_context.work_actions` | string[] | 否 | 作业票解析智能体抽取的作业动作 |
| `ticket_context.risk_level` | string | 否 | 票面风险等级，仅作为观察重点，不直接决定违规 |
| `ticket_context.plan_time_range.start` | string | 否 | 计划开始时间，格式 `yyyy-MM-dd HH:mm:ss` |
| `ticket_context.plan_time_range.end` | string | 否 | 计划结束时间，格式 `yyyy-MM-dd HH:mm:ss` |
| `frames[].media_id` | string | 是 | 平台侧帧 ID |
| `frames[].camera_id` | string | 是 | 监控编号 |
| `frames[].camera_name` | string | 否 | 监控点名称 |
| `frames[].capture_time` | string | 是 | 抽帧时间 |
| `frames[].image_url` | string | 是 | 可由视觉服务访问的图片 URL |
| `options.language` | string | 否 | 固定 `zh-CN` |
| `options.return_frame_level_evidence` | boolean | 否 | 是否返回逐帧事实 |
| `options.return_uncertainties` | boolean | 否 | 是否返回不确定项 |
| `options.max_evidence_items` | number | 否 | 最多证据条数 |
| `options.focus_dimensions` | string[] | 否 | 重点观察维度 |
| `options.decision_boundary` | string | 是 | 必须为 `facts_only` |
| `review_context` | object | 复核时是 | 违规检测触发复核时传入疑点、原因和重点帧 |

请求体：

```json
{
  "task": "现场事实证据提取",
  "instruction": "只输出现场事实证据包，不直接输出最终违规裁决。",
  "request_id": "vision_20260610_0001",
  "ticket_context": {
    "plan_id": "082100WS22200001-0068",
    "project_name": "110千伏新隆沙输变电工程（土建分册）",
    "work_location": "广东省广州市荔湾区芳村大道中万科海上传奇",
    "work_content_raw": "配电装置楼4.97m至9.97m层主变室、GIS室高大支模施工",
    "work_actions": ["支模"],
    "risk_level": "高",
    "plan_time_range": {
      "start": "2026-06-10 10:34:00",
      "end": "2026-06-10 16:34:00"
    }
  },
  "frames": [
    {
      "media_id": "frame_001",
      "camera_id": "CAM_L13_01",
      "camera_name": "L13塔固定枪机",
      "capture_time": "2026-06-10 13:01:00",
      "image_url": "<BACKEND_API_URL>/api/media/site/frame_001.jpg"
    }
  ],
  "options": {
    "language": "zh-CN",
    "return_frame_level_evidence": true,
    "return_uncertainties": true,
    "max_evidence_items": 80,
    "focus_dimensions": [
      "作业动作",
      "作业对象",
      "人员与装备",
      "区域位置",
      "安全措施可见性"
    ],
    "decision_boundary": "facts_only"
  }
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `success` | boolean | 是 | 视觉理解是否成功 |
| `model_name` | string | 是 | 视觉模型名称或服务名称 |
| `frame_count` | number | 是 | 处理帧数量 |
| `output_boundary` | string | 是 | 固定说明为现场事实证据包 |
| `final_decision_allowed` | boolean | 是 | 必须为 false，不允许视觉模块直接裁决违规 |
| `aggregates.observed_actions` | string[] | 是 | 跨帧汇总观察到的作业动作 |
| `aggregates.observed_objects` | string[] | 是 | 跨帧汇总观察到的作业对象、设备、区域对象 |
| `aggregates.personnel_summary.max_visible_person_count` | number | 否 | 最大可见人员数量 |
| `aggregates.personnel_summary.ppe_visible` | string[] | 否 | 可见劳保用品 |
| `aggregates.personnel_summary.uncertain_items` | string[] | 否 | 人员或劳保不确定项 |
| `aggregates.equipment_summary` | string[] | 否 | 设备机具汇总 |
| `aggregates.location_consistency_evidence` | string | 否 | 地点一致性的事实描述，不作裁决 |
| `aggregates.safety_measure_evidence` | string[] | 否 | 安全措施可见事实 |
| `frames[].media_id` | string | 是 | 对应请求帧 ID |
| `frames[].capture_time` | string | 是 | 帧时间 |
| `frames[].camera_id` | string | 是 | 监控编号 |
| `frames[].facts[]` | array | 是 | 该帧事实条目 |
| `frames[].facts[].fact_type` | string | 是 | 事实类型，如 `作业动作`、`人员与装备`、`区域位置` |
| `frames[].facts[].label` | string | 是 | 事实标签，如 `支模`、`构件吊装`、`吊车` |
| `frames[].facts[].confidence` | number | 是 | 事实置信度，0 到 1 |
| `frames[].facts[].evidence_text` | string | 是 | 中文证据描述 |
| `frames[].facts[].bbox` | number[] | 否 | 归一化坐标 `[x1,y1,x2,y2]` |
| `frames[].uncertainties` | string[] | 否 | 该帧不确定项 |
| `evidence_text` | string | 是 | 给违规检测智能体使用的紧凑中文证据链文本 |
| `uncertainties` | string[] | 否 | 全局不确定项 |
| `review` | object | 复核时建议返回 | 复核轮次、聚焦点、已确认/排除疑点、剩余不确定项 |
| `raw` | object | 否 | 原始模型响应，便于排查但不直接展示给用户 |

响应体：

```json
{
  "success": true,
  "model_name": "vision-model-name",
  "frame_count": 30,
  "output_boundary": "现场事实证据包，不直接作最终违规裁决",
  "final_decision_allowed": false,
  "aggregates": {
    "observed_actions": ["支模", "材料转运", "构件吊装"],
    "observed_objects": ["主变室", "GIS室", "支撑架体", "吊车"],
    "personnel_summary": {
      "max_visible_person_count": 8,
      "ppe_visible": ["安全帽", "反光衣"],
      "uncertain_items": ["安全带佩戴情况部分帧不可见"]
    },
    "equipment_summary": ["吊车", "钢管", "模板", "切割机"],
    "location_consistency_evidence": "画面区域与作业票地点描述相符",
    "safety_measure_evidence": ["围蔽可见", "临边防护部分可见"]
  },
  "frames": [
    {
      "media_id": "frame_018",
      "capture_time": "2026-06-10 13:18:00",
      "camera_id": "CAM_L13_01",
      "facts": [
        {
          "fact_type": "作业动作",
          "label": "构件吊装",
          "confidence": 0.86,
          "evidence_text": "画面中央可见吊车臂架和被吊构件",
          "bbox": [0.42, 0.18, 0.76, 0.62]
        }
      ],
      "uncertainties": [
        "吊装构件用途无法仅凭单帧确认"
      ]
    }
  ],
  "evidence_text": "第01帧 现场可见支模材料和作业人员进场。第18帧 现场出现构件吊装和大型机械配合作业。",
  "uncertainties": [
    "部分帧遮挡导致人员数量统计存在误差"
  ],
  "raw": {}
}
```

### 二次复核接口扩展

同一接口可通过 `review_context` 支持复核：

复核请求扩展字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `review_context.trigger_reason` | string | 是 | 复核触发原因，如低置信、疑似不一致 |
| `review_context.first_pass_unmatched_work[]` | array | 是 | 首轮违规检测输出的疑点列表 |
| `review_context.first_pass_unmatched_work[].ticket_side` | string | 是 | 票面侧疑点 |
| `review_context.first_pass_unmatched_work[].video_side` | string | 是 | 现场侧疑点 |
| `review_context.first_pass_unmatched_work[].evidence` | string | 是 | 首轮证据说明 |
| `review_context.focus_frame_ids` | string[] | 否 | 希望重点复核的帧 ID |

```json
{
  "task": "现场事实证据复核",
  "instruction": "只围绕首轮违规检测疑点补充事实证据，不直接裁决。",
  "review_context": {
    "trigger_reason": "低置信或疑似不一致",
    "first_pass_unmatched_work": [
      {
        "ticket_side": "作业票未明确吊装",
        "video_side": "现场出现构件吊装",
        "evidence": "第18帧出现吊装"
      }
    ],
    "focus_frame_ids": ["frame_018", "frame_022"]
  },
  "ticket_context": {},
  "frames": []
}
```

复核响应仍然是事实证据包，但应补充：

```json
{
  "review": {
    "review_round": 1,
    "focus_points": ["构件吊装是否成立", "是否存在大型机械配合作业"],
    "verified_suspicions": [],
    "rejected_suspicions": [],
    "remaining_uncertainties": []
  }
}
```

## 6. 模型配置边界

| 功能 | 当前模型 |
| --- | --- |
| 系统交互、普通问答、作业票上下文问答 | Qwen `qwen-plus-latest` |
| 违规检测智能体 | Qwen `qwen-plus-latest` |
| 视觉理解智能体 | 待内网接口开发，平台提供 mock fallback |

## 7. 演示兜底策略

- `CAMERA_API_MOCK_FALLBACK=1`：监控抽帧接口不可用时使用演示图片。
- `VISION_API_MOCK_FALLBACK=1`：视觉理解接口不可用时使用本地演示事实包。
- 违规检测接口失败时会返回结构化错误，不影响其它页面使用。

## 8. 前端页面路由

| 路由 | 页面 |
| --- | --- |
| `/` | 仪表盘 |
| `/workbench/tickets` | 作业票查看 |
| `/workbench/parser` | 作业票解析 |
| `/inspection/system` | 系统交互 |
| `/inspection/violations` | 违规检测 |
| `/inspection/checks` | 作业检查 demo |
| `/pilot/hj` | 合景在线试点 |
| `/docx` | 接口与视觉理解开发文档 |
