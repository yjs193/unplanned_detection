
import { Alert, Button, Descriptions, Divider, Image, Input, List, Select, Space, Statistic, Steps, Table, Tabs, Tag, Upload, message } from 'antd'
import { DatabaseOutlined, InboxOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchSamples, importParsedTicket, parseTicketStream, runFullInspection } from '../api'
import type { ParseRecord, PilotWorkflowResult, SampleTicket } from '../types'

const { TextArea } = Input
const { Dragger } = Upload

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const frameLabel = (row: Record<string, any>) => row.display_label || `第${String(row.minute_index || String(row.media_id || '').match(/(\d+)$/)?.[1] || '').padStart(2, '0')}帧`

const workTypeLabels: Record<string, string> = {
  wire_and_cable_stringing: '导地线展放',
  wire_tensioning: '紧线作业',
  crimping: '压接作业',
  accessory_installation: '附件安装',
  crossing_frame_erection: '跨越架搭设',
  protective_net_installation: '封网施工',
  retaining_wall_construction: '挡土墙施工',
  rebar_binding: '钢筋绑扎',
  formwork_installation: '模板安装',
  concrete_pouring: '混凝土浇筑',
  material_transport: '材料转运',
  trench_excavation: '电缆沟开挖',
  grounding_grid_installation: '接地网敷设',
  lifting_operation: '吊装作业',
  tower_assembly: '塔材组立',
  earthwork_excavation: '土方开挖',
  foundation_construction: '地基基础',
  transformer_installation: '主变安装',
  power_outage_coordination: '停电配合',
}


function cnWorkType(value: string) {
  return workTypeLabels[value] || '其他作业'
}

function saveLatest(record: ParseRecord) {
  localStorage.setItem('latest_parse_record', JSON.stringify(record))
}

