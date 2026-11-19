
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 当前 Agent 的长期记忆列表
export function getMemories(
  agentId,
  options = {}
) {
  return api.get('/memories', {
    params: {
      agent_id: agentId,
      memory_type: options.memoryType || undefined,
      limit: options.limit ?? 100,
      offset: options.offset ?? 0
    }
  })
}

// 新增记忆
export function createMemory(agentId, data) {
  return api.post('/memories', {
    agent_id: agentId,
    memory_key: data.memory_key,
    content: data.content,
    memory_type: data.memory_type,
    source: data.source || 'manual',
    importance: Number(data.importance)
  })
}

// 编辑记忆
export function updateMemory(
  agentId,
  memoryId,
  data
) {
  return api.patch(
    `/memories/${encodeURIComponent(memoryId)}`,
    {
      memory_key: data.memory_key,
      content: data.content,
      memory_type: data.memory_type,
      importance: Number(data.importance)
    },
    {
      params: {
        agent_id: agentId
      }
    }
  )
}

// 删除记忆
export function deleteMemory(agentId, memoryId) {
  return api.delete(
    `/memories/${encodeURIComponent(memoryId)}`,
    {
      params: {
        agent_id: agentId
      }
    }
  )
}

// AI 提取记忆候选
// 支持：聊天会话 或 自己输入的一段文字
export function extractMemoryCandidates(
  agentId,
  options = {}
) {
  const payload = {
    agent_id: agentId
  }

  if (options.sessionId) {
    payload.session_id = options.sessionId
  } else {
    payload.text = options.text
  }

  return api.post(
    '/memories/extract',
    payload,
    {
      timeout: 120000
    }
  )
}
