import { Alert, Collapse, Descriptions, Table, Tag, Typography } from 'antd'

const { Paragraph, Text, Title } = Typography

const endpointRows = [
  { group: '基础', method: 'GET', path: '/api/health', usage: '服务健康检查', request: '无', response: '{ ok, service, time }' },
  { group: '基础', method: 'GET', path: '/api/assets/logo/{name}', usage: '平台 logo', request: 'path: name', response: '图片文件' },
  { group: '媒体', method: 'GET', path: '/api/media/site/{filename}', usage: '现场图片资源', request: 'path: filename', response: '图片文件' },
  { group: '媒体', method: 'GET', path: '/api/media/pilot/{filename}', usage: '试点图片资源', request: 'path: filename', response: '图片文件' },
  { group: '媒体', method: 'GET', path: '/api/media/pilot-frame/{filename}', usage: '试点抽帧资源', request: 'path: filename', response: '图片文件' },
  { group: '仪表盘', method: 'GET', path: '/api/dashboard', usage: '统计指标、风险分布、近期作业票', request: '无', response: 'DashboardData' },
  { group: '作业票', method: 'GET', path: '/api/work-tickets', usage: '分页查询作业票', request: 'page,page_size,status,keyword', response: '{ total, items }' },
  { group: '作业票', method: 'GET', path: '/api/work-tickets/samples', usage: '前端选择作业票样本', request: '无', response: '{ samples }' },
  { group: '作业票', method: 'GET', path: '/api/work-tickets/history', usage: '作业票解析历史', request: '无', response: '{ items }' },
  { group: '作业票', method: 'POST', path: '/api/work-tickets/parse', usage: '文本/PDF/图片作业票解析', request: 'multipart: text,sample_id,file', response: '{ success, record }' },
  { group: '作业票', method: 'POST', path: '/api/work-tickets/parse/stream', usage: '流式解析作业票', request: 'multipart: text,sample_id,file', response: 'SSE: step/final/error/done' },
  { group: '作业票', method: 'POST', path: '/api/work-tickets/import', usage: '解析结果入库', request: '{ record }', response: '{ success, created, ticket, message }' },
  { group: '检查', method: 'POST', path: '/api/interaction/start-inspection', usage: '发起作业检查闭环', request: 'InspectionRequest', response: '{ success, inspection, result }' },
  { group: '检查', method: 'GET', path: '/api/interaction/inspections', usage: '检查记录列表', request: '无', response: '{ items }' },
  { group: '智能服务', method: 'GET', path: '/api/interaction/llm-status', usage: '通用智能服务状态', request: '无', response: '{ provider, model, available, api_format }' },
  { group: '交互', method: 'GET', path: '/api/interaction/conversations', usage: '系统交互会话列表', request: '无', response: '{ items }' },
  { group: '交互', method: 'GET', path: '/api/interaction/conversations/{conversation_id}/messages', usage: '会话消息', request: 'path: conversation_id', response: '{ items }' },
  { group: '交互', method: 'POST', path: '/api/interaction/chat', usage: '非流式智能问答', request: 'ChatRequest', response: '{ success, answer, conversation_id }' },
  { group: '交互', method: 'POST', path: '/api/interaction/chat/stream', usage: '流式智能问答', request: 'ChatRequest', response: 'SSE: conversation/delta/final/error/done' },
  { group: '试点', method: 'GET', path: '/api/pilot/hj', usage: '合景试点状态', request: '无', response: '试点作业票、图片源状态' },
  { group: '试点', method: 'POST', path: '/api/pilot/hj/run', usage: '运行合景试点闭环', request: '无', response: 'PilotWorkflowResult' },
  { group: '闭环', method: 'POST', path: '/api/inspection/run-full', usage: '完整作业检查闭环', request: 'FullInspectionRequest', response: 'PilotWorkflowResult' },
  { group: '违规检测', method: 'POST', path: '/api/violation-detection/run', usage: '作业内容匹配判别', request: 'ViolationDetectionRequest', response: 'ViolationDetectionResult' },
]

