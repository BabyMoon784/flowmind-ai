import axios from 'axios'

// 与 Day 1 相同：经 Vite /api 代理访问 FastAPI。
const request = axios.create({
  baseURL: '/api',
  timeout: 20000
})

export function getAgentDetail(agentId) {
  return request.get(`/agents/${encodeURIComponent(agentId)}`)
}

export function createAgent(payload) {
  return request.post('/agents', payload)
}

export function updateAgent(agentId, payload) {
  return request.patch(`/agents/${encodeURIComponent(agentId)}`, payload)
}
