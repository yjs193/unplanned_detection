import { Alert, Button, Descriptions, Image, InputNumber, Select, Space, Table, Tag, Typography, message } from 'antd'
import { PlayCircleOutlined, ReloadOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { fetchSamples, fetchVisionBindings, runVisionAnalysis } from '../api'
import type { SampleTicket, VisionAnalysisResult, VisionBinding, WorkTicket } from '../types'

const { Paragraph } = Typography

function ticketLabel(ticket?: WorkTicket) {
  if (!ticket) return ''
  return `${ticket.plan_id}｜${ticket.project_name || '未填工程'}`
}

export default function VisionUnderstandingPage() {
  const [ticketId, setTicketId] = useState<string>()
  const [videoFile, setVideoFile] = useState<string>()
  const [frameCount, setFrameCount] = useState(8)
  const [result, setResult] = useState<VisionAnalysisResult>()

  const { data: sampleData, isLoading, refetch } = useQuery({
    queryKey: ['vision-ticket-samples'],
    queryFn: async () => (await fetchSamples()).data,
  })

  const tickets = useMemo(
    () => (sampleData?.samples || []).map((item: SampleTicket) => item.ticket).filter(Boolean) as WorkTicket[],
    [sampleData?.samples],
  )
  const selectedTicket = useMemo(() => tickets.find((item) => item.id === ticketId), [tickets, ticketId])

  useEffect(() => {
    if (ticketId || !tickets.length) return
    const boundCandidate = tickets.find((ticket) => ticket.plan_id?.startsWith('030120WS24010001')) || tickets[0]
    setTicketId(boundCandidate.id)
  }, [ticketId, tickets])

  const { data: bindingData, isFetching: bindingLoading } = useQuery({
    queryKey: ['vision-bindings', ticketId],
    queryFn: async () => (await fetchVisionBindings({ ticket_id: ticketId })).data,
    enabled: !!ticketId,
  })

  const binding = bindingData?.items?.[0] as VisionBinding | undefined
  const videos = binding?.videos || []

  useEffect(() => {
    if (!videos.length) {
      setVideoFile(undefined)
      return
    }
    setVideoFile((current) => current && videos.some((item) => item.filename === current) ? current : videos[0].filename)
  }, [videos])

  const mutation = useMutation({
    mutationFn: runVisionAnalysis,
    onSuccess: ({ data }) => {
      setResult(data)
      if (data.success) message.success('视觉理解已完成')
      else message.warning(data.error || data.fallback_reason || '未生成有效视觉证据')
    },
    onError: () => message.error('视觉理解请求失败'),
  })

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>视觉理解</h1>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新作业票</Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={mutation.isPending}
            disabled={!selectedTicket || !binding?.matched}
            onClick={() => selectedTicket && mutation.mutate({ ticket_id: selectedTicket.id, video_filename: videoFile, frame_count: frameCount, use_model: true })}
          >
            执行视觉理解
          </Button>
        </Space>
      </div>

      <div className="two-col vision-layout">
        <div className="panel">
          <div className="panel-title">作业票与视频绑定</div>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Select
              showSearch
              loading={isLoading}
              placeholder="选择作业票"
              optionFilterProp="label"
              value={ticketId}
              onChange={(value) => {
                setTicketId(value)
                setResult(undefined)
              }}
              options={tickets.map((ticket) => ({ value: ticket.id, label: ticketLabel(ticket) }))}
              style={{ width: '100%' }}
            />

            {selectedTicket && (
              <div className="summary-box">
                <div className="summary-title">{selectedTicket.ticket_title || selectedTicket.project_name}</div>
                <div className="summary-meta">{selectedTicket.plan_id}｜{selectedTicket.work_location || '作业地点待补充'}</div>
                <Space wrap style={{ marginTop: 10 }}>
                  <Tag color={selectedTicket.plan_status === '开工中' ? 'green' : 'default'}>{selectedTicket.plan_status}</Tag>
                  <Tag color="blue">{selectedTicket.risk_level || '未定级'}</Tag>
                  <Tag color={binding?.matched ? 'cyan' : 'orange'}>{bindingLoading ? '正在匹配视频' : binding?.matched ? `已绑定 ${binding.video_count} 段视频` : '未匹配到视频'}</Tag>
                </Space>
                <div className="summary-work-content">{selectedTicket.work_content_raw || '票面作业内容待补充'}</div>
              </div>
            )}

            {binding ? (
              <Descriptions bordered size="small" column={1} className="professional-desc">
                <Descriptions.Item label="信息表">{binding.workbook}</Descriptions.Item>
                <Descriptions.Item label="关联周计划">{binding.weekly_plan || '未填写'}</Descriptions.Item>
                <Descriptions.Item label="三级作业任务">{binding.task_name || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="执行状态">{binding.execution_status || '待补充'}</Descriptions.Item>
                <Descriptions.Item label="现场负责人">{binding.site_leader || '待补充'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Alert type="warning" showIcon message="当前作业票未在信息表中匹配到本地视频" description="请确认作业票编号与信息表“作业票编号”一致，且“关联周计划”字段能匹配视频文件名前缀。" />
            )}

            <div className="vision-control-row">
              <div>
                <div className="field-label">视频文件</div>
                <Select
                  value={videoFile}
                  disabled={!videos.length}
                  onChange={setVideoFile}
                  options={videos.map((video) => ({ value: video.filename, label: `${video.filename}｜${video.size_mb}MB` }))}
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <div className="field-label">抽帧数量</div>
                <InputNumber min={1} max={12} value={frameCount} onChange={(value) => setFrameCount(Number(value || 8))} style={{ width: '100%' }} />
              </div>
            </div>
          </Space>
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">现场事实证据包</div>
            {result?.source && <Tag color={result.success ? 'green' : 'orange'}>{result.success ? '已生成' : '需补充'}</Tag>}
          </div>
          {mutation.isPending && <Alert type="info" showIcon message="正在抽取视频帧并调用视觉理解" description="视频较大时需要等待，完成后会输出逐帧事实和紧凑证据链。" style={{ marginBottom: 12 }} />}
          {result?.fallback_reason && <Alert type="warning" showIcon message={result.fallback_reason} style={{ marginBottom: 12 }} />}
          {result ? (
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Descriptions bordered size="small" column={2} className="professional-desc">
                <Descriptions.Item label="分析编号">{result.analysis_id || '待生成'}</Descriptions.Item>
                <Descriptions.Item label="帧数">{result.frame_count}</Descriptions.Item>
                <Descriptions.Item label="视频文件" span={2}>{result.video?.filename || '未绑定'}</Descriptions.Item>
                <Descriptions.Item label="输出边界" span={2}>{result.output_boundary || '只输出现场事实证据包'}</Descriptions.Item>
              </Descriptions>
              <div>
                <div className="panel-title small">现场证据链文本</div>
                <Paragraph className="vision-evidence-text">{result.evidence_text || '暂无证据链文本'}</Paragraph>
              </div>
              <Table
                size="small"
                rowKey="frame_index"
                pagination={false}
                dataSource={result.frames || []}
                columns={[
                  { title: '帧', dataIndex: 'display_label', width: 86 },
                  { title: '画面', dataIndex: 'image_url', width: 132, render: (value) => value ? <Image width={104} height={58} src={value} style={{ objectFit: 'cover', borderRadius: 6 }} /> : '-' },
                  { title: '现场事实', dataIndex: 'evidence_text', ellipsis: true },
                ]}
                expandable={{ expandedRowRender: (row) => <div className="vision-expand">{row.evidence_text}</div> }}
              />
            </Space>
          ) : (
            <div className="empty-state compact">选择已绑定视频的作业票后，点击执行视觉理解生成现场事实证据包</div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">已匹配视频清单</div>
        <Table
          size="small"
          rowKey="filename"
          loading={bindingLoading}
          pagination={{ pageSize: 6 }}
          dataSource={videos}
          columns={[
            { title: '视频文件', dataIndex: 'filename', ellipsis: true },
            { title: '关联周计划', dataIndex: 'weekly_plan', width: 180 },
            { title: '摄像头编号', dataIndex: 'camera_id', width: 250, ellipsis: true },
            { title: '大小', dataIndex: 'size_mb', width: 90, render: (value) => `${value}MB` },
            { title: '操作', dataIndex: 'url', width: 110, render: (value) => <a href={value} target="_blank" rel="noreferrer"><VideoCameraOutlined /> 预览</a> },
          ]}
          locale={{ emptyText: '当前作业票没有匹配到本地视频' }}
        />
      </div>
    </div>
  )
}