const endpointDetails = [
  {
    key: 'health',
    group: '基础',
    method: 'GET',
    path: '/api/health',
    usage: '检查后端服务是否正常。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [
      { name: 'ok', type: 'boolean', required: '是', desc: '服务是否正常' },
      { name: 'service', type: 'string', required: '是', desc: '服务标识' },
      { name: 'time', type: 'string', required: '是', desc: '服务器当前时间 ISO 字符串' },
    ],
  },
  {
    key: 'logo',
    group: '基础',
    method: 'GET',
    path: '/api/assets/logo/{name}',
    usage: '读取平台 logo，目前支持 nfdw。',
    requestFields: [{ name: 'name', type: 'path string', required: '否', desc: 'logo 名称，非法值自动回退为 nfdw' }],
    responseFields: [{ name: 'body', type: 'image/*', required: '是', desc: '图片文件响应' }],
  },
  {
    key: 'media-site',
    group: '媒体',
    method: 'GET',
    path: '/api/media/site/{filename}',
    usage: '读取现场图片。视觉理解开发时可将该地址作为 image_url 样例。',
    requestFields: [{ name: 'filename', type: 'path string', required: '是', desc: '图片文件名，只取安全文件名' }],
    responseFields: [{ name: 'body', type: 'image/*', required: '是', desc: '现场图片文件；不存在时回退到默认图片' }],
  },
  {
    key: 'media-pilot',
    group: '媒体',
    method: 'GET',
    path: '/api/media/pilot/{filename}',
    usage: '读取合景试点图片。',
    requestFields: [{ name: 'filename', type: 'path string', required: '是', desc: '图片文件名' }],
    responseFields: [{ name: 'body', type: 'image/*', required: '是', desc: '图片文件' }],
  },
  {
    key: 'media-pilot-frame',
    group: '媒体',
    method: 'GET',
    path: '/api/media/pilot-frame/{filename}',
    usage: '读取合景试点抽帧图片。',
    requestFields: [{ name: 'filename', type: 'path string', required: '是', desc: '抽帧图片文件名' }],
    responseFields: [{ name: 'body', type: 'image/*', required: '是', desc: '图片文件' }],
  },
  {
    key: 'dashboard',
    group: '仪表盘',
    method: 'GET',
    path: '/api/dashboard',
    usage: '首页统计数据。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [
      { name: 'stats.total_tickets', type: 'number', required: '是', desc: '作业票总数' },
      { name: 'stats.active_tickets', type: 'number', required: '是', desc: '开工中作业票数量' },
      { name: 'stats.pending_match_tickets', type: 'number', required: '是', desc: '待匹配作业票数量' },
      { name: 'stats.high_risk_tickets', type: 'number', required: '是', desc: '高风险作业票数量' },
      { name: 'stats.video_control_tickets', type: 'number', required: '是', desc: '纳入视频管控数量' },
      { name: 'by_status/by_risk/by_district', type: 'array', required: '是', desc: '图表数据，元素为 { name, value }' },
      { name: 'recent_tickets', type: 'WorkTicket[]', required: '是', desc: '近期作业票列表' },
    ],
  },
  {
    key: 'work-tickets',
    group: '作业票',
    method: 'GET',
    path: '/api/work-tickets',
    usage: '分页查询作业票。',
    requestFields: [
      { name: 'page', type: 'query integer', required: '否', desc: '页码，默认 1，最小 1' },
      { name: 'page_size', type: 'query integer', required: '否', desc: '每页数量，默认 20，最大 100' },
      { name: 'status', type: 'query string', required: '否', desc: '计划状态过滤，如 开工中、待开工、已完工' },
      { name: 'keyword', type: 'query string', required: '否', desc: '按计划编号、工程名、地点等关键字查询' },
    ],
    responseFields: [
      { name: 'total', type: 'number', required: '是', desc: '符合条件的总数' },
      { name: 'items', type: 'WorkTicket[]', required: '是', desc: '作业票列表' },
      { name: 'items[].id/plan_id', type: 'string', required: '是', desc: '内部 ID / 计划编号' },
      { name: 'items[].ticket_fact', type: 'TicketFact', required: '是', desc: '作业票结构化事实，视觉理解 ticket_context 主要来源' },
      { name: 'items[].media_query_task', type: 'object', required: '是', desc: '媒体调取任务，包含候选摄像头和时间窗口' },
    ],
  },
  {
    key: 'samples',
    group: '作业票',
    method: 'GET',
    path: '/api/work-tickets/samples',
    usage: '前端选择器使用的作业票样本列表。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [
      { name: 'samples', type: 'SampleTicket[]', required: '是', desc: '样本列表' },
      { name: 'samples[].id/name/source_type/raw_text', type: 'string', required: '是', desc: '样本基础信息' },
      { name: 'samples[].ticket', type: 'WorkTicket', required: '否', desc: '数据库作业票对象' },
    ],
  },
  {
    key: 'history',
    group: '作业票',
    method: 'GET',
    path: '/api/work-tickets/history',
    usage: '读取最近作业票解析记录。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [{ name: 'items', type: 'ParseRecord[]', required: '是', desc: '最近 20 条解析记录' }],
  },
  {
    key: 'parse',
    group: '作业票',
    method: 'POST',
    path: '/api/work-tickets/parse',
    usage: '解析文本、PDF 或图片作业票。',
    requestFields: [
      { name: 'text', type: 'form string', required: '否', desc: '作业票文本；上传文件时可为空' },
      { name: 'sample_id', type: 'form string', required: '否', desc: '样本 ID' },
      { name: 'file', type: 'form File', required: '否', desc: 'PDF 或图片文件' },
    ],
    responseFields: [
      { name: 'success', type: 'boolean', required: '是', desc: '是否解析成功' },
      { name: 'record.id/source_type/summary/raw_text', type: 'string', required: '是', desc: '解析记录基础信息' },
      { name: 'record.pdf_result/ocr_result', type: 'object', required: '否', desc: 'PDF 或 OCR 提取结果' },
      { name: 'record.ticket_fact', type: 'TicketFact', required: '是', desc: '作业票结构化结果' },
      { name: 'record.work_content_items', type: 'string[]', required: '是', desc: '拆分后的作业内容' },
      { name: 'record.media_query_task', type: 'object', required: '是', desc: '媒体调取任务' },
      { name: 'record.agent_analysis', type: 'object', required: '否', desc: '作业票智能体分析结果' },
    ],
  },
  {
    key: 'parse-stream',
    group: '作业票',
    method: 'POST',
    path: '/api/work-tickets/parse/stream',
    usage: '流式解析作业票，前端用于展示进度。',
    requestFields: [
      { name: 'text/sample_id/file', type: 'multipart/form-data', required: '否', desc: '同 /api/work-tickets/parse' },
    ],
    responseFields: [
      { name: 'type=step', type: 'SSE JSON', required: '否', desc: '{ index, title, status }' },
      { name: 'type=final', type: 'SSE JSON', required: '否', desc: '{ record }' },
      { name: 'type=error', type: 'SSE JSON', required: '否', desc: '{ message }' },
      { name: 'type=done', type: 'SSE JSON', required: '是', desc: '流结束' },
    ],
  },
  {
    key: 'import',
    group: '作业票',
    method: 'POST',
    path: '/api/work-tickets/import',
    usage: '将解析记录入库为业务作业票。',
    requestFields: [{ name: 'record', type: 'ParseRecord', required: '是', desc: '作业票解析记录' }],
    responseFields: [
      { name: 'success', type: 'boolean', required: '是', desc: '接口是否处理成功' },
      { name: 'created', type: 'boolean', required: '是', desc: '是否新建入库' },
      { name: 'ticket', type: 'WorkTicket', required: '否', desc: '入库后的作业票' },
      { name: 'message', type: 'string', required: '是', desc: '处理说明' },
    ],
  },
  {
    key: 'start-inspection',
    group: '检查',
    method: 'POST',
    path: '/api/interaction/start-inspection',
    usage: '从作业票发起检查闭环。',
    requestFields: [
      { name: 'ticket_id', type: 'string', required: '否', desc: '作业票内部 ID 或 plan_id' },
      { name: 'ticket_fact', type: 'TicketFact', required: '否', desc: '不传 ticket_id 时可直接传票面事实' },
      { name: 'media_query_task', type: 'object', required: '否', desc: '媒体调取任务' },
      { name: 'operator', type: 'string', required: '否', desc: '操作人，默认 系统自动检查' },
      { name: 'mode', type: 'string', required: '否', desc: '检查模式，默认 manual' },
    ],
    responseFields: [
      { name: 'success', type: 'boolean', required: '是', desc: '是否发起成功' },
      { name: 'inspection', type: 'InspectionRecord', required: '是', desc: '检查记录' },
      { name: 'result', type: 'PilotWorkflowResult', required: '否', desc: '完整闭环结果' },
    ],
  },
  {
    key: 'inspections',
    group: '检查',
    method: 'GET',
    path: '/api/interaction/inspections',
    usage: '读取检查记录列表。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [{ name: 'items', type: 'InspectionRecord[]', required: '是', desc: '最近 50 条检查记录' }],
  },
  {
    key: 'llm-status',
    group: '智能服务',
    method: 'GET',
    path: '/api/interaction/llm-status',
    usage: '通用智能服务状态，当前系统交互、智能问答和违规检测统一使用平台配置。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [
      { name: 'provider', type: 'string', required: '是', desc: '智能服务供应商' },
      { name: 'model', type: 'string', required: '是', desc: '当前模型名称' },
      { name: 'available', type: 'boolean', required: '是', desc: '是否配置可用' },
      { name: 'api_format', type: 'string', required: '否', desc: '接口格式，如 anthropic/openai' },
    ],
  },
  {
    key: 'conversations',
    group: '交互',
    method: 'GET',
    path: '/api/interaction/conversations',
    usage: '查询系统交互会话列表。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [{ name: 'items', type: 'array', required: '是', desc: '会话列表，含 id/title/ticket_id/created_at/updated_at' }],
  },
  {
    key: 'conversation-messages',
    group: '交互',
    method: 'GET',
    path: '/api/interaction/conversations/{conversation_id}/messages',
    usage: '查询指定会话消息。',
    requestFields: [{ name: 'conversation_id', type: 'path string', required: '是', desc: '会话 ID' }],
    responseFields: [{ name: 'items', type: 'array', required: '是', desc: '消息列表，含 role/content/created_at' }],
  },
  {
    key: 'chat',
    group: '交互',
    method: 'POST',
    path: '/api/interaction/chat',
    usage: '非流式系统问答。',
    requestFields: [
      { name: 'message', type: 'string', required: '是', desc: '用户问题' },
      { name: 'context.ticket_fact', type: 'TicketFact', required: '否', desc: '作业票上下文' },
      { name: 'context.ticket_id', type: 'string', required: '否', desc: '作业票 ID' },
      { name: 'conversation_id', type: 'string', required: '否', desc: '已有会话 ID' },
    ],
    responseFields: [
      { name: 'success', type: 'boolean', required: '是', desc: '模型调用是否成功' },
      { name: 'provider/model', type: 'string', required: '是', desc: '模型来源' },
      { name: 'conversation_id', type: 'string', required: '是', desc: '会话 ID' },
      { name: 'answer', type: 'string', required: '是', desc: '中文 Markdown 回答' },
      { name: 'suggested_actions', type: 'string[]', required: '是', desc: '建议动作' },
    ],
  },
  {
    key: 'chat-stream',
    group: '交互',
    method: 'POST',
    path: '/api/interaction/chat/stream',
    usage: '流式系统问答。',
    requestFields: [{ name: 'message/context/conversation_id', type: 'ChatRequest', required: '是', desc: '同非流式问答' }],
    responseFields: [
      { name: 'type=conversation', type: 'SSE JSON', required: '否', desc: '{ conversation_id }' },
      { name: 'type=delta', type: 'SSE JSON', required: '否', desc: '{ content, provider, model }' },
      { name: 'type=final', type: 'SSE JSON', required: '否', desc: '{ answer, conversation_id, provider, model }' },
      { name: 'type=done', type: 'SSE JSON', required: '是', desc: '流结束' },
    ],
  },
  {
    key: 'pilot-status',
    group: '试点',
    method: 'GET',
    path: '/api/pilot/hj',
    usage: '查询合景在线试点状态。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求参数' }],
    responseFields: [
      { name: 'success/project', type: 'boolean/string', required: '是', desc: '试点状态和项目名' },
      { name: 'ticket', type: 'WorkTicket', required: '是', desc: '试点作业票' },
      { name: 'parse_record', type: 'ParseRecord', required: '是', desc: '解析记录' },
      { name: 'image_count/image_sources', type: 'number/array', required: '是', desc: '可用图片资源' },
    ],
  },
  {
    key: 'pilot-run',
    group: '试点',
    method: 'POST',
    path: '/api/pilot/hj/run',
    usage: '运行合景试点完整闭环。',
    requestFields: [{ name: '无', type: '-', required: '-', desc: '无请求体' }],
    responseFields: [{ name: 'body', type: 'PilotWorkflowResult', required: '是', desc: '完整闭环结果' }],
  },
  {
    key: 'run-full',
    group: '闭环',
    method: 'POST',
    path: '/api/inspection/run-full',
    usage: '基于 ticket_id 或解析 record 运行完整闭环。',
    requestFields: [
      { name: 'ticket_id', type: 'string', required: '否', desc: '作业票 ID 或 plan_id' },
      { name: 'record', type: 'ParseRecord', required: '否', desc: '未入库解析记录' },
      { name: 'operator', type: 'string', required: '否', desc: '操作人' },
      { name: 'mode', type: 'string', required: '否', desc: '默认 full_closed_loop' },
    ],
    responseFields: [
      { name: 'success', type: 'boolean', required: '是', desc: '是否成功' },
      { name: 'ticket', type: 'WorkTicket', required: '是', desc: '作业票' },
      { name: 'media_manifest', type: 'SiteMediaFrame[]', required: '是', desc: '监控抽帧/兜底帧列表' },
      { name: 'vision_result', type: 'object', required: '是', desc: '视觉事实证据包' },
      { name: 'violation_result', type: 'object', required: '是', desc: '违规检测结果' },
      { name: 'inspection', type: 'InspectionRecord', required: '是', desc: '检查记录' },
    ],
  },
  {
    key: 'violation-run',
    group: '违规检测',
    method: 'POST',
    path: '/api/violation-detection/run',
    usage: '作业票任务文本与现场证据链匹配判别。当前只对作业内容维度做判别。',
    requestFields: [
      { name: 'ticket_id', type: 'string', required: '否', desc: '作业票 ID 或 plan_id；传入后自动生成 ticket_task_text' },
      { name: 'ticket_task_text', type: 'string', required: '否', desc: '票面允许/计划作业内容；无 ticket_id 时必填' },
      { name: 'video_evidence_text', type: 'string', required: '否', desc: '视觉理解输出的现场事实证据链文本' },
      { name: 'video_evidence_package', type: 'object', required: '否', desc: '视觉事实证据包；无 evidence_text 时转 JSON 文本传给智能体' },
      { name: 'probability_threshold', type: 'number', required: '否', desc: '低置信复核阈值，默认 0.35；高危会至少提升到 0.45' },
      { name: 'enable_second_video_reasoning', type: 'boolean', required: '否', desc: '是否允许二次视频证据复核，默认 true' },
      { name: 'risk_level', type: 'string', required: '否', desc: '风险口径，如 常规/低/中/高/高危' },
    ],
    responseFields: [
      { name: 'success/match_id/created_at', type: 'boolean/string/string', required: '是', desc: '结果状态、匹配任务 ID、创建时间' },
      { name: 'provider/model', type: 'string', required: '是', desc: '平台当前智能服务与模型名称' },
      { name: 'token_probability_available', type: 'boolean', required: '是', desc: '是否返回 token 概率' },
      { name: 'token_probability/avg_token_probability/token_probability_count', type: 'number', required: '否', desc: '最低/平均 token 概率和 token 数量' },
      { name: 'result.match_result', type: 'enum', required: '是', desc: '未发现明显异常/需持续观察/疑似不一致/明显不一致' },
      { name: 'result.task_match_score', type: 'number', required: '是', desc: '作业内容匹配分' },
      { name: 'result.matched_work', type: 'string[]', required: '是', desc: '已匹配作业内容' },
      { name: 'result.unmatched_work[]', type: 'array', required: '是', desc: '疑似不一致项，含 ticket_side/video_side/evidence/confidence' },
      { name: 'second_pass', type: 'object', required: '是', desc: '二次复核触发、原因、复核结果' },
      { name: 'manual_review_required', type: 'boolean', required: '是', desc: '是否建议人工复核' },
      { name: 'ticket_summary/ticket_task_text/video_evidence_text', type: 'object/string/string', required: '否', desc: '平台补充上下文' },
    ],
  },
]

const graphRows = [
  { graph: 'work_ticket_parse_agent', usage: '单独作业票解析智能体', input: '{ raw_text, source_type }', output: 'ticket_fact, work_content_items, validation_result, media_query_task' },
  { graph: 'violation_detection_agent', usage: '单独违规检测智能体', input: '{ ticket_id | ticket_task_text, video_evidence_text, risk_level }', output: 'match_result, token_probability, second_pass, manual_review_required' },
  { graph: 'unplanned_work_inspection_workflow', usage: '完整流程图：作业票解析 -> 视觉理解 -> 违规检测，并带复核回边', input: '{ raw_text | ticket_id | ticket_task_text, video_evidence_text }', output: 'ticket_fact, visual_evidence_package, violation_result' },
]

const envRows = [
  { key: 'META_API_KEY / META_BASE_URL / META_MODEL_NAME', usage: '全平台大模型调用配置' },
  { key: 'DASHSCOPE_API_KEY / MODEL_API_BASE_URL / MODEL_NAME', usage: '备用模型配置，主配置未启用时使用' },
  { key: 'MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE', usage: 'MySQL 数据库连接' },
  { key: 'TICKET_DATA_DIR', usage: '作业票批量导入扫描目录' },
  { key: 'CAMERA_API_URL / CAMERA_API_TOKEN', usage: '内网监控抽帧接口' },
  { key: 'VISION_API_URL / VISION_API_TOKEN', usage: '视觉理解智能体接口' },
  { key: 'TICKET_API_URL / TICKET_API_TOKEN', usage: '外部作业票业务系统接口' },
]

