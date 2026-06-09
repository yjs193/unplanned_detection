
import { Button, Progress, Table, Tag } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { fetchDashboard } from '../api'

const riskColor: Record<string, string> = { 高: 'red', 中: 'orange', 低: 'green' }
const statusColor: Record<string, string> = { 待开工: 'gold', 开工中: 'blue', 已完工: 'default' }

export default function DashboardPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => (await fetchDashboard()).data,
  })

  const [themeMode, setThemeMode] = useState(document.documentElement.getAttribute('data-theme') || 'light')
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeMode(document.documentElement.getAttribute('data-theme') || 'light'))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  const isDark = themeMode === 'dark'
  const chartTextColor = isDark ? '#f8fafc' : '#344054'
  const axisLineColor = isDark ? '#3b4a60' : '#d0d5dd'
  const stats = data?.stats
  const statusOption = useMemo(() => ({
    backgroundColor: 'transparent',
    color: ['#5b7bd5', '#90c978', '#ffd166', '#f2656b', '#6ec6df'],
    textStyle: { color: chartTextColor, fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', textBorderWidth: 0, textShadowBlur: 0 },
    tooltip: { trigger: 'item', backgroundColor: isDark ? '#0f172a' : '#ffffff', borderColor: axisLineColor, textStyle: { color: chartTextColor } },
    legend: { bottom: 0, itemWidth: 14, itemHeight: 10, textStyle: { color: chartTextColor, fontSize: 13, textBorderWidth: 0, textShadowBlur: 0 } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '43%'],
      data: data?.by_status || [],
      label: { color: chartTextColor, fontSize: 14, fontWeight: 600, fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', textBorderWidth: 0, textBorderColor: 'transparent', textShadowBlur: 0 },
      labelLine: { lineStyle: { color: isDark ? '#94a3b8' : chartTextColor } },
      emphasis: { label: { textBorderWidth: 0, textShadowBlur: 0 } },
    }],
  }), [data?.by_status, chartTextColor, axisLineColor, isDark])
  const districtOption = useMemo(() => ({
    backgroundColor: 'transparent',
    textStyle: { color: chartTextColor, fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', textBorderWidth: 0, textShadowBlur: 0 },
    grid: { left: 42, right: 18, top: 16, bottom: 36 },
    tooltip: { backgroundColor: isDark ? '#0f172a' : '#ffffff', borderColor: axisLineColor, textStyle: { color: chartTextColor } },
    xAxis: { type: 'category', data: (data?.by_district || []).map((item) => item.name), axisLabel: { interval: 0, rotate: 20, color: chartTextColor, textBorderWidth: 0, textShadowBlur: 0 }, axisLine: { lineStyle: { color: axisLineColor } } },
    yAxis: { type: 'value', axisLabel: { color: chartTextColor }, splitLine: { lineStyle: { color: isDark ? '#2b3648' : '#eef2f6' } } },
    series: [{ type: 'bar', data: (data?.by_district || []).map((item) => item.value), itemStyle: { color: isDark ? '#22d3ee' : '#1769aa' }, barMaxWidth: 28 }],
  }), [data?.by_district, chartTextColor, axisLineColor, isDark])

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>仪表盘</h1>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>刷新</Button>
      </div>

      <div className="metric-grid dashboard-metrics">
        <div className="metric-tile accent-blue">
          <div className="metric-label">作业票总数</div>
          <div className="metric-value">{stats?.total_tickets ?? 0}</div>
        </div>
        <div className="metric-tile accent-red">
          <div className="metric-label">开工中作业票</div>
          <div className="metric-value">{stats?.active_tickets ?? stats?.pending_match_tickets ?? 0}</div>
        </div>
        <div className="metric-tile accent-orange">
          <div className="metric-label">高风险作业票</div>
          <div className="metric-value">{stats?.high_risk_tickets ?? 0}</div>
        </div>
        <div className="metric-tile accent-green">
          <div className="metric-label">纳入视频管控</div>
          <div className="metric-value">{stats?.video_control_tickets ?? 0}</div>
          <Progress percent={Math.round((stats?.video_control_rate ?? 0) * 100)} size="small" showInfo={false} strokeColor="#1f7a5f" />
        </div>
      </div>

      <div className="two-col dashboard-grid">
        <div className="panel chart-panel">
          <div className="panel-title">计划状态分布</div>
          <ReactECharts option={statusOption} notMerge style={{ height: 280 }} />
        </div>
        <div className="panel chart-panel">
          <div className="panel-title">广州各区作业票分布</div>
          <ReactECharts option={districtOption} notMerge style={{ height: 280 }} />
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">作业票台账</div>
        <Table
          size="middle"
          rowKey={(row) => row.id}
          loading={isLoading}
          dataSource={data?.recent_tickets || []}
          pagination={false}
          columns={[
            { title: '计划编号', dataIndex: 'plan_id', width: 150, ellipsis: true },
            { title: '项目名称', dataIndex: 'project_name', ellipsis: true },
            { title: '行政区', dataIndex: 'district', width: 120 },
            { title: '作业地点', dataIndex: 'work_location', width: 180, ellipsis: true },
            { title: '计划状态', dataIndex: 'plan_status', width: 110, render: (value) => <Tag color={statusColor[value] || 'default'}>{value}</Tag> },
            { title: '风险', dataIndex: 'risk_level', width: 90, render: (value) => <Tag color={riskColor[value] || 'default'}>{value}</Tag> },
            { title: '负责人', dataIndex: 'work_leader', width: 100 },
            { title: '更新时间', dataIndex: 'updated_at', width: 170 },
          ]}
        />
      </div>
    </div>
  )
}
