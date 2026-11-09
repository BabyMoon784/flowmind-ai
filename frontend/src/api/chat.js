
import axios from 'axios'

// 创建统一的 API 请求实例
const request = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 发送聊天消息
export function sendChat(message, sessionId = null) {
  return request.post('/chat', {
    message: message,
    session_id: sessionId,
    use_long_term_memory: false
  })
}

// 获取指定会话的历史记录
export function getSessionHistory(sessionId) {
  return request.get(`/chat/sessions/${sessionId}`)
}

// 获取所有历史会话
export function getSessions() {
  return request.get('/chat/sessions')
}

// 删除指定会话
export function deleteSession(sessionId) {
  return request.delete(`/chat/sessions/${sessionId}`)
}