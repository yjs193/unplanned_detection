import { Alert, Button, Descriptions, Input, Modal, Select, Space, Tag, Typography, message } from 'antd'
import { DatabaseOutlined, FileSearchOutlined, ReloadOutlined, SaveOutlined, ToolOutlined, UndoOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { fetchAgentPrompts, resetAgentPrompt, resetAllAgentPrompts, updateAgentPrompt } from '../api'
import type { AgentPromptSetting } from '../types'

const { TextArea } = Input

function promptChecks(item?: AgentPromptSetting, draft = '') {
  if (!item) return []
  const checks = [
    { label: '中文表达', ok: /[\u4e00-\u9fa5]/.test(draft) },
    { label: '输出约束', ok: draft.includes('JSON') || draft.includes('Markdown') || draft.includes('中文') },
    { label: '职责边界', ok: draft.includes('职责') || draft.includes('只能') || draft.includes('不要') || draft.includes('不允许') },
  ]
  if (item.required_output.includes('JSON')) {
    checks.push({ label: '结构化输出', ok: draft.includes('JSON') && (draft.includes('字段') || draft.includes('包含')) })
  }
  return checks
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string>()
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [resourceOpen, setResourceOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['agent-prompts'],
    queryFn: async () => (await fetchAgentPrompts()).data,
  })

  const items = data?.items || []
  const selected = useMemo(() => items.find((item) => item.agent_id === selectedId) || items[0], [items, selectedId])
  const draft = selected ? drafts[selected.agent_id] ?? selected.prompt : ''
  const changed = selected ? draft !== selected.prompt : false

  useEffect(() => {
    if (!selectedId && items.length) setSelectedId(items[0].agent_id)
  }, [items, selectedId])

  useEffect(() => {
    if (!items.length) return
    setDrafts((current) => {
      const next = { ...current }
      items.forEach((item) => {
        if (!(item.agent_id in next)) next[item.agent_id] = item.prompt
      })
      return next
    })
  }, [items])

  const refreshPrompts = () => queryClient.invalidateQueries({ queryKey: ['agent-prompts'] })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error('请选择智能体')
      return (await updateAgentPrompt(selected.agent_id, draft)).data
    },
    onSuccess: (payload) => {
      if (!payload.success) {
        message.error(payload.error || '保存失败')
        return
      }
      message.success('提示语已保存')
      refreshPrompts()
    },
    onError: () => message.error('保存失败'),
  })

  const resetMutation = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error('请选择智能体')
      return (await resetAgentPrompt(selected.agent_id)).data
    },
    onSuccess: (payload) => {
      if (!payload.success || !payload.item) {
        message.error(payload.error || '重置失败')
        return
      }
      setDrafts((current) => ({ ...current, [payload.item!.agent_id]: payload.item!.prompt }))
      message.success('已恢复默认提示语')
      refreshPrompts()
    },
    onError: () => message.error('重置失败'),
  })

  const resetAllMutation = useMutation({
    mutationFn: async () => (await resetAllAgentPrompts()).data,
    onSuccess: (payload) => {
      const next: Record<string, string> = {}
      payload.items.forEach((item) => { next[item.agent_id] = item.prompt })
      setDrafts(next)
      message.success('全部智能体提示语已恢复默认')
      refreshPrompts()
    },
    onError: () => message.error('全部重置失败'),
  })

  const checks = promptChecks(selected, draft)

  return (
    <div className="page-stack">
      <div className="page-heading">
        <h1>设置</h1>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refreshPrompts()} loading={isLoading}>刷新配置</Button>
          <Button danger icon={<UndoOutlined />} loading={resetAllMutation.isPending} onClick={() => resetAllMutation.mutate()}>全部恢复默认</Button>
        </Space>
      </div>

      <div className="settings-layout">
        <div className="panel settings-agent-list">
          <div className="panel-title">智能体提示语</div>
          <Select
            loading={isLoading}
            value={selected?.agent_id}
            onChange={setSelectedId}
            options={items.map((item) => ({ value: item.agent_id, label: `${item.agent_name}｜${item.category}` }))}
            style={{ width: '100%', marginBottom: 12 }}
          />
          <div className="settings-agent-cards">
            {items.map((item) => (
              <button
                type="button"
                key={item.agent_id}
                className={`settings-agent-card ${item.agent_id === selected?.agent_id ? 'active' : ''}`}
                onClick={() => setSelectedId(item.agent_id)}
              >
                <span>{item.agent_name}</span>
                <small>{item.description}</small>
                <Tag color={item.is_custom ? 'blue' : 'default'}>{item.is_custom ? '已自定义' : '默认'}</Tag>
                <span className="settings-resource-count">
                  {(item.tools?.length || 0)} 工具 · {(item.knowledge_bases?.length || 0) + (item.manuals?.length || 0)} 知识
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="panel settings-editor-panel">
          {selected ? (
            <>
              <div className="panel-toolbar">
                <div>
                  <div className="panel-title">{selected.agent_name}</div>
                  <Typography.Text type="secondary">{selected.description}</Typography.Text>
                </div>
                <Space>
                  <Button icon={<DatabaseOutlined />} onClick={() => setResourceOpen(true)}>资源详情</Button>
                  <Button icon={<UndoOutlined />} onClick={() => resetMutation.mutate()} loading={resetMutation.isPending}>恢复默认</Button>
                  <Button type="primary" icon={<SaveOutlined />} disabled={!changed} loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>保存提示语</Button>
                </Space>
              </div>

              <Descriptions bordered size="small" column={2} className="professional-desc settings-meta">
                <Descriptions.Item label="所属模块">{selected.category}</Descriptions.Item>
                <Descriptions.Item label="当前状态">{selected.is_custom ? '已自定义' : '使用默认'}</Descriptions.Item>
                <Descriptions.Item label="输出要求">{selected.required_output}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{selected.updated_at || '未修改'}</Descriptions.Item>
              </Descriptions>

              <div className="settings-variable-row">
                <span>可用上下文</span>
                <Space wrap>
                  {selected.variables.map((item) => <Tag color="cyan" key={item}>{item}</Tag>)}
                </Space>
              </div>

              <div className="settings-resource-summary">
                <div>
                  <ToolOutlined />
                  <span>工具调用</span>
                  <b>{selected.tools?.length || 0}</b>
                </div>
                <div>
                  <DatabaseOutlined />
                  <span>知识与数据</span>
                  <b>{(selected.knowledge_bases?.length || 0) + (selected.data_sources?.length || 0)}</b>
                </div>
                <div>
                  <FileSearchOutlined />
                  <span>指导手册</span>
                  <b>{selected.manuals?.length || 0}</b>
                </div>
                <Button onClick={() => setResourceOpen(true)}>查看资源</Button>
              </div>

              <TextArea
                value={draft}
                onChange={(event) => setDrafts((current) => ({ ...current, [selected.agent_id]: event.target.value }))}
                rows={15}
                className="settings-prompt-editor"
                placeholder="请输入智能体系统提示语"
              />

              <div className="settings-quality-row">
                <Space wrap>
                  {checks.map((check) => <Tag color={check.ok ? 'green' : 'orange'} key={check.label}>{check.label}</Tag>)}
                  <Tag color={draft.length >= 20 ? 'green' : 'red'}>{draft.length} 字符</Tag>
                </Space>
                {changed && <Typography.Text type="warning">有未保存修改</Typography.Text>}
              </div>

              <Alert
                type="info"
                showIcon
                message="保存后立即影响后续调用；已运行完成的解析、问答和检测记录不会被回写修改。"
              />
            </>
          ) : (
            <div className="empty-state compact">暂无可配置智能体</div>
          )}
        </div>
      </div>

      <Modal
        title={selected ? `${selected.agent_name}资源详情` : '资源详情'}
        open={resourceOpen}
        onCancel={() => setResourceOpen(false)}
        footer={null}
        width={860}
      >
        {selected && (
          <div className="settings-resource-modal">
            <div className="settings-resource-section">
              <h3><ToolOutlined />工具调用</h3>
              {(selected.tools || []).length ? selected.tools!.map((item) => (
                <div className="settings-resource-item" key={`${item.name}-${item.type || ''}`}>
                  <div><b>{item.name}</b>{item.type && <Tag color="blue">{item.type}</Tag>}</div>
                  {item.purpose && <p>用途：{item.purpose}</p>}
                </div>
              )) : <div className="empty-state compact">暂无工具配置</div>}
            </div>

            <div className="settings-resource-section">
              <h3><DatabaseOutlined />知识库与数据源</h3>
              {[...(selected.knowledge_bases || []), ...(selected.data_sources || []).map((item) => ({ name: item.name, source: item.path, usage: item.status }))].length ? (
                [...(selected.knowledge_bases || []), ...(selected.data_sources || []).map((item) => ({ name: item.name, source: item.path, usage: item.status }))].map((item) => (
                  <div className="settings-resource-item" key={`${item.name}-${item.source}`}>
                    <div><b>{item.name}</b></div>
                    {item.source && <p>来源：{item.source}</p>}
                    {item.usage && <p>说明：{item.usage}</p>}
                  </div>
                ))
              ) : <div className="empty-state compact">暂无知识库或数据源配置</div>}
            </div>

            <div className="settings-resource-section">
              <h3><FileSearchOutlined />指导手册</h3>
              {(selected.manuals || []).length ? selected.manuals!.map((item) => (
                <div className="settings-resource-item" key={`${item.title}-${item.path}`}>
                  <div><b>{item.title}</b></div>
                  {item.path && <p>路径：{item.path}</p>}
                  {item.summary && <p>摘要：{item.summary}</p>}
                </div>
              )) : <div className="empty-state compact">暂无指导手册配置</div>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
