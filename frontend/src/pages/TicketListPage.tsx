
import { Input, Select, Space, Table, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchTickets } from '../api'

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const statusColor: Record<string, string> = { 待开工: 'gold', 开工中: 'blue', 已完工: 'default' }

export default function TicketListPage() {
  const [status, setStatus] = useState<string>()
  const [keyword, setKeyword] = useState('')
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
          ]}
        />
      </div>
    </div>
  )
}
