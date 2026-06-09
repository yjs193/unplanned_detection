import { Alert, Button, Descriptions, Divider, Image, List, Progress, Space, Statistic, Steps, Table, Tag, Timeline, Tooltip, message } from 'antd'
import { ApiOutlined, CameraOutlined, CheckCircleOutlined, CloudSyncOutlined, EyeOutlined, PlayCircleOutlined, WarningOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { fetchPilotHj, runPilotHj } from '../api'
import type { PilotWorkflowResult } from '../types'

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const matchColor: Record<string, string> = { 匹配: 'green', 部分匹配: 'cyan', 需确认: 'orange', 不匹配: 'red', 待判断: 'default' }
const frameLabel = (row: Record<string, any>) => row.display_label || `第${String(row.minute_index || String(row.media_id || '').match(/(\d+)$/)?.[1] || '').padStart(2, '0')}帧`

export default function PilotWorkflowPage() {
  const [result, setResult] = useState<PilotWorkflowResult>()

  const { data: statusData, refetch } = useQuery({
    queryKey: ['pilot-hj-status'],
    queryFn: async () => (await fetchPilotHj()).data,
  })

  const runMutation = useMutation({
    mutationFn: runPilotHj,
    onSuccess: ({ data }) => {
      setResult(data)
      refetch()
      message.success('合景在线试点闭环已完成')
    },
    onError: () => message.error('合景在线试点启动失败'),
  })

  const ticket = result?.ticket || statusData?.ticket
  const fact = ticket?.ticket_fact || {}
  const mediaFrames = result?.media_manifest || []
  const visionFrames = result?.vision_result?.frames || []
  const anomalies = result?.violation_result?.anomalies || []
  const workflowStages = result?.violation_result?.workflow_stages || []
  const matchedRules = result?.violation_result?.matched_rules || []
  const dimensionRows = result?.violation_result?.dimension_comparison || []
  const rulebookSummary = result?.violation_result?.rulebook_summary
  const agentAnalysis = result?.parse_record?.agent_analysis || ticket?.agent_analysis || {}

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>合景在线试点闭环</h1>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={runMutation.isPending} onClick={() => runMutation.mutate()}>启动闭环</Button>
      </div>

      <Alert
        type="info"
        showIcon
        message="220千伏合景输变电工程在线试点"
        description="本原型演示串联作业票解析入库、近30分钟现场图片调取、视觉理解、计划-现场一致性比对和违规检测。视觉理解阶段按“目标检测/多模态模型已接入”的接口形态返回结构化结果，便于后续替换为真实模型。"
      />

      <div className="panel">
        <Steps
          current={result ? 4 : 0}
          items={[
            { title: '作业票解析入库', icon: <ApiOutlined /> },
            { title: '现场图片调取', icon: <CameraOutlined /> },
            { title: '视觉理解', icon: <EyeOutlined /> },
            { title: '违规检测', icon: <WarningOutlined /> },
            { title: '闭环记录', icon: <CheckCircleOutlined /> },
          ]}
        />
      </div>

      <div className="metric-grid">
        <div className="metric-tile"><div className="metric-label">图片样本</div><div className="metric-value">{statusData?.image_count || result?.data_sources?.length || 0}</div></div>
        <div className="metric-tile accent-green"><div className="metric-label">绑定快照</div><div className="metric-value">{mediaFrames.length}</div></div>
        <div className="metric-tile accent-orange"><div className="metric-label">视觉帧</div><div className="metric-value">{result?.vision_result?.frame_count || 0}</div></div>
        <div className="metric-tile accent-red"><div className="metric-label">异常项</div><div className="metric-value">{result?.violation_result?.anomaly_count || 0}</div></div>
      </div>

      {workflowStages.length > 0 && (
        <div className="pilot-flow-grid">
          {workflowStages.map((stage: Record<string, any>, index: number) => (
            <div className="stage-card" key={stage.name}>
              <div className="stage-index">{index + 1}</div>
              <div>
                <div className="stage-title">{stage.name}</div>
                <div className="stage-detail">{stage.detail}</div>
              </div>
              <Tag color="green">{stage.status}</Tag>
            </div>
          ))}
        </div>
      )}

      <div className="two-col pilot-layout">
        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">计划侧事实</div>
            {ticket && <Tag color="blue">{ticket.plan_id}</Tag>}
          </div>
          {ticket ? (
            <Descriptions bordered size="small" column={2} className="professional-desc">
              <Descriptions.Item label="工程名称" span={2}>{ticket.project_name}</Descriptions.Item>
              <Descriptions.Item label="计划状态">{ticket.plan_status}</Descriptions.Item>
              <Descriptions.Item label="风险等级"><Tag color={riskColor[ticket.risk_level] || 'default'}>{ticket.risk_level}</Tag></Descriptions.Item>
              <Descriptions.Item label="作业地点" span={2}>{ticket.work_location}</Descriptions.Item>
              <Descriptions.Item label="计划时间" span={2}>{ticket.plan_start} 至 {ticket.plan_end}</Descriptions.Item>
              <Descriptions.Item label="作业内容" span={2}>{ticket.work_content_raw}</Descriptions.Item>
              <Descriptions.Item label="主要危害" span={2}>{(fact.main_hazards || []).join('、') || '待识别'}</Descriptions.Item>
            </Descriptions>
          ) : <div className="empty-state compact">点击启动闭环后生成试点作业票</div>}

          {agentAnalysis?.agent_report && (
            <>
              <Divider />
              <div className="panel-title small">入库分析智能体</div>
              <div className="summary-box">
                <div className="summary-title">{agentAnalysis.risk_judgement || '计划侧理解'}</div>
                <div className="summary-meta">{agentAnalysis.agent_report}</div>
                {agentAnalysis.llm_error && <div className="ocr-error">{agentAnalysis.llm_error}</div>}
              </div>
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">现场图片调取</div>
            {result && <Tag color="cyan">近30分钟 / 全量{mediaFrames.length}张</Tag>}
          </div>
          {mediaFrames.length ? (
            <Image.PreviewGroup>
              <div className="media-grid pilot-media-grid">
                {mediaFrames.map((frame) => (
                  <div className="media-card" key={frame.media_id}>
                    <Image src={frame.thumbnail_path} alt={frameLabel(frame)} height={118} width="100%" style={{ objectFit: 'cover' }} />
                    <div className="media-meta"><span>{frameLabel(frame)}</span><span>{frame.capture_time.slice(11, 16)}</span></div>
                  </div>
                ))}
              </div>
            </Image.PreviewGroup>
          ) : <div className="empty-state">启动闭环后展示近30分钟全量快照</div>}
        </div>
      </div>

      {result && (
        <div className="two-col pilot-layout">
          <div className="panel">
            <div className="panel-toolbar">
              <div className="panel-title">视觉理解</div>
              <Tooltip title={result.vision_result.model_assumption}><Tag color="blue">{result.vision_result.model_name}</Tag></Tooltip>
            </div>
            <Alert type="warning" showIcon message="原型假设" description={result.vision_result.model_assumption} style={{ marginBottom: 12 }} />
            <Space wrap size={16} style={{ marginBottom: 12 }}>
              <Statistic title="帧数" value={result.vision_result.frame_count} />
              <Statistic title="人员观察" value={result.vision_result.aggregates.total_worker_observations || 0} />
              <Statistic title="活动类型" value={(result.vision_result.aggregates.activities || []).length} />
              <Statistic title="不一致帧" value={(result.vision_result.aggregates.unmatched_frames || []).length} />
            </Space>
            <List
              size="small"
              className="pilot-pipeline"
              dataSource={result.vision_result.inference_pipeline || []}
              renderItem={(item: Record<string, any>) => <List.Item><b>{item.stage}</b><span>{item.output}</span></List.Item>}
            />
            <Table
              size="small"
              rowKey={(row) => row.media_id}
              dataSource={visionFrames}
              pagination={{ pageSize: 8, size: 'small' }}
              columns={[
                { title: '帧', dataIndex: 'media_id', width: 105, render: (_value, row) => frameLabel(row) },
                { title: '场景理解', dataIndex: 'scene', ellipsis: true },
                { title: '人员', dataIndex: 'workers', width: 64 },
                { title: '防护装备', dataIndex: 'personal_protection', width: 150 },
                { title: '匹配', dataIndex: 'planned_match', width: 88, render: (value) => <Tag color={matchColor[value] || 'default'}>{value}</Tag> },
              ]}
              expandable={{
                expandedRowRender: (row) => (
                  <div className="vision-expand">
                    <div>{row.evidence}</div>
                    <div className="object-tags">
                      {(row.objects || []).map((item: Record<string, any>) => <Tag key={`${row.media_id}-${item.name}`}>{item.name} {Math.round((item.confidence || 0) * 100)}%</Tag>)}
                    </div>
                    <Space wrap>
                      {Object.entries(row.match_scores || {}).map(([key, value]) => <span key={key}>{key}<Progress percent={Math.round(Number(value) * 100)} size="small" style={{ width: 110 }} /></span>)}
                    </Space>
                  </div>
                ),
              }}
            />
          </div>

          <div className="panel">
            <div className="panel-toolbar">
              <div className="panel-title">违规检测</div>
              <Tag color={riskColor[result.violation_result.risk_level] || 'default'}>{result.violation_result.conclusion}</Tag>
            </div>
            <Table
              size="small"
              rowKey={(row, index) => `${row.rule_id || row.media_id}-${index}`}
              dataSource={anomalies}
              pagination={{ pageSize: 8, size: 'small' }}
              columns={[
                { title: '等级', dataIndex: 'level', width: 72, render: (value) => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
                { title: '命中规则', dataIndex: 'rule_name', width: 150, render: (value, row) => value || row.rule_id || '规则命中' },
                { title: '类型', dataIndex: 'type', width: 150 },
                { title: '片段', dataIndex: 'frame_range', width: 150, render: (value, row) => value || frameLabel(row) },
                { title: '说明', dataIndex: 'description' },
              ]}
              expandable={{ expandedRowRender: (row) => <div className="vision-expand"><div>{row.evidence}</div><div>{row.suggestion}</div>{row.count > 1 && <div>同类事件聚合：{row.count}帧</div>}</div> }}
            />
            <Divider />
            <List size="small" header={<b>检测规则</b>} dataSource={result.violation_result.rules} renderItem={(item) => <List.Item>{item}</List.Item>} />
          </div>
        </div>
      )}

      {result && (
        <div className="two-col pilot-layout">
          <div className="panel">
            <div className="panel-toolbar">
              <div className="panel-title">检测依据</div>
              {rulebookSummary && <Tag color="blue">{rulebookSummary.version}</Tag>}
            </div>
            <div className="rulebook-summary">
              <div><b>规则库</b><span>{rulebookSummary?.name || '无计划作业违规检测规则库'}</span></div>
              <div><b>通用规则</b><span>{rulebookSummary?.general_rule_count || 0} 条</span></div>
              <div><b>作业类型</b><span>{rulebookSummary?.work_type_rule_count || 0} 类</span></div>
              <div><b>本地作业票</b><span>{rulebookSummary?.source_stats?.parsed_ticket_pdf_count || 0} 份</span></div>
            </div>
            <Divider />
            <List
              size="small"
              header={<b>命中规则</b>}
              dataSource={matchedRules}
              renderItem={(item: Record<string, any>) => <List.Item><Tag color={item.severity === '高' ? 'red' : 'orange'}>{item.id}</Tag><span>{item.name}：{item.condition}</span></List.Item>}
            />
          </div>

          <div className="panel">
            <div className="panel-toolbar">
              <div className="panel-title">维度比对</div>
              <Tag color={riskColor[result.violation_result.risk_level] || 'default'}>{result.violation_result.risk_level}</Tag>
            </div>
            <Table
              size="small"
              rowKey={(row) => row.dimension}
              dataSource={dimensionRows}
              pagination={false}
              columns={[
                { title: '维度', dataIndex: 'dimension', width: 92 },
                { title: '票面要求', dataIndex: 'plan', ellipsis: true },
                { title: '现场识别', dataIndex: 'vision', ellipsis: true },
                { title: '结论', dataIndex: 'result', width: 88, render: (value) => <Tag color={value === '不匹配' ? 'red' : value === '匹配' ? 'green' : 'orange'}>{value}</Tag> },
              ]}
              expandable={{ expandedRowRender: (row) => <div className="vision-expand">{row.evidence}</div> }}
            />
          </div>
        </div>
      )}

      {result?.violation_result?.report_md && (
        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">检测报告</div>
            <Tag color={riskColor[result.violation_result.risk_level] || 'default'}>{result.violation_result.conclusion}</Tag>
          </div>
          <div className="markdown-report"><ReactMarkdown>{result.violation_result.report_md}</ReactMarkdown></div>
        </div>
      )}

      {result && (
        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">闭环记录</div>
            <Tag color={riskColor[result.inspection.risk] || 'default'}>{result.inspection.status}</Tag>
          </div>
          <Timeline items={result.inspection.timeline.map((item) => ({ children: `${item.time} ${item.event}` }))} />
        </div>
      )}

      <div className="panel">
        <div className="panel-toolbar">
          <div className="panel-title">图片数据来源</div>
          <CloudSyncOutlined />
        </div>
        <Table
          size="small"
          rowKey={(row: Record<string, any>) => row.filename}
          dataSource={(result?.data_sources || statusData?.image_sources || []) as Array<Record<string, any>>}
          pagination={false}
          columns={[
            { title: '本地文件', dataIndex: 'filename', width: 140 },
            { title: '公开图片标题', dataIndex: 'title', ellipsis: true },
            { title: '来源页面', dataIndex: 'source_page', render: (value) => <a href={value} target="_blank" rel="noreferrer">查看来源</a>, width: 120 },
          ]}
        />
      </div>
    </div>
  )
}
