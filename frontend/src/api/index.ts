
import axios from 'axios'
import type { DashboardData, InspectionRecord, ParseRecord, PilotWorkflowResult, SampleTicket, TicketFact, WorkTicket } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export const fetchDashboard = () => api.get<DashboardData>('/dashboard')

export const fetchTickets = (params?: { page?: number; page_size?: number; status?: string; keyword?: string }) =>
  api.get<{ total: number; items: WorkTicket[] }>('/work-tickets', { params })

export const fetchSamples = () => api.get<{ samples: SampleTicket[] }>('/work-tickets/samples')

export const importParsedTicket = (record: ParseRecord) =>
  api.post<{ success: boolean; created: boolean; ticket?: WorkTicket; message: string }>('/work-tickets/import', { record })

export const parseTicket = (payload: { text?: string; sampleId?: string; file?: File }) => {
  const fd = new FormData()
  if (payload.text) fd.append('text', payload.text)
  if (payload.sampleId) fd.append('sample_id', payload.sampleId)
  if (payload.file) fd.append('file', payload.file)
  return api.post<{ success: boolean; record: ParseRecord }>('/work-tickets/parse', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const startInspection = (payload: {
  ticket_id?: string
  ticket_fact?: TicketFact
  media_query_task?: Record<string, any>
  operator?: string
  mode?: string
}) => api.post<{ success: boolean; inspection: InspectionRecord }>('/interaction/start-inspection', payload)

export const fetchInspections = () => api.get<{ items: InspectionRecord[] }>('/interaction/inspections')

export const sendInteractionMessage = (payload: { message: string; context?: Record<string, any> }) =>
  api.post<{ success: boolean; provider: string; conversation_id?: string; answer: string; suggested_actions: string[] }>('/interaction/chat', payload)

export const fetchLlmStatus = () => api.get<{ provider: string; model?: string; available: boolean }>('/interaction/llm-status')


function readSseStream(response: Response, onEvent: (event: any) => void, onDone: () => void, onError: (message: string) => void) {
  if (!response.body) {
    onError('响应流不可用')
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const pump = (): any => reader.read().then(({ done, value }) => {
    if (done) {
      onDone()
      return
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.split('\n').find((item) => item.startsWith('data: '))
      if (!line) continue
      try { onEvent(JSON.parse(line.slice(6))) } catch { /* ignore */ }
    }
    return pump()
  }).catch((err) => onError(err.message || '流式请求失败'))
  pump()
}

export function parseTicketStream(
  payload: { text?: string; sampleId?: string; file?: File },
  onEvent: (event: any) => void,
  onDone: () => void,
  onError: (message: string) => void,
) {
  const fd = new FormData()
  if (payload.text) fd.append('text', payload.text)
  if (payload.sampleId) fd.append('sample_id', payload.sampleId)
  if (payload.file) fd.append('file', payload.file)
  fetch('/api/work-tickets/parse/stream', { method: 'POST', body: fd })
    .then((response) => {
      if (!response.ok) throw new Error(`请求失败：${response.status}`)
      readSseStream(response, onEvent, onDone, onError)
    })
    .catch((err) => onError(err.message || '解析失败'))
}

export function sendInteractionMessageStream(
  payload: { message: string; context?: Record<string, any>; conversation_id?: string },
  onEvent: (event: any) => void,
  onDone: () => void,
  onError: (message: string) => void,
) {
  fetch('/api/interaction/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then((response) => {
      if (!response.ok) throw new Error(`请求失败：${response.status}`)
      readSseStream(response, onEvent, onDone, onError)
    })
    .catch((err) => onError(err.message || '对话失败'))
}


export const fetchPilotHj = () => api.get<Record<string, any>>('/pilot/hj')
export const runPilotHj = () => api.post<PilotWorkflowResult>('/pilot/hj/run')
export const runFullInspection = (payload: { ticket_id?: string; record?: ParseRecord; operator?: string; mode?: string }) =>
  api.post<PilotWorkflowResult>('/inspection/run-full', payload)

export const fetchConversations = () => api.get<{ items: Array<Record<string, any>> }>('/interaction/conversations')
export const fetchConversationMessages = (conversationId: string) => api.get<{ items: Array<{ role: string; content: string; created_at: string }> }>(`/interaction/conversations/${conversationId}/messages`)