const visionRequest = `{
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
    "focus_dimensions": ["作业动作", "作业对象", "人员与装备", "区域位置", "安全措施可见性"],
    "decision_boundary": "facts_only"
  }
}`

const visionResponse = `{
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
    "equipment_summary": ["吊车", "钢管", "模板"],
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
      "uncertainties": ["吊装构件用途无法仅凭单帧确认"]
    }
  ],
  "evidence_text": "第01帧 现场可见支模材料和作业人员进场。第18帧 现场出现构件吊装和大型机械配合作业。",
  "uncertainties": ["部分帧遮挡导致人员数量统计存在误差"],
  "raw": {}
}`

const reviewRequest = `{
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
}`

type FieldRow = {
  name: string
  type: string
  required: string
  desc: string
}

function FieldTable({ rows }: { rows: FieldRow[] }) {
  return (
    <Table
      rowKey={(row) => `${row.name}-${row.type}`}
      size="small"
      pagination={false}
      dataSource={rows}
      columns={[
        { title: '字段', dataIndex: 'name', width: 260, render: (value) => <Text code>{value}</Text> },
        { title: '类型', dataIndex: 'type', width: 180 },
        { title: '必填', dataIndex: 'required', width: 80 },
        { title: '说明', dataIndex: 'desc' },
      ]}
    />
  )
}

