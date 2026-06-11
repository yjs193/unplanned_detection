
import { Button, Descriptions, Input, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchTickets } from '../api'
import type { WorkTicket } from '../types'

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const statusColor: Record<string, string> = { 待开工: 'gold', 开工中: 'blue', 已完工: 'default' }

const { Paragraph } = Typography

function joinValues(values?: unknown[]) {
  return Array.isArray(values) && values.length ? values.filter(Boolean).join('、') : '待识别'
}

export default function TicketListPage() {
  const [status, setStatus] = useState<string>()
  const [keyword, setKeyword] = useState('')
  const [selectedTicket, setSelectedTicket] = useState<WorkTicket | null>(null)
  const { data, isLoading } = useQuery({
    queryKey: ['tickets', status, keyword],
    queryFn: async () => (await fetchTickets({ page: 1, page_size: 100, status, keyword })).data,
  })

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>作业票查看</h1></div>
      <div className="panel">
        <div className="table-filters">
          <Space>
            <Select allowClear placeholder="计划状态" style={{ width: 160 }} value={status} onChange={setStatus} options={['待开工', '开工中', '已完工'].map((item) => ({ value: item, label: item }))} />
            <Input.Search placeholder="计划编号、项目或地点" allowClear style={{ width: 280 }} onSearch={setKeyword} onChange={(event) => !event.target.value && setKeyword('')} />
          </Space>
          <span className="table-total">共 {data?.total || 0} 条</span>
        </div>
        <Table
          rowKey={(row) => row.id}
          loading={isLoading}
          dataSource={data?.items || []}
          pagination={{ pageSize: 12 }}
          columns={[
            { title: '计划编号', dataIndex: 'plan_id', width: 160, ellipsis: true },
            { title: '项目名称', dataIndex: 'project_name', ellipsis: true },
            { title: '行政区', dataIndex: 'district', width: 130 },
            { title: '作业地点', dataIndex: 'work_location', width: 180, ellipsis: true },
            { title: '计划状态', dataIndex: 'plan_status', width: 120, render: (value) => <Tag color={statusColor[value] || 'default'}>{value}</Tag> },
            { title: '风险', dataIndex: 'risk_level', width: 90, render: (value) => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
            { title: '视频管控', dataIndex: 'video_control_enabled', width: 110, render: (value) => <Tag color={value ? 'green' : 'default'}>{value ? '是' : '否'}</Tag> },
            { title: '负责人', dataIndex: 'work_leader', width: 100 },
            { title: '更新时间', dataIndex: 'updated_at', width: 170 },
            {
              title: '操作',
              width: 116,
              align: 'center',
              render: (_, row) => (
                <Button type="link" icon={<EyeOutlined />} className="table-action-link" onClick={() => setSelectedTicket(row)}>
                  查看详情
                </Button>
              ),
            },
          ]}
        />
      </div>
      <Modal
        title="作业票详情"
        open={!!selectedTicket}
        onCancel={() => setSelectedTicket(null)}
        footer={null}
        width={880}
        destroyOnClose
        centered
      >
        {selectedTicket && (
          <div className="ticket-detail-drawer">
            <div className="summary-box ticket-detail-head">
              <div className="summary-title">{selectedTicket.ticket_title || selectedTicket.project_name}</div>
              <div className="summary-meta">{selectedTicket.plan_id}｜{selectedTicket.district || '未填区域'}｜{selectedTicket.work_location || '未填地点'}</div>
              <Space wrap style={{ marginTop: 10 }}>
                <Tag color={statusColor[selectedTicket.plan_status] || 'default'}>{selectedTicket.plan_status}</Tag>
                <Tag color={riskColor[selectedTicket.risk_level] || 'default'}>{selectedTicket.risk_level || '未定级'}</Tag>
                <Tag color={selectedTicket.video_control_enabled ? 'green' : 'default'}>{selectedTicket.video_control_enabled ? '已纳入视频管控' : '未纳入视频管控'}</Tag>
              </Space>
            </div>

            <Descriptions bordered size="small" column={2} className="professional-desc">
              <Descriptions.Item label="作业票编号">{selectedTicket.ticket_no || selectedTicket.plan_id}</Descriptions.Item>
              <Descriptions.Item label="行政区">{selectedTicket.district || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="工程名称" span={2}>{selectedTicket.project_name}</Descriptions.Item>
              <Descriptions.Item label="施工单位" span={2}>{selectedTicket.contractor || selectedTicket.ticket_fact?.contractor || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="工作负责人">{selectedTicket.work_leader || selectedTicket.ticket_fact?.work_leader || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="执行状态">{selectedTicket.execution_status || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="计划开始">{selectedTicket.plan_start || selectedTicket.ticket_fact?.plan_time_range?.start || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="计划结束">{selectedTicket.plan_end || selectedTicket.ticket_fact?.plan_time_range?.end || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="作业地点" span={2}>{selectedTicket.work_location || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="作业内容" span={2}>{selectedTicket.work_content_raw || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="作业动作" span={2}>{joinValues(selectedTicket.ticket_fact?.work_actions)}</Descriptions.Item>
              <Descriptions.Item label="作业对象" span={2}>{joinValues(selectedTicket.ticket_fact?.equipment_targets)}</Descriptions.Item>
              <Descriptions.Item label="主要危害" span={2}>{joinValues(selectedTicket.ticket_fact?.main_hazards)}</Descriptions.Item>
              <Descriptions.Item label="施工方案" span={2}>{selectedTicket.ticket_fact?.construction_plan_name || '待补充'}</Descriptions.Item>
            </Descriptions>

            <div className="ticket-detail-section">
              <div className="panel-title small">风险控制措施</div>
              {selectedTicket.ticket_fact?.risk_control_measures?.length ? (
                <Table
                  size="small"
                  rowKey={(_, index) => String(index)}
                  pagination={false}
                  dataSource={selectedTicket.ticket_fact.risk_control_measures}
                  columns={[
                    { title: '风险名称', dataIndex: 'risk_name', width: 160 },
                    { title: '控制措施', dataIndex: 'control_measure' },
                  ]}
                />
              ) : (
                <div className="empty-state compact">暂无结构化风险控制措施</div>
              )}
            </div>

            <div className="ticket-detail-section">
              <div className="panel-title small">智能体分析</div>
              {selectedTicket.agent_analysis ? (
                <div className="agent-analysis">
                  <div className="agent-analysis-head">
                    <span>{selectedTicket.agent_analysis.agent_name || '作业票入库分析智能体'}</span>
                    <Tag color={selectedTicket.agent_analysis.risk_judgement === '重点跟踪' ? 'orange' : 'blue'}>{selectedTicket.agent_analysis.risk_judgement || '常规检查'}</Tag>
                  </div>
                  <div className="agent-analysis-body">
                    {(selectedTicket.agent_analysis.key_findings || []).map((item: string, index: number) => (
                      <Paragraph key={`${index}-${item}`}>{item}</Paragraph>
                    ))}
                    {selectedTicket.agent_analysis.dispatch_suggestion && <Paragraph>调度建议：{selectedTicket.agent_analysis.dispatch_suggestion}</Paragraph>}
                  </div>
                </div>
              ) : (
                <div className="empty-state compact">暂无智能体分析结果</div>
              )}
            </div>

            <div className="ticket-detail-section">
              <div className="panel-title small">结构化结果</div>
              <pre className="json-preview">{JSON.stringify({
                ticket_fact: selectedTicket.ticket_fact,
                media_query_task: selectedTicket.media_query_task,
                validation_result: selectedTicket.validation_result,
              }, null, 2)}</pre>
            </div>

            <div className="ticket-detail-section">
              <div className="panel-title small">票面原文</div>
              <pre className="json-preview">{selectedTicket.raw_text || '暂无原文'}</pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
