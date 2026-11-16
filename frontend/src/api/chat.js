import axios from 'axios'

// 共用 Vite 的 /api 代理，后端地址仍在 vite.config.js 配置。
const request = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 保留以前的 sendChat(message, sessionId) 调用方式。
// Day 1 新增第三个可选参数，支持 Agent 和长期记忆开关。
export function sendChat(message, sessionId = null, options = {}) {
  return request.post('/chat', {
    message,
    session_id: sessionId,
    agent_id: options.agentId ?? null,
    use_long_term_memory: options.useLongTermMemory ?? false
  })
}

export function getAgents() {
  return request.get('/agents')
}

// 请求最近 100 条消息；后端分页接口从最新消息开始返回。
export function getSessionHistory(sessionId) {
  return request.get(`/chat/sessions/${encodeURIComponent(sessionId)}`, {
    params: { limit: 100, offset: 0 }
  })
}

export function getSessions() {
  return request.get('/chat/sessions')
}

export function deleteSession(sessionId) {
  return request.delete(`/chat/sessions/${encodeURIComponent(sessionId)}`)
}