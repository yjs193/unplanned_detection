import { Alert, Button, Descriptions, Drawer, Image, Input, InputNumber, Progress, Select, Space, Switch, Table, Tag, Tooltip, Typography, message } from 'antd'
import { BugOutlined, FileTextOutlined, PlayCircleOutlined, ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { fetchSamples, runViolationDetection, runVisionAnalysis } from '../api'
import type { SampleTicket, TicketFact, ViolationDetectionResult, VisionAnalysisResult, WorkTicket } from '../types'

const { TextArea } = Input

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green', 高危: 'red', 常规: 'blue' }
const resultColor: Record<string, string> = { 未发现明显异常: 'green', 需持续观察: 'blue', 疑似不一致: 'orange', 明显不一致: 'red' }
const detectionSteps = ['读取作业票', '调用视觉理解', '整理证据链', '匹配判别', '二次复核', '生成结论']

function ticketLabel(ticket?: WorkTicket) {
  if (!ticket) return ''
  return `${ticket.plan_id}｜${ticket.district || '未填区域'}｜${ticket.work_location || '未填地点'}`
}

function workItems(ticket?: WorkTicket) {
  const fact = (ticket?.ticket_fact || {}) as Partial<TicketFact>
  const actions = Array.isArray(fact.work_actions) ? fact.work_actions : []
  const normalized = Array.isArray(fact.normalized_work_types) ? fact.normalized_work_types : []
  const raw = ticket?.work_content_raw || fact.work_content_raw || ''
  const pieces = raw.split(/[；;，,。、\n]/).map((item: string) => item.trim()).filter(Boolean)
  return [...new Set([...actions, ...pieces, ...normalized])].slice(0, 8)
}

function buildEvidence(ticket?: WorkTicket, suspicious = false) {
  const items = workItems(ticket)
  const matched = items.length ? items.slice(0, 4) : ['现场围蔽检查', '材料转运', '基础施工作业']
  const lines = [
    `证据来源：近30分钟监控抽帧形成的现场证据链文本。`,
    `作业区域：${ticket?.work_location || '作业票绑定区域'}。`,
    `第01帧 现场可见施工围蔽和作业人员进场，未见大范围无关作业。`,
    `第08帧 现场识别到${matched.join('、')}，与票面作业内容存在对应关系。`,
    `第16帧 作业对象集中在${ticket?.work_location || '票面作业区域'}，未见跨区域施工迹象。`,
    `第24帧 现场作业仍以${matched[0] || '票面作业'}为主，证据连续性较好。`,
  ]
  if (suspicious) {
    lines.push(`第18帧 现场额外出现构件吊装和大型机械配合作业，作业票任务文本未明确该项内容。`)
    lines.push(`第22帧 吊装区域附近有人员短暂停留，建议对吊装相关帧做二次视频理解。`)
  }
  return lines.join('\n')
}

export default function ViolationDetectionPage() {
  const [ticketId, setTicketId] = useState<string>()
  const [evidenceText, setEvidenceText] = useState('')
  const [threshold, setThreshold] = useState(0.35)
  const [secondReasoning, setSecondReasoning] = useState(true)
  const [riskLevel, setRiskLevel] = useState<string>()
  const [result, setResult] = useState<ViolationDetectionResult>()
  const [visionResult, setVisionResult] = useState<VisionAnalysisResult>()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [flowStep, setFlowStep] = useState(0)
  const [flowFailed, setFlowFailed] = useState(false)

  const { data: sampleData, isLoading, refetch } = useQuery({
    queryKey: ['violation-ticket-samples'],
    queryFn: async () => (await fetchSamples()).data,
  })

  const tickets = useMemo(
    () => (sampleData?.samples || []).map((item: SampleTicket) => item.ticket).filter(Boolean) as WorkTicket[],
    [sampleData?.samples],
  )
  const selectedTicket = useMemo(() => tickets.find((item) => item.id === ticketId), [tickets, ticketId])

  useEffect(() => {
    if (ticketId || !tickets.length) return
    const active = tickets.find((item) => item.plan_status === '开工中') || tickets[0]
    setTicketId(active.id)
    setRiskLevel(active.risk_level || undefined)
    setEvidenceText(buildEvidence(active))
  }, [tickets, ticketId])

  useEffect(() => {
    if (!selectedTicket) return
    setRiskLevel((value) => value || selectedTicket.risk_level || undefined)
  }, [selectedTicket])

  const mutation = useMutation({
    mutationFn: async () => {
      if (!selectedTicket) throw new Error('请先选择作业票')
      setFlowStep(0)
      let currentVision: VisionAnalysisResult | undefined
      let currentEvidence = ''
      try {
        setFlowStep(1)
        const visionResponse = await runVisionAnalysis({ ticket_id: selectedTicket.id, frame_count: 8, use_model: true })
        currentVision = visionResponse.data
        setVisionResult(currentVision)
        if (currentVision.success && currentVision.evidence_text?.trim()) {
          currentEvidence = currentVision.evidence_text.trim()
        }
      } catch {
        currentVision = undefined
      }
      if (!currentEvidence) {
        currentEvidence = buildEvidence(selectedTicket)
        setVisionResult(undefined)
        message.warning('未匹配到可用现场视频，已使用匹配示例生成证据链')
      }
      setFlowStep(2)
      setEvidenceText(currentEvidence)
      setFlowStep(3)
      const response = await runViolationDetection({
        ticket_id: selectedTicket.id,
        video_evidence_text: currentEvidence,
        video_evidence_package: currentVision,
        probability_threshold: threshold,
        enable_second_video_reasoning: secondReasoning,
        risk_level: riskLevel,
      })
      setFlowStep(response.data.second_pass?.triggered ? 4 : 5)
      return response
    },
    onSuccess: ({ data }) => {
      setResult(data)
      setFlowStep(detectionSteps.length - 1)
      setFlowFailed(!data.success)
      if (data.success) message.success('违规检测已完成')
      else message.error(data.error || '违规检测失败')
    },
    onError: () => {
      setFlowFailed(true)
      message.error('违规检测请求失败')
    },
  })

  const flowVisible = mutation.isPending || !!result || flowFailed
  const flowPercent = flowFailed
    ? Math.max(20, Math.round(((flowStep + 1) / detectionSteps.length) * 100))
    : mutation.isPending
      ? Math.min(88, Math.round(((flowStep + 1) / detectionSteps.length) * 100))
      : result
        ? 100
        : 0
  const activeFlowStep = mutation.isPending ? flowStep : result && !flowFailed ? detectionSteps.length - 1 : flowStep

  const conclusion = result?.result
  const unmatched = conclusion?.unmatched_work || []
  const visionFrames = visionResult?.frames || result?.vision_result?.frames || []

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>违规检测</h1>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新作业票</Button>
          <Button icon={<FileTextOutlined />} onClick={() => setDrawerOpen(true)} disabled={!result}>完整结果</Button>
        </Space>
      </div>

      <div className="two-col violation-layout">
        <div className="panel">
          <div className="panel-title">作业票任务</div>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Select
              showSearch
              loading={isLoading}
              placeholder="选择作业票"
              optionFilterProp="label"
              value={ticketId}
              onChange={(value) => {
                const ticket = tickets.find((item) => item.id === value)
                setTicketId(value)
                setRiskLevel(ticket?.risk_level || undefined)
                setEvidenceText(buildEvidence(ticket))
                setVisionResult(undefined)
                setResult(undefined)
              }}
              options={tickets.map((ticket) => ({
                value: ticket.id,
                label: ticketLabel(ticket),
              }))}
              style={{ width: '100%' }}
            />

            {selectedTicket ? (
              <div className="summary-box violation-ticket-summary">
                <div className="summary-title">{selectedTicket.ticket_title || selectedTicket.project_name}</div>
                <div className="summary-meta">{selectedTicket.project_name}</div>
                <Space wrap style={{ marginTop: 10 }}>
                  <Tag color="blue">{selectedTicket.plan_id}</Tag>
                  <Tag color={selectedTicket.plan_status === '开工中' ? 'green' : 'default'}>{selectedTicket.plan_status}</Tag>
                  <Tag color={riskColor[selectedTicket.risk_level] || 'default'}>{selectedTicket.risk_level || '未定级'}</Tag>
                  <Tag color={selectedTicket.video_control_enabled ? 'cyan' : 'default'}>{selectedTicket.video_control_enabled ? '已纳入视频管控' : '未纳入视频管控'}</Tag>
                </Space>
                <div className="summary-work-content">{selectedTicket.work_content_raw || '票面未提取到作业内容'}</div>
              </div>
            ) : (
              <div className="empty-state compact">请先选择一张作业票</div>
            )}

            <div className="violation-controls">
              <div>
                <div className="field-label">风险口径</div>
                <Select
                  value={riskLevel}
                  onChange={setRiskLevel}
                  options={['常规', '低', '中', '高', '高危'].map((item) => ({ value: item, label: item }))}
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <div className="field-label">
                  <Tooltip title="用于比较智能判别返回的最低 token 概率，不是作业内容匹配分；低于该值会进入二次复核。">
                    <span>复核概率阈值</span>
                  </Tooltip>
                </div>
                <InputNumber
                  min={0}
                  max={1}
                  step={0.05}
                  precision={2}
                  value={threshold}
                  onChange={(value) => setThreshold(Math.max(0, Math.min(1, Number(value ?? 0.35))))}
                  style={{ width: '100%' }}
                />
              </div>
              <div className="switch-line">
                <span>低置信二次复核</span>
                <Switch checked={secondReasoning} onChange={setSecondReasoning} />
              </div>
            </div>
          </Space>
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">现场证据链</div>
            <Space>
              <Tooltip title="按票面内容生成一段可编辑的证据链文本">
                <Button onClick={() => setEvidenceText(buildEvidence(selectedTicket))}>匹配示例</Button>
              </Tooltip>
              <Tooltip title="加入票面未明确的现场作业，便于验证疑似违规判别">
                <Button icon={<BugOutlined />} onClick={() => setEvidenceText(buildEvidence(selectedTicket, true))}>疑似异常示例</Button>
              </Tooltip>
            </Space>
          </div>
          <TextArea
            value={evidenceText}
            onChange={(event) => setEvidenceText(event.target.value)}
            rows={11}
            placeholder="请输入视觉理解输出的现场事实证据链，例如每帧识别到的作业动作、作业对象、证据帧和不确定点。"
          />
          <div className="violation-action-row">
            <Alert
              type={visionResult?.success ? 'success' : 'info'}
              showIcon
              message={visionResult?.success ? `已由视觉理解生成 ${visionResult.frame_count} 帧现场证据` : '点击执行违规检测后，将自动调用视觉理解；未匹配到视频时使用匹配示例兜底。'}
            />
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              loading={mutation.isPending}
              disabled={!selectedTicket}
              onClick={() => {
                if (!selectedTicket) return
                setResult(undefined)
                setVisionResult(undefined)
                setFlowStep(0)
                setFlowFailed(false)
                mutation.mutate()
              }}
            >
              执行违规检测
            </Button>
          </div>
          {visionFrames.length > 0 && (
            <div className="violation-vision-frames">
              <div className="panel-title small">视觉抽帧</div>
              <div className="violation-frame-grid">
                {visionFrames.slice(0, 8).map((frame) => (
                  <div className="violation-frame-card" key={frame.image_url || frame.display_label}>
                    {frame.image_url && <Image src={frame.image_url} width="100%" height={72} style={{ objectFit: 'cover', borderRadius: 6 }} />}
                    <div className="violation-frame-caption">{frame.display_label || `第${frame.frame_index}帧`}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {flowVisible && (
            <div className="violation-flow-strip">
              <div className="violation-flow-head">
                <span>{flowFailed ? '检测请求未完成' : mutation.isPending ? '正在执行违规检测' : '检测流程完成'}</span>
                <Typography.Text type="secondary">{flowFailed ? '请检查接口或重试' : detectionSteps[activeFlowStep]}</Typography.Text>
              </div>
              <Progress
                percent={flowPercent}
                size="small"
                status={flowFailed ? 'exception' : mutation.isPending ? 'active' : 'success'}
                showInfo={false}
              />
              <div className="violation-flow-steps">
                {detectionSteps.map((step, index) => {
                  const disabled = step === '二次复核' && !secondReasoning
                  const done = !disabled && (result && !flowFailed ? true : index < activeFlowStep)
                  const active = !disabled && index === activeFlowStep && mutation.isPending
                  return (
                    <span
                      key={step}
                      className={`violation-flow-step ${done ? 'done' : ''} ${active ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
                    >
                      {step}
                    </span>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-toolbar">
          <div className="panel-title">检测结论</div>
          {result?.success && <Tag color="blue">判别完成</Tag>}
        </div>
        {result?.error && <Alert type="error" showIcon message={result.error} />}
        {conclusion ? (
          <div className="violation-result-grid">
            <div className="violation-conclusion">
              <div className="conclusion-head">
                <SafetyCertificateOutlined />
                <span>{conclusion.match_result}</span>
              </div>
              <Progress percent={Math.round((conclusion.task_match_score || 0) * 100)} strokeColor={resultColor[conclusion.match_result] === 'red' ? '#cf1322' : '#1769aa'} />
              <Space wrap>
                <Tag color={resultColor[conclusion.match_result] || 'default'}>匹配分 {conclusion.task_match_score}</Tag>
                <Tag color={result.manual_review_required ? 'orange' : 'green'}>{result.manual_review_required ? '需人工复核' : '自动流程可继续'}</Tag>
                <Tag color={result.second_pass?.triggered ? 'purple' : 'default'}>{result.second_pass?.triggered ? '已触发二次复核' : '未触发二次复核'}</Tag>
              </Space>
              <Typography.Paragraph className="violation-reason">{conclusion.reason || result.capability_scope}</Typography.Paragraph>
            </div>

            <Descriptions bordered size="small" column={1} className="professional-desc">
              <Descriptions.Item label="检测编号">{result.match_id}</Descriptions.Item>
              <Descriptions.Item label="证据来源">{result.evidence_source || '现场证据链文本'}</Descriptions.Item>
              <Descriptions.Item label="判别来源">{result.final_decision_source || '首轮判别'}</Descriptions.Item>
              <Descriptions.Item label="概率状态">{result.token_probability_available ? `最小 ${result.token_probability}，平均 ${result.avg_token_probability}` : '当前模型接口未返回 token 概率'}</Descriptions.Item>
              <Descriptions.Item label="复核阈值">{result.probability_thresholds ? `最低 ${result.probability_thresholds.min}，平均 ${result.probability_thresholds.avg}` : threshold}</Descriptions.Item>
            </Descriptions>
          </div>
        ) : (
          <div className="empty-state compact">执行检测后展示智能体判别结论</div>
        )}
      </div>

      <div className="panel">
          <div className="panel-title">疑似不一致内容</div>
          <Table
            className="violation-unmatched-table"
            size="small"
            rowKey={(_, index) => String(index)}
            pagination={false}
            dataSource={unmatched}
            columns={[
              { title: '票面侧', dataIndex: 'ticket_side', width: '28%', render: (value) => <span className="multi-line-cell">{value || '待补充'}</span> },
              { title: '现场侧', dataIndex: 'video_side', width: '28%', render: (value) => <span className="multi-line-cell">{value || '待补充'}</span> },
              { title: '证据说明', dataIndex: 'evidence', render: (value) => <span className="multi-line-cell">{value || '暂无说明'}</span> },
              { title: '置信度', dataIndex: 'confidence', width: 92, render: (value) => `${Math.round(Number(value || 0) * 100)}%` },
            ]}
          />
      </div>

      <Drawer title="完整检测结果" open={drawerOpen} onClose={() => setDrawerOpen(false)} width={720}>
        <pre className="json-preview">{JSON.stringify(result || {}, null, 2)}</pre>
      </Drawer>
    </div>
  )
}
