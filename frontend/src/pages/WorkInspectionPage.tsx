
import { Alert, Button, Divider, Image, List, Select, Space, Table, Tag, Timeline, message } from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchInspections, fetchTickets, startInspection } from '../api'
import type { InspectionRecord, PilotWorkflowResult, WorkTicket } from '../types'

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const frameLabel = (row: Record<string, any>) => row.display_label || `第${String(row.minute_index || String(row.media_id || '').match(/(\d+)$/)?.[1] || '').padStart(2, '0')}帧`

export default function WorkInspectionPage() {
  const [ticketId, setTicketId] = useState<string>()
  const [inspection, setInspection] = useState<InspectionRecord>()
  const [fullResult, setFullResult] = useState<PilotWorkflowResult>()

  const { data: ticketData, isLoading: loadingTickets, refetch: refetchTickets } = useQuery({
    queryKey: ['active-work-tickets'],
    queryFn: async () => (await fetchTickets({ page: 1, page_size: 100, status: '开工中' })).data,
  })

  const { data: inspectionData, refetch: refetchInspections } = useQuery({
    queryKey: ['inspections'],
    queryFn: async () => (await fetchInspections()).data,
  })

  const selectedTicket = useMemo(
    () => ticketData?.items.find((item: WorkTicket) => item.id === ticketId),
    [ticketData?.items, ticketId],
  )

  const inspectMutation = useMutation({
    mutationFn: startInspection,
    onSuccess: ({ data }) => {
      setInspection(data.inspection)
      setFullResult((data as any).result)
      refetchInspections()
      message.success('作业检查已发起')
    },
    onError: () => message.error('发起检查失败'),
  })

  const mediaPreview = inspection?.media_manifest.slice(0, 30) || []
  const violation = fullResult?.violation_result || (inspection as any)?.violation_result
  const vision = fullResult?.vision_result || (inspection as any)?.vision_result

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>作业检查demo</h1>
        <Button icon={<ReloadOutlined />} onClick={() => { refetchTickets(); refetchInspections() }}>刷新</Button>
      </div>

      <div className="two-col inspection-layout">
        <div className="panel">
          <div className="panel-title">开工中作业票</div>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Select
              showSearch
              loading={loadingTickets}
              placeholder="选择开工中的作业票"
              optionFilterProp="label"
              value={ticketId}
              onChange={setTicketId}
              options={(ticketData?.items || []).map((item) => ({
                value: item.id,
                label: `${item.plan_id}｜${item.district}｜${item.work_location}`,
              }))}
              style={{ width: '100%' }}
            />
            {selectedTicket ? (
              <div className="summary-box">
                <div className="summary-title">{selectedTicket.project_name}</div>
                <div className="summary-meta">{selectedTicket.district}｜{selectedTicket.work_location}</div>
                <Space wrap style={{ marginTop: 10 }}>
                  <Tag color="blue">{selectedTicket.plan_id}</Tag>
                  <Tag color="cyan">{selectedTicket.plan_status}</Tag>
                  <Tag color={riskColor[selectedTicket.risk_level] || 'default'}>{selectedTicket.risk_level}</Tag>
                  <Tag color={selectedTicket.video_control_enabled ? 'green' : 'default'}>{selectedTicket.video_control_enabled ? '视频管控' : '未纳入视频管控'}</Tag>
                </Space>
                <div className="summary-work-content">{selectedTicket.work_content_raw}</div>
              </div>
            ) : (
              <div className="empty-state compact">请选择一张开工中作业票</div>
            )}
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              block
              loading={inspectMutation.isPending}
              disabled={!selectedTicket}
              onClick={() => selectedTicket && inspectMutation.mutate({ ticket_id: selectedTicket.id, operator: '系统自动检查', mode: 'manual' })}
            >
              发起作业检查
            </Button>
          </Space>

          {inspection && (
            <>
              <Divider />
              <div className="panel-title small">检查进度</div>
              <Timeline items={inspection.timeline.map((item) => ({ children: `${item.time} ${item.event}` }))} />
              <Alert type={inspection.media_manifest.length ? 'info' : 'warning'} showIcon message={inspection.report.conclusion} />
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">现场画面</div>
            {inspection && <Tag color="blue">共 {inspection.media_manifest.length} 张</Tag>}
          </div>
          {inspection && inspection.media_manifest.length > 0 ? (
            <>
              <Image.PreviewGroup>
                <div className="media-grid">
                  {mediaPreview.map((frame) => (
                    <div className="media-card" key={frame.media_id}>
                      <Image src={frame.thumbnail_path} alt={frameLabel(frame)} height={112} width="100%" style={{ objectFit: 'cover' }} />
                      <div className="media-meta">
                        <span>{frameLabel(frame)}</span>
                        <span>{frame.capture_time.slice(11, 16)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Image.PreviewGroup>
              <Divider />
              <List size="small" header={<b>自动检查步骤</b>} dataSource={inspection.report.next_actions} renderItem={(item) => <List.Item>{item}</List.Item>} />
              {vision && violation && (
                <>
                  <Divider />
                  <Space wrap size={16} style={{ marginBottom: 12 }}>
                    <Tag color="blue">视觉帧 {vision.frame_count}</Tag>
                    <Tag color={riskColor[violation.risk_level] || 'default'}>{violation.conclusion}</Tag>
                    <Tag color="orange">异常事件 {violation.anomaly_count}</Tag>
                  </Space>
                  <Table
                    size="small"
                    rowKey={(row: Record<string, any>) => row.dimension}
                    pagination={false}
                    dataSource={(violation.dimension_comparison || []) as Array<Record<string, any>>}
                    columns={[
                      { title: '维度', dataIndex: 'dimension', width: 90 },
                      { title: '票面要求', dataIndex: 'plan', ellipsis: true },
                      { title: '现场识别', dataIndex: 'vision', ellipsis: true },
                      { title: '结论', dataIndex: 'result', width: 86, render: (value) => <Tag color={value === '不匹配' ? 'red' : value === '匹配' ? 'green' : 'orange'}>{value}</Tag> },
                    ]}
                  />
                  <List
                    size="small"
                    header={<b>命中规则</b>}
                    dataSource={(violation.matched_rules || []) as Array<Record<string, any>>}
                    renderItem={(item) => <List.Item><Tag color={item.severity === '高' ? 'red' : 'orange'}>{item.id}</Tag>{item.name}</List.Item>}
                  />
                </>
              )}
            </>
          ) : (
            <div className="empty-state">发起检查后展示近30分钟现场画面</div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">检查记录</div>
        <Table
          size="middle"
          rowKey={(row) => row.id}
          dataSource={inspectionData?.items || []}
          pagination={{ pageSize: 8 }}
          onRow={(row) => ({ onClick: () => setInspection(row) })}
          columns={[
            { title: '任务编号', dataIndex: 'id', width: 140 },
            { title: '计划编号', dataIndex: 'ticket', width: 170, ellipsis: true },
            { title: '作业地点', dataIndex: 'location', ellipsis: true },
            { title: '状态', dataIndex: 'status', width: 130, render: (value) => <Tag color={value === '等待视觉比对' ? 'blue' : 'default'}>{value}</Tag> },
            { title: '风险', dataIndex: 'risk', width: 80, render: (value) => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
            { title: '画面', dataIndex: 'media_manifest', width: 90, render: (value) => `${value?.length || 0}张` },
            { title: '更新时间', dataIndex: 'updated_at', width: 170 },
          ]}
        />
      </div>
    </div>
  )
}