export default function TicketParserPage() {
  const [text, setText] = useState('')
  const [sampleId, setSampleId] = useState<string>()
  const [file, setFile] = useState<File>()
  const [activeTab, setActiveTab] = useState('sample')
  const [record, setRecord] = useState<ParseRecord>()
  const [parsing, setParsing] = useState(false)
  const [parseSteps, setParseSteps] = useState<Array<{ title: string; status: string }>>([])
  const [ocrText, setOcrText] = useState('')
  const [importedTicketId, setImportedTicketId] = useState<string>()
  const [inspectionResult, setInspectionResult] = useState<PilotWorkflowResult>()

  const { data: sampleData, isLoading } = useQuery({
    queryKey: ['ticket-samples'],
    queryFn: async () => (await fetchSamples()).data,
  })

  const selectedSample = useMemo(
    () => sampleData?.samples.find((sample: SampleTicket) => sample.id === sampleId),
    [sampleData?.samples, sampleId],
  )

  const startParse = () => {
    setParsing(true)
    setRecord(undefined)
    setParseSteps([])
    setOcrText('')
    setImportedTicketId(undefined)
    setInspectionResult(undefined)
    const payload = activeTab === 'sample' ? { sampleId } : activeTab === 'image' ? { text, file } : { text }
    parseTicketStream(
      payload,
      (event) => {
        if (event.type === 'step') {
          setParseSteps((items) => {
            const next = [...items]
            next[event.index] = { title: event.title, status: event.status }
            return next.filter(Boolean)
          })
        }
        if (event.type === 'ocr' || event.type === 'pdf') {
          setOcrText(event.text || '')
        }
        if (event.type === 'final') {
          setRecord(event.record)
          if (event.record?.ocr_result?.text) setOcrText(event.record.ocr_result.text)
          if (event.record?.pdf_result?.text) setOcrText(event.record.pdf_result.text)
          saveLatest(event.record)
        }
        if (event.type === 'error') {
          message.error(event.message || '解析失败')
        }
      },
      () => {
        setParsing(false)
        message.success('解析完成')
      },
      (err) => {
        setParsing(false)
        message.error(err)
      },
    )
  }


  const importMutation = useMutation({
    mutationFn: importParsedTicket,
    onSuccess: ({ data }) => {
      if (data.ticket?.id) setImportedTicketId(data.ticket.id)
      message.success(data.message || (data.created ? '作业票已入库' : '作业票已在库中'))
    },
    onError: () => message.error('作业票入库失败'),
  })

  const fullInspectionMutation = useMutation({
    mutationFn: runFullInspection,
    onSuccess: ({ data }) => {
      setInspectionResult(data)
      if (data.ticket?.id) setImportedTicketId(data.ticket.id)
      message.success('无计划作业检查已完成')
    },
    onError: () => message.error('无计划作业检查启动失败'),
  })

  const canImport = !!record && record.source_type !== 'database'

  const fact = record?.ticket_fact

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>作业票解析</h1></div>

      <div className="two-col parser-layout">
        <div className="panel">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'sample',
                label: '数据库作业票',
                children: (
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    <Select
                      showSearch
                      loading={isLoading}
                      placeholder="选择作业票"
                      style={{ width: '100%' }}
                      value={sampleId}
                      optionFilterProp="label"
                      onChange={(value) => {
                        setSampleId(value)
                        const next = sampleData?.samples.find((item) => item.id === value)
                        setText(next?.raw_text || '')
                      }}
                      options={(sampleData?.samples || []).map((sample) => ({ value: sample.id, label: sample.name }))}
                    />
                    <TextArea rows={14} value={selectedSample?.raw_text || text} onChange={(event) => setText(event.target.value)} />
                  </Space>
                ),
              },
              {
                key: 'text',
                label: '文本录入',
                children: <TextArea rows={17} value={text} onChange={(event) => setText(event.target.value)} />,
              },
              {
                key: 'image',
                label: '图片/PDF识别',
                children: (
                  <Dragger
                    accept="image/*,.pdf,application/pdf"
                    maxCount={1}
                    beforeUpload={(nextFile) => {
                      setFile(nextFile)
                      return false
                    }}
                    onRemove={() => setFile(undefined)}
                  >
                    <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                    <p className="ant-upload-text">上传作业票图片或PDF</p>
                  </Dragger>
                ),
              },
            ]}
          />
          <Divider />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            block
            loading={parsing}
            onClick={startParse}
          >
            开始解析
          </Button>
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">解析结果</div>
            <Space>
              {record && <Tag color={record.validation_result.requires_human_review ? 'orange' : 'green'}>置信度 {record.validation_result.confidence}</Tag>}
              {canImport && (
                <Button
                  size="small"
                  type={importedTicketId ? 'default' : 'primary'}
                  icon={<DatabaseOutlined />}
                  loading={importMutation.isPending}
                  disabled={!!importedTicketId}
                  onClick={() => record && importMutation.mutate(record)}
                >
                  {importedTicketId ? '已入库' : '作业票入库'}
                </Button>
              )}
              {record && (
                <Button
                  size="small"
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={fullInspectionMutation.isPending}
                  onClick={() => record && fullInspectionMutation.mutate({ record, operator: '系统自动检查', mode: 'parse_to_full_check' })}
                >
                  发起无计划检查
                </Button>
              )}
            </Space>
          </div>

          {!record && parseSteps.length === 0 && <div className="empty-state">暂无解析结果</div>}
          {!record && parseSteps.length > 0 && (
            <Steps direction="vertical" size="small" current={Math.max(0, parseSteps.length - 1)} items={parseSteps.map((item) => ({ title: item.title, status: item.status === 'done' ? 'finish' : 'process' }))} />
          )}

          {record && fact && (
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Steps size="small" current={record.agent_trace.length - 1} items={record.agent_trace.map((item) => ({ title: item.name }))} />
              {((record.source_type === 'image_ocr' || record.source_type === 'pdf') || ocrText) && (
                <div className="ocr-result-box">
                  <div className="ocr-result-head">
                    <span>文件识别文本</span>
                    <Tag color={(record.pdf_result?.success ?? record.ocr_result?.success) ? 'green' : 'orange'}>{record.pdf_result?.engine || record.ocr_result?.engine || '本地识别'}</Tag>
                  </div>
                  <TextArea rows={6} value={record.pdf_result?.text || record.ocr_result?.text || ocrText || record.raw_text || ''} readOnly />
                  {record.pdf_result?.page_count ? <div className="ocr-error">PDF页数：{record.pdf_result.page_count}</div> : null}
                  {(record.pdf_result?.error || record.ocr_result?.error) && <div className="ocr-error">{record.pdf_result?.error || record.ocr_result?.error}</div>}
                </div>
              )}
              {record.validation_result.warnings.length > 0 && (
                <Alert type="warning" showIcon message={record.validation_result.warnings.join('；')} />
              )}
              {fact.source_consistency?.matched === false && (
                <Alert type="warning" showIcon message={fact.source_consistency.message || '上传文件名与票面标题不一致'} />
              )}
              <Descriptions bordered size="small" column={2} className="professional-desc">
                <Descriptions.Item label="上传文件">{fact.source_file_name || record.pdf_result?.filename || record.ocr_result?.filename || '无'}</Descriptions.Item>
                <Descriptions.Item label="票面标题">{fact.ticket_title || '待识别'}</Descriptions.Item>
                <Descriptions.Item label="作业票编号">{fact.ticket_no || fact.plan_id || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="行政区">{fact.district || '广州'}</Descriptions.Item>
                <Descriptions.Item label="项目名称" span={2}>{fact.project_name}</Descriptions.Item>
                <Descriptions.Item label="计划状态">{fact.plan_status}</Descriptions.Item>
                <Descriptions.Item label="执行状态">{fact.execution_status}</Descriptions.Item>
                <Descriptions.Item label="风险等级">{fact.risk_level}</Descriptions.Item>
                <Descriptions.Item label="负责人">{fact.work_leader || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="作业地点" span={2}>{fact.work_location || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="计划时间" span={2}>{fact.plan_time_range.start || '待补充'} 至 {fact.plan_time_range.end || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="停电配合">{fact.requires_power_outage === true ? '是' : fact.requires_power_outage === false ? '否' : '待确认'}</Descriptions.Item>
                <Descriptions.Item label="运行区域/邻电">{fact.in_running_area_or_near_electric === true ? '是' : fact.in_running_area_or_near_electric === false ? '否' : '待确认'}</Descriptions.Item>
                <Descriptions.Item label="现场人数">{fact.person_count ?? '未识别'}</Descriptions.Item>
                <Descriptions.Item label="视频管控">{fact.video_control_enabled ? '是' : '否'}</Descriptions.Item>
                <Descriptions.Item label="施工方案" span={2}>{fact.construction_plan_name || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="作业摘要" span={2}>{fact.work_content_summary || '待生成'}</Descriptions.Item>
                <Descriptions.Item label="作业内容" span={2}>{fact.work_content_raw}</Descriptions.Item>
              </Descriptions>

              <div className="tag-row">
                {fact.normalized_work_types.map((item) => <Tag color="blue" key={item}>{cnWorkType(item)}</Tag>)}
                {fact.scene_tags.map((item) => <Tag color="green" key={item}>{item}</Tag>)}
                {(fact.main_hazards || []).map((item) => <Tag color="orange" key={item}>{item}</Tag>)}
                {(fact.work_actions || []).map((item) => <Tag color="purple" key={item}>{item}</Tag>)}
                {(fact.special_operations || []).map((item) => <Tag color="red" key={item}>{item}</Tag>)}
              </div>

              {(fact.risk_control_measures || []).length > 0 && (
                <Table
                  size="small"
                  rowKey={(row: Record<string, any>, index) => `${row.risk_name}-${index}`}
                  pagination={false}
                  dataSource={(fact.risk_control_measures || []) as Array<Record<string, any>>}
                  columns={[
                    { title: '风险名称', dataIndex: 'risk_name', width: 180 },
                    { title: '控制措施', dataIndex: 'control_measure' },
                  ]}
                />
              )}

              {(fact.site_assessment_items || []).length > 0 && (
                <Table
                  size="small"
                  rowKey={(row: Record<string, any>, index) => `${row.category}-${index}`}
                  pagination={{ pageSize: 8, size: 'small' }}
                  dataSource={(fact.site_assessment_items || []) as Array<Record<string, any>>}
                  columns={[
                    { title: '场景要素', dataIndex: 'category', width: 110 },
                    { title: '勘察项', dataIndex: 'question' },
                    { title: '票面结果', dataIndex: 'answer', width: 90, render: (value) => <Tag color={value === '是' ? 'green' : 'default'}>{value}</Tag> },
                  ]}
                />
              )}

              {fact.personnel_approval && (
                <Descriptions bordered size="small" column={2} className="professional-desc">
                  <Descriptions.Item label="现场负责人">{fact.personnel_approval.site_work_leader || '待补充'}</Descriptions.Item>
                  <Descriptions.Item label="安全监护人">{fact.personnel_approval.safety_guardian || '待补充'}</Descriptions.Item>
                  <Descriptions.Item label="特种作业人员" span={2}>{fact.personnel_approval.special_workers || '待补充'}</Descriptions.Item>
                  <Descriptions.Item label="一般施工人员" span={2}>{fact.personnel_approval.general_workers || '待补充'}</Descriptions.Item>
                </Descriptions>
              )}

              {record.agent_analysis && (
                <div className="agent-analysis">
                  <div className="agent-analysis-head">
                    <span>{record.agent_analysis.agent_name || '作业票入库分析智能体'}</span>
                    <Tag color={record.agent_analysis.review_required ? 'orange' : 'green'}>{record.agent_analysis.risk_judgement}</Tag>
                  </div>
                  <div className="agent-analysis-body">
                    {(record.agent_analysis.key_findings || []).map((item) => <div key={item}>• {item}</div>)}
                    <div>• {record.agent_analysis.dispatch_suggestion}</div>
                    {(record.agent_analysis.inspection_rules || []).slice(0, 3).map((item) => <div key={item}>• {item}</div>)}
                  </div>
                </div>
              )}

              <Table
                size="small"
                rowKey={(row: Record<string, any>) => row.camera_id || row.media_id}
                pagination={false}
                dataSource={(record.media_query_task.arguments?.candidate_cameras || []) as Array<Record<string, any>>}
                columns={[
                  { title: '候选设备', dataIndex: 'camera_name' },
                  { title: '设备ID', dataIndex: 'camera_id', width: 160 },
                  { title: '距离', dataIndex: 'distance_m', width: 90, render: (value) => `${value}m` },
                ]}
              />

              {inspectionResult && (
                <div className="full-check-result">
                  <Divider />
                  <div className="panel-toolbar">
                    <div className="panel-title">无计划作业检查结果</div>
                    <Tag color={riskColor[inspectionResult.violation_result.risk_level] || 'default'}>{inspectionResult.violation_result.conclusion}</Tag>
                  </div>
                  <Space wrap size={16} style={{ marginBottom: 12 }}>
                    <Statistic title="现场快照" value={inspectionResult.media_manifest.length} />
                    <Statistic title="视觉帧" value={inspectionResult.vision_result.frame_count} />
                    <Statistic title="异常事件" value={inspectionResult.violation_result.anomaly_count} />
                    <Statistic title="命中规则" value={(inspectionResult.violation_result.matched_rules || []).length} />
                  </Space>
                  <Image.PreviewGroup>
                    <div className="media-grid pilot-media-grid compact-grid">
                      {inspectionResult.media_manifest.slice(0, 10).map((frame) => (
                        <div className="media-card" key={frame.media_id}>
                          <Image src={frame.thumbnail_path} alt={frameLabel(frame)} height={104} width="100%" style={{ objectFit: 'cover' }} />
                          <div className="media-meta"><span>{frameLabel(frame)}</span><span>{frame.capture_time.slice(11, 16)}</span></div>
                        </div>
                      ))}
                    </div>
                  </Image.PreviewGroup>
                  <Table
                    size="small"
                    rowKey={(row: Record<string, any>) => row.dimension}
                    pagination={false}
                    dataSource={(inspectionResult.violation_result.dimension_comparison || []) as Array<Record<string, any>>}
                    columns={[
                      { title: '维度', dataIndex: 'dimension', width: 92 },
                      { title: '票面要求', dataIndex: 'plan', ellipsis: true },
                      { title: '现场识别', dataIndex: 'vision', ellipsis: true },
                      { title: '结论', dataIndex: 'result', width: 88, render: (value) => <Tag color={value === '不匹配' ? 'red' : value === '匹配' ? 'green' : 'orange'}>{value}</Tag> },
                    ]}
                  />
                  <List
                    size="small"
                    header={<b>命中规则</b>}
                    dataSource={(inspectionResult.violation_result.matched_rules || []) as Array<Record<string, any>>}
                    renderItem={(item) => <List.Item><Tag color={item.severity === '高' ? 'red' : 'orange'}>{item.id}</Tag>{item.name}：{item.condition}</List.Item>}
                  />
                  <Table
                    size="small"
                    rowKey={(row: Record<string, any>, index) => `${row.rule_id}-${index}`}
                    pagination={false}
                    dataSource={(inspectionResult.violation_result.anomalies || []) as Array<Record<string, any>>}
                    columns={[
                      { title: '等级', dataIndex: 'level', width: 72, render: (value) => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
                      { title: '规则', dataIndex: 'rule_name', width: 150 },
                      { title: '片段', dataIndex: 'frame_range', width: 150 },
                      { title: '说明', dataIndex: 'description' },
                    ]}
                  />
                </div>
              )}
            </Space>
          )}
        </div>
      </div>
    </div>
  )
}
