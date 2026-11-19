
import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// ==========================================
// 发送聊天消息
// ==========================================

export function sendChat(
  message,
  sessionId = null,
  options = {}
) {
  return request.post('/chat', {
    message,
    session_id: sessionId,
    agent_id: options.agentId ?? null,
    use_long_term_memory:
      options.useLongTermMemory ?? false,
    attachment: options.attachment ?? null
  })
}

// ==========================================
// 文档：提取文字
// ==========================================

export function extractAttachment(file) {
  const formData = new FormData()

  formData.append('file', file)

  return request.post(
    '/attachments/extract',
    formData,
    {
      timeout: 90000
    }
  )
}

// ==========================================
// 图片：DeepSeek 视觉理解
// ==========================================

export function analyzeImage(file) {
  const formData = new FormData()

  formData.append('file', file)

  return request.post(
    '/attachments/analyze-image',
    formData,
    {
      timeout: 120000
    }
  )
}

// ==========================================
// Agent 列表
// ==========================================

export function getAgents() {
  return request.get('/agents')
}

// ==========================================
// 历史会话
// ==========================================

export function getSessionHistory(sessionId) {
  return request.get(
    `/chat/sessions/${encodeURIComponent(sessionId)}`,
    {
      params: {
        limit: 100,
        offset: 0
      }
    }
  )
}

export function getSessions() {
  return request.get('/chat/sessions')
}

export function deleteSession(sessionId) {
  return request.delete(
    `/chat/sessions/${encodeURIComponent(sessionId)}`
  )
}
