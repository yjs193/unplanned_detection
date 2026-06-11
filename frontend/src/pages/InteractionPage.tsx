
import { Button, Descriptions, Drawer, Input, Select, Space, Table, Tag, message } from 'antd'
import { FileTextOutlined, SendOutlined, SyncOutlined } from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { fetchConversationMessages, fetchConversations, fetchLlmStatus, fetchSamples, parseTicket, sendInteractionMessageStream } from '../api'
import type { ParseRecord } from '../types'

type ChatItem = { role: 'user' | 'assistant'; content: string }

function readLatest(): ParseRecord | undefined {
  try {
    const raw = localStorage.getItem('latest_parse_record')
    return raw ? JSON.parse(raw) : undefined
  } catch {
    return undefined
  }
}

export default function InteractionPage() {
  const [parseRecord, setParseRecord] = useState<ParseRecord>()
  const [sampleId, setSampleId] = useState<string>()
  const [input, setInput] = useState('')
  const [chat, setChat] = useState<ChatItem[]>([{ role: 'assistant', content: '请选择或载入作业票，系统会围绕计划状态、作业地点和自动检查流程给出建议。' }])
  const [conversationId, setConversationId] = useState<string>()
  const [streaming, setStreaming] = useState(false)
  const [contextOpen, setContextOpen] = useState(false)

  useEffect(() => {
    setParseRecord(readLatest())
  }, [])

  const { data: sampleData, isLoading } = useQuery({
    queryKey: ['interaction-samples'],
    queryFn: async () => (await fetchSamples()).data,
  })

  const { data: llmStatus } = useQuery({
    queryKey: ['interaction-llm-status'],
    queryFn: async () => (await fetchLlmStatus()).data,
  })

  const { data: conversationData, refetch: refetchConversations } = useQuery({
    queryKey: ['conversations'],
    queryFn: async () => (await fetchConversations()).data,
  })

  const parseMutation = useMutation({
    mutationFn: parseTicket,
    onSuccess: ({ data }) => {
      setParseRecord(data.record)
      localStorage.setItem('latest_parse_record', JSON.stringify(data.record))
      message.success('作业票已载入')
    },
  })

  const loadSample = (nextId: string) => {
    setSampleId(nextId)
    parseMutation.mutate({ sampleId: nextId })
  }

  const fact = parseRecord?.ticket_fact
  const contextTags = fact ? (
    <Space wrap>
      <Tag color="blue">{fact.plan_id}</Tag>
      <Tag color={fact.plan_status === '开工中' ? 'cyan' : 'default'}>{fact.plan_status}</Tag>
      <Tag color="orange">{fact.risk_level}</Tag>
      <Tag color={fact.video_control_enabled ? 'green' : 'default'}>{fact.video_control_enabled ? '视频管控' : '未纳入视频管控'}</Tag>
    </Space>
  ) : null

  const send = () => {
    const content = input.trim()
    if (!content || streaming) return
    setChat((items) => [...items, { role: 'user', content }, { role: 'assistant', content: '' }])
    setInput('')
    setStreaming(true)
    sendInteractionMessageStream(
      { message: content, conversation_id: conversationId, context: parseRecord ? { ticket_id: parseRecord.ticket_id, ticket_fact: parseRecord.ticket_fact } : undefined },
      (event) => {
        if (event.type === 'conversation') setConversationId(event.conversation_id)
        if (event.type === 'delta') {
          setChat((items) => {
            const next = [...items]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') last.content += event.content
            return next
          })
        }
        if (event.type === 'final') {
          setConversationId(event.conversation_id)
          setChat((items) => {
            const next = [...items]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') last.content = event.answer
            return next
          })
          refetchConversations()
        }
        if (event.type === 'error') message.error(event.message || '模型 API 调用失败')
      },
      () => setStreaming(false),
      (err) => {
        setStreaming(false)
        message.error(err)
      },
    )
  }

  const loadConversation = async (id: string) => {
    const { data } = await fetchConversationMessages(id)
    setConversationId(id)
    setChat(data.items.map((item) => ({ role: item.role as 'user' | 'assistant', content: item.content })))
  }

  return (
    <div className="page-stack">
      <div className="page-heading"><h1>系统交互</h1></div>

      <div className="interaction-stack">
        <div className="panel interaction-context-panel">
          <div className="panel-toolbar">
            <div className="panel-title">作业票上下文</div>
            <Space>
              {fact && <Button icon={<FileTextOutlined />} onClick={() => setContextOpen(true)}>查看详情</Button>}
              <Button icon={<SyncOutlined />} onClick={() => setParseRecord(readLatest())}>最近解析</Button>
            </Space>
          </div>
          <div className="interaction-context-grid">
            <div className="interaction-context-controls">
              <Select
                showSearch
                loading={isLoading}
                placeholder="选择作业票"
                value={sampleId}
                onChange={loadSample}
                optionFilterProp="label"
                options={(sampleData?.samples || []).map((sample) => ({ value: sample.id, label: sample.name }))}
                style={{ width: '100%' }}
              />
              <Button loading={parseMutation.isPending} onClick={() => sampleId && parseMutation.mutate({ sampleId })} disabled={!sampleId}>
                重新载入作业票
              </Button>
            </div>
            {fact ? (
              <div className="interaction-context-summary">
                <div>
                  <div className="summary-title">{fact.project_name}</div>
                  <div className="summary-meta">{fact.district || '广州'}｜{fact.work_location}</div>
                </div>
                {contextTags}
                <div className="summary-work-content">{fact.work_content_summary || fact.work_content_raw}</div>
              </div>
            ) : (
              <div className="empty-state compact">暂无作业票上下文</div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-toolbar">
            <div className="panel-title">智能问答</div>
            <Tag color={llmStatus?.available ? 'cyan' : 'red'}>{llmStatus?.available ? `${llmStatus.provider} ${llmStatus.model || ''}` : '模型接口未配置'}</Tag>
          </div>

          <div className="chat-list professional-chat">
            {chat.map((item, index) => (
              <div className={`chat-bubble ${item.role}`} key={`${item.role}-${index}`}><ReactMarkdown>{item.content || '...'}</ReactMarkdown></div>
            ))}
          </div>

          <Space.Compact style={{ width: '100%', marginTop: 12 }}>
            <Input value={input} onChange={(event) => setInput(event.target.value)} onPressEnter={send} placeholder="输入检查问题或处置要求" />
            <Button icon={<FileTextOutlined />} onClick={() => setContextOpen(true)} disabled={!fact}>上下文</Button>
            <Button type="primary" icon={<SendOutlined />} loading={streaming} onClick={send}>发送</Button>
          </Space.Compact>
        </div>
      </div>

      <Drawer
        title="作业票上下文"
        open={contextOpen}
        onClose={() => setContextOpen(false)}
        width={680}
      >
        {fact ? (
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            {contextTags}
            <Descriptions bordered size="small" column={1} className="professional-desc">
              <Descriptions.Item label="项目名称">{fact.project_name}</Descriptions.Item>
              <Descriptions.Item label="计划编号">{fact.plan_id}</Descriptions.Item>
              <Descriptions.Item label="作业地点">{fact.work_location}</Descriptions.Item>
              <Descriptions.Item label="计划时间">{fact.plan_time_range?.start || '待补充'} 至 {fact.plan_time_range?.end || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="工作负责人">{fact.work_leader || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="施工单位">{fact.contractor || '待补充'}</Descriptions.Item>
              <Descriptions.Item label="作业摘要">{fact.work_content_summary || '待生成'}</Descriptions.Item>
              <Descriptions.Item label="作业内容">{fact.work_content_raw}</Descriptions.Item>
              <Descriptions.Item label="主要危害">{fact.main_hazards?.join('、') || '待识别'}</Descriptions.Item>
              <Descriptions.Item label="安全措施">{fact.risk_control_measures?.map((item) => `${item.risk_name}：${item.control_measure}`).join('；') || '待识别'}</Descriptions.Item>
            </Descriptions>
          </Space>
        ) : (
          <div className="empty-state compact">暂无作业票上下文</div>
        )}
      </Drawer>

      <div className="panel">
        <div className="panel-title">对话记录</div>
        <Table
          size="small"
          rowKey={(row) => row.id}
          dataSource={conversationData?.items || []}
          pagination={false}
          onRow={(row) => ({ onClick: () => loadConversation(row.id) })}
          columns={[
            { title: '会话标题', dataIndex: 'title', ellipsis: true },
            { title: '关联作业票', dataIndex: 'ticket_id', width: 160, render: (value) => value || '-' },
            { title: '更新时间', dataIndex: 'updated_at', width: 170 },
          ]}
        />
      </div>
    </div>
  )
}