function CodeBlock({ children }: { children: string }) {
  return <pre className="doc-code">{children}</pre>
}

export default function DocxPage() {
  return (
    <div className="doc-page">
      <div className="doc-hero">
        <Tag color="blue">接口说明</Tag>
        <Title level={1}>无计划作业智能检查平台接口与视觉理解智能体说明</Title>
        <Paragraph>本文档覆盖当前平台 REST API、LangGraph/Smith graph、内网集成客户端、模型边界和待开发视觉理解智能体接口模板。更新时间：2026-06-10。</Paragraph>
      </div>

      <Alert
        type="info"
        showIcon
        message="关键边界"
        description="视觉理解智能体只输出现场事实证据包，不直接做最终违规裁决；违规检测智能体负责读取票面结构化结果、视觉证据包和检测规则，输出风险等级、命中规则、证据帧、维度比对和检查报告。"
      />

      <section className="doc-section">
        <Title level={2}>1. 服务入口</Title>
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="前端平台">&lt;FRONTEND_URL&gt;</Descriptions.Item>
          <Descriptions.Item label="本文档">&lt;FRONTEND_URL&gt;/docx</Descriptions.Item>
          <Descriptions.Item label="后端 API">&lt;BACKEND_API_URL&gt;/api</Descriptions.Item>
          <Descriptions.Item label="LangGraph 本地服务">&lt;LANGGRAPH_URL&gt;</Descriptions.Item>
          <Descriptions.Item label="当前 tunnel">&lt;LANGGRAPH_TUNNEL_URL&gt;</Descriptions.Item>
        </Descriptions>
      </section>

      <section className="doc-section">
        <Title level={2}>2. 后端 REST API</Title>
        <Table
          rowKey={(row) => `${row.method}-${row.path}`}
          size="small"
          pagination={false}
          dataSource={endpointRows}
          columns={[
            { title: '分组', dataIndex: 'group', width: 92, render: (value) => <Tag>{value}</Tag> },
            { title: '方法', dataIndex: 'method', width: 78, render: (value) => <Tag color={value === 'GET' ? 'green' : 'blue'}>{value}</Tag> },
            { title: '路径', dataIndex: 'path', width: 330, render: (value) => <Text code>{value}</Text> },
            { title: '用途', dataIndex: 'usage' },
            { title: '入参', dataIndex: 'request' },
            { title: '返回', dataIndex: 'response' },
          ]}
        />
        <Title level={3}>接口字段明细</Title>
        <Collapse
          accordion
          className="doc-api-collapse"
          items={endpointDetails.map((endpoint) => ({
            key: endpoint.key,
            label: (
              <div className="doc-api-label">
                <Tag>{endpoint.group}</Tag>
                <Tag color={endpoint.method === 'GET' ? 'green' : 'blue'}>{endpoint.method}</Tag>
                <Text code>{endpoint.path}</Text>
                <span>{endpoint.usage}</span>
              </div>
            ),
            children: (
              <div className="doc-api-detail">
                <Title level={4}>输入参数</Title>
                <FieldTable rows={endpoint.requestFields} />
                <Title level={4}>输出字段</Title>
                <FieldTable rows={endpoint.responseFields} />
              </div>
            ),
          }))}
        />
      </section>

      <section className="doc-section">
        <Title level={2}>3. LangGraph / Smith graph</Title>
        <Table
          rowKey="graph"
          size="small"
          pagination={false}
          dataSource={graphRows}
          columns={[
            { title: 'Graph', dataIndex: 'graph', width: 280, render: (value) => <Text code>{value}</Text> },
            { title: '说明', dataIndex: 'usage' },
            { title: '输入', dataIndex: 'input' },
            { title: '输出', dataIndex: 'output' },
          ]}
        />
        <div className="doc-flow">
          <span>作业票解析智能体</span>
          <b>{'->'}</b>
          <span>视觉理解智能体</span>
          <b>{'->'}</b>
          <span>违规检测智能体</span>
          <b className="doc-return">复核回边：违规检测 {'->'} 视觉理解</b>
        </div>
      </section>

      <section className="doc-section">
        <Title level={2}>4. 环境变量与内网集成</Title>
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={envRows}
          columns={[
            { title: '配置项', dataIndex: 'key', width: 420, render: (value) => <Text code>{value}</Text> },
            { title: '用途', dataIndex: 'usage' },
          ]}
        />
      </section>

      <section className="doc-section">
        <Title level={2}>5. 视觉理解智能体接口模板</Title>
        <Paragraph>
          推荐接口：<Text code>POST /api/site-evidence/analyze</Text>。平台通过 <Text code>VISION_API_URL</Text> 调用该接口。
          响应必须保持“事实证据包”边界，字段 <Text code>final_decision_allowed</Text> 应为 <Text code>false</Text>。
        </Paragraph>
        <Title level={3}>请求字段</Title>
        <FieldTable
          rows={[
            { name: 'task', type: 'string', required: '是', desc: '任务名称，首轮为 现场事实证据提取，复核为 现场事实证据复核' },
            { name: 'instruction', type: 'string', required: '是', desc: '边界提示，必须强调只输出事实证据包' },
            { name: 'request_id', type: 'string', required: '是', desc: '平台生成的视觉请求 ID，用于链路追踪' },
            { name: 'ticket_context.plan_id', type: 'string', required: '否', desc: '作业票编号' },
            { name: 'ticket_context.project_name', type: 'string', required: '否', desc: '工程名称' },
            { name: 'ticket_context.work_location', type: 'string', required: '否', desc: '票面工作地点，用于区域一致性描述' },
            { name: 'ticket_context.work_content_raw', type: 'string', required: '否', desc: '票面原始作业内容' },
            { name: 'ticket_context.work_actions', type: 'string[]', required: '否', desc: '作业票解析智能体抽取的作业动作' },
            { name: 'ticket_context.risk_level', type: 'string', required: '否', desc: '票面风险等级，仅作为观察重点，不直接决定违规' },
            { name: 'ticket_context.plan_time_range.start/end', type: 'string', required: '否', desc: '计划开始/结束时间，格式 yyyy-MM-dd HH:mm:ss' },
            { name: 'frames[].media_id', type: 'string', required: '是', desc: '平台侧帧 ID' },
            { name: 'frames[].camera_id', type: 'string', required: '是', desc: '监控编号' },
            { name: 'frames[].camera_name', type: 'string', required: '否', desc: '监控点名称' },
            { name: 'frames[].capture_time', type: 'string', required: '是', desc: '抽帧时间' },
            { name: 'frames[].image_url', type: 'string', required: '是', desc: '可由视觉服务访问的图片 URL' },
            { name: 'options.language', type: 'string', required: '否', desc: '固定 zh-CN' },
            { name: 'options.return_frame_level_evidence', type: 'boolean', required: '否', desc: '是否返回逐帧事实' },
            { name: 'options.return_uncertainties', type: 'boolean', required: '否', desc: '是否返回不确定项' },
            { name: 'options.max_evidence_items', type: 'number', required: '否', desc: '最多证据条数' },
            { name: 'options.focus_dimensions', type: 'string[]', required: '否', desc: '重点观察维度' },
            { name: 'options.decision_boundary', type: 'string', required: '是', desc: '必须为 facts_only' },
            { name: 'review_context', type: 'object', required: '复核时是', desc: '违规检测触发复核时传入疑点、原因和重点帧' },
          ]}
        />
        <Title level={3}>响应字段</Title>
        <FieldTable
          rows={[
            { name: 'success', type: 'boolean', required: '是', desc: '视觉理解是否成功' },
            { name: 'model_name', type: 'string', required: '是', desc: '视觉模型名称或服务名称' },
            { name: 'frame_count', type: 'number', required: '是', desc: '处理帧数量' },
            { name: 'output_boundary', type: 'string', required: '是', desc: '固定说明为现场事实证据包' },
            { name: 'final_decision_allowed', type: 'boolean', required: '是', desc: '必须为 false，不允许视觉模块直接裁决违规' },
            { name: 'aggregates.observed_actions', type: 'string[]', required: '是', desc: '跨帧汇总观察到的作业动作' },
            { name: 'aggregates.observed_objects', type: 'string[]', required: '是', desc: '跨帧汇总观察到的作业对象、设备、区域对象' },
            { name: 'aggregates.personnel_summary', type: 'object', required: '否', desc: '人员数量、劳保可见性、不确定项' },
            { name: 'aggregates.equipment_summary', type: 'string[]', required: '否', desc: '设备机具汇总' },
            { name: 'aggregates.location_consistency_evidence', type: 'string', required: '否', desc: '地点一致性的事实描述，不作裁决' },
            { name: 'aggregates.safety_measure_evidence', type: 'string[]', required: '否', desc: '安全措施可见事实' },
            { name: 'frames[].media_id', type: 'string', required: '是', desc: '对应请求帧 ID' },
            { name: 'frames[].capture_time', type: 'string', required: '是', desc: '帧时间' },
            { name: 'frames[].camera_id', type: 'string', required: '是', desc: '监控编号' },
            { name: 'frames[].facts[]', type: 'array', required: '是', desc: '该帧事实条目' },
            { name: 'frames[].facts[].fact_type', type: 'string', required: '是', desc: '事实类型，如 作业动作、人员与装备、区域位置' },
            { name: 'frames[].facts[].label', type: 'string', required: '是', desc: '事实标签，如 支模、构件吊装、吊车' },
            { name: 'frames[].facts[].confidence', type: 'number', required: '是', desc: '事实置信度，0 到 1' },
            { name: 'frames[].facts[].evidence_text', type: 'string', required: '是', desc: '中文证据描述' },
            { name: 'frames[].facts[].bbox', type: 'number[]', required: '否', desc: '归一化坐标 [x1,y1,x2,y2]' },
            { name: 'frames[].uncertainties', type: 'string[]', required: '否', desc: '该帧不确定项' },
            { name: 'evidence_text', type: 'string', required: '是', desc: '给违规检测智能体使用的紧凑中文证据链文本' },
            { name: 'uncertainties', type: 'string[]', required: '否', desc: '全局不确定项' },
            { name: 'review', type: 'object', required: '复核时建议返回', desc: '复核轮次、聚焦点、已确认/排除疑点、剩余不确定项' },
            { name: 'raw', type: 'object', required: '否', desc: '原始模型响应，便于排查但不直接展示给用户' },
          ]}
        />
        <Collapse
          defaultActiveKey={['request', 'response']}
          items={[
            { key: 'request', label: '请求体模板', children: <CodeBlock>{visionRequest}</CodeBlock> },
            { key: 'response', label: '响应体模板', children: <CodeBlock>{visionResponse}</CodeBlock> },
            { key: 'review', label: '二次复核请求扩展', children: <CodeBlock>{reviewRequest}</CodeBlock> },
          ]}
        />
      </section>

      <section className="doc-section">
        <Title level={2}>6. 前端路由</Title>
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="/">仪表盘</Descriptions.Item>
          <Descriptions.Item label="/workbench/tickets">作业票查看</Descriptions.Item>
          <Descriptions.Item label="/workbench/parser">作业票解析</Descriptions.Item>
          <Descriptions.Item label="/inspection/system">系统交互</Descriptions.Item>
          <Descriptions.Item label="/inspection/violations">违规检测</Descriptions.Item>
          <Descriptions.Item label="/inspection/checks">作业检查 demo</Descriptions.Item>
          <Descriptions.Item label="/pilot/hj">合景在线试点</Descriptions.Item>
          <Descriptions.Item label="/docx">接口与视觉理解开发文档</Descriptions.Item>
        </Descriptions>
      </section>
    </div>
  )
}
