<script setup>
import { ref, nextTick, onMounted, computed, watch } from 'vue'

import {
  sendChat,
  getSessionHistory,
  getSessions,
  deleteSession,
  getAgents
} from './api/chat'

import { renderMarkdown } from './utils/markdown'

// Phase 4 Day 1：保留原有聊天、Markdown、代码复制和历史会话功能。
const DEFAULT_AGENT_ID = '00000000-0000-4000-8000-000000000001'
const AGENT_STORAGE_KEY = 'flowmind_agent_id'
const SESSION_STORAGE_KEY = 'flowmind_session_id'
const MEMORY_STORAGE_KEY = 'flowmind_use_memory'

const agents = ref([])
const agentError = ref('')
const selectedAgentId = ref(
  localStorage.getItem(AGENT_STORAGE_KEY) || DEFAULT_AGENT_ID
)
const useLongTermMemory = ref(
  localStorage.getItem(MEMORY_STORAGE_KEY) === 'true'
)

const currentAgent = computed(() =>
  agents.value.find(agent => agent.id === selectedAgentId.value)
)
const currentAgentName = computed(() =>
  currentAgent.value?.name || 'My Agent'
)
const currentAgentDescription = computed(() =>
  currentAgent.value?.description || '你的个人 AI 助手'
)

const createWelcomeMessage = () => ({
  id: 'welcome',
  role: 'assistant',
  content: currentAgentName.value === 'My Agent'
    ? '你好呀！我是鱼鱼。有什么想法，都可以和我说。'
    : `你好！我是 ${currentAgentName.value}，有什么可以帮你？`
})

const messages = ref([createWelcomeMessage()])
const inputText = ref('')
const sessionId = ref(localStorage.getItem(SESSION_STORAGE_KEY) || null)
const sessions = ref([])

const isRestoring = ref(Boolean(sessionId.value))
const isSending = ref(false)
const isLoadingSessions = ref(false)
const deletingSessionId = ref(null)
const listError = ref('')
const historyHasMore = ref(false)
const messageList = ref(null)

const currentSessionTitle = computed(() => {
  const current = sessions.value.find(item => item.id === sessionId.value)
  return current?.title || '新对话'
})

// 旧数据没有 agent_id 时，视为默认 Agent 的会话。
function sessionAgentId(session) {
  return session?.agent_id || DEFAULT_AGENT_ID
}

const filteredSessions = computed(() =>
  sessions.value.filter(session =>
    sessionAgentId(session) === selectedAgentId.value
  )
)

watch(selectedAgentId, agentId => {
  localStorage.setItem(AGENT_STORAGE_KEY, agentId)
})

watch(useLongTermMemory, enabled => {
  localStorage.setItem(MEMORY_STORAGE_KEY, String(enabled))
})

async function scrollToBottom() {
  await nextTick()
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight
  }
}

// 保留原先经过 DOMPurify 清理的 Markdown 代码块复制功能。
async function handleMessageListClick(event) {
  const target = event.target
  if (!(target instanceof Element)) return

  const button = target.closest('.code-copy-button')
  if (!button || !messageList.value?.contains(button)) return

  const wrapper = button.closest('.code-block-wrapper')
  const codeElement = wrapper?.querySelector('pre code')
  if (!codeElement) return

  const code = codeElement.textContent || ''
  try {
    if (!navigator.clipboard?.writeText) {
      throw new Error('当前浏览器不支持剪贴板 API')
    }
    await navigator.clipboard.writeText(code)
    button.textContent = '已复制'
    button.classList.add('copied')
    window.setTimeout(() => {
      if (button.isConnected) {
        button.textContent = '复制'
        button.classList.remove('copied')
      }
    }, 1500)
  } catch (error) {
    console.error('复制代码失败：', error)
    button.textContent = '复制失败'
    window.setTimeout(() => {
      if (button.isConnected) button.textContent = '复制'
    }, 1500)
  }
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadAgents() {
  agentError.value = ''
  try {
    const response = await getAgents()
    const payload = response.data
    const list = Array.isArray(payload)
      ? payload
      : (payload?.agents || payload?.items || [])
    if (!Array.isArray(list)) throw new Error('Agent 列表格式不正确')

    agents.value = list
    if (list.length && !list.some(agent => agent.id === selectedAgentId.value)) {
      selectedAgentId.value = list.some(agent => agent.id === DEFAULT_AGENT_ID)
        ? DEFAULT_AGENT_ID
        : list[0].id
    }

    // 页面上的欢迎语应与当前 Agent 保持一致。
    if (!sessionId.value && messages.value.length === 1 &&
        messages.value[0].id === 'welcome') {
      messages.value = [createWelcomeMessage()]
    }
  } catch (error) {
    console.error('获取 Agent 列表失败：', error)
    agentError.value = 'Agent 列表加载失败，请检查后端。'
  }
}

async function loadSessions() {
  isLoadingSessions.value = true
  listError.value = ''
  try {
    const response = await getSessions()
    const payload = response.data
    const list = Array.isArray(payload)
      ? payload
      : (payload?.sessions || [])
    if (!Array.isArray(list)) throw new Error('会话列表格式不正确')
    sessions.value = list.map(item => ({
      ...item,
      id: item.id || item.session_id
    }))
  } catch (error) {
    console.error('获取会话列表失败：', error)
    listError.value = '历史会话加载失败，请检查后端服务。'
  } finally {
    isLoadingSessions.value = false
  }
}

async function restoreSession(id) {
  if (!id || isSending.value) return
  isRestoring.value = true
  try {
    const response = await getSessionHistory(id)
    const data = response.data
    if (!Array.isArray(data.messages)) {
      throw new Error('历史消息数据格式不正确')
    }

    const fromList = sessions.value.find(item => item.id === id)
    const boundAgentId = data.agent_id || fromList?.agent_id
    if (boundAgentId && boundAgentId !== selectedAgentId.value) {
      selectedAgentId.value = boundAgentId
    }

    // 后端分页返回的是从新到旧，界面改为从旧到新。
    messages.value = [...data.messages]
      .sort((a, b) => Number(a.id) - Number(b.id))
      .map(message => ({
        id: message.id,
        role: message.role,
        content: message.content
      }))

    historyHasMore.value = Boolean(data.has_more)
    if (messages.value.length === 0) {
      messages.value = [createWelcomeMessage()]
    }

    sessionId.value = id
    localStorage.setItem(SESSION_STORAGE_KEY, id)
    await scrollToBottom()
  } catch (error) {
    console.error('恢复会话失败：', error)
    if (error.response?.status === 404) {
      if (sessionId.value === id) createNewSession(true)
      await loadSessions()
      window.alert('这个会话已经不存在了。')
    } else {
      window.alert('读取聊天记录失败，请检查后端服务。')
    }
  } finally {
    isRestoring.value = false
  }
}

async function switchSession(id) {
  if (id === sessionId.value || isSending.value || isRestoring.value) return
  await restoreSession(id)
}

// force 仅供恢复已删除的会话时清理本地状态使用。
function createNewSession(force = false) {
  if (!force && (isSending.value || isRestoring.value)) return
  sessionId.value = null
  localStorage.removeItem(SESSION_STORAGE_KEY)
  historyHasMore.value = false
  messages.value = [createWelcomeMessage()]
  inputText.value = ''
  scrollToBottom()
}

function handleAgentChange() {
  // 选了另一个 Agent，必须新建聊天，不能复用之前绑定的 session_id。
  createNewSession()
}

async function removeSession(session) {
  if (isSending.value || isRestoring.value || deletingSessionId.value) return
  const confirmed = window.confirm(
    `确定删除会话「${session.title || '新对话'}」吗？\n删除后无法恢复。`
  )
  if (!confirmed) return

  deletingSessionId.value = session.id
  try {
    await deleteSession(session.id)
    if (sessionId.value === session.id) createNewSession()
    await loadSessions()
  } catch (error) {
    console.error('删除会话失败：', error)
    window.alert(error.response?.data?.detail || '删除失败，请检查后端服务。')
  } finally {
    deletingSessionId.value = null
  }
}

function formatRequestError(error) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail) return JSON.stringify(detail)
  return error.message || '未知错误'
}

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content || isSending.value || isRestoring.value) return

  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content
  })
  inputText.value = ''
  isSending.value = true
  await scrollToBottom()

  try {
    const response = await sendChat(content, sessionId.value, {
      agentId: selectedAgentId.value,
      useLongTermMemory: useLongTermMemory.value
    })
    const data = response.data
    sessionId.value = data.session_id
    localStorage.setItem(SESSION_STORAGE_KEY, data.session_id)
    messages.value.push({
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: data.reply
    })
    await loadSessions()
  } catch (error) {
    console.error('聊天请求失败：', error)
    messages.value.push({
      id: `error-${Date.now()}`,
      role: 'assistant',
      content: `请求失败：${formatRequestError(error)}`
    })
  } finally {
    isSending.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  await Promise.all([loadAgents(), loadSessions()])
  const savedSessionId = sessionId.value
  if (savedSessionId) {
    await restoreSession(savedSessionId)
  } else {
    messages.value = [createWelcomeMessage()]
    isRestoring.value = false
  }
})
</script>

<template>
  <div class="app-shell">

    <!-- 左侧历史会话栏 -->
    <aside class="sidebar">

      <div class="sidebar-brand">
        <div class="brand-icon">鱼</div>

        <div>
          <div class="brand-name">FlowMind AI</div>
          <div class="brand-subtitle">你的个人 AI 助手</div>
        </div>
      </div>


      <button
        class="new-chat-button"
        @click="createNewSession"
        :disabled="isSending || isRestoring"
      >
        <span>＋</span>
        新建对话
      </button>


      <div class="sidebar-agent-section">
        <label class="sidebar-agent-label" for="agent-select">
          当前 Agent
        </label>
        <select
          id="agent-select"
          v-model="selectedAgentId"
          class="agent-select"
          :disabled="isSending || isRestoring"
          @change="handleAgentChange"
        >
          <option
            v-for="agent in agents"
            :key="agent.id"
            :value="agent.id"
          >
            {{ agent.name }}
          </option>
          <option
            v-if="agents.length === 0"
            :value="selectedAgentId"
          >
            My Agent
          </option>
        </select>
        <p v-if="agentError" class="agent-error">{{ agentError }}</p>
      </div>


      <div class="sidebar-title">
        最近对话
      </div>


      <div class="history-list">

        <div
          v-if="isLoadingSessions && sessions.length === 0"
          class="empty-history"
        >
          正在加载会话...
        </div>

        <div
          v-else-if="listError && sessions.length === 0"
          class="empty-history"
        >
          {{ listError }}
        </div>

        <div
          v-else-if="filteredSessions.length === 0"
          class="empty-history"
        >
          暂无历史会话
          <p>开始聊天后会自动保存。</p>
        </div>


        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{
            active: session.id === sessionId
          }"
          role="button"
          tabindex="0"
          @click="switchSession(session.id)"
          @keydown.enter.prevent="switchSession(session.id)"
        >

          <div class="session-info">

            <div class="session-title">
              {{ session.title || '新对话' }}
            </div>

            <div class="session-meta">
              {{ formatDate(session.created_at) }}
              ·
              {{ session.message_count }} 条消息
            </div>

          </div>


          <button
            class="delete-button"
            title="删除会话"
            aria-label="删除会话"
            :disabled="
              isSending ||
              isRestoring ||
              deletingSessionId === session.id
            "
            @click.stop="removeSession(session)"
          >
            {{ deletingSessionId === session.id ? '…' : '×' }}
          </button>

        </div>

      </div>


      <div class="sidebar-footer">
        FlowMind AI · Personal Agent
      </div>

    </aside>


    <!-- 右侧聊天区域 -->
    <main class="main">

      <header class="topbar">

        <div>
          <div class="current-title">
            {{ currentSessionTitle }}
          </div>

          <div class="current-subtitle">
            FlowMind AI · 真实 AI 对话
          </div>
        </div>

        <div class="topbar-actions">
          <label class="memory-switch" title="开启后会检索当前 Agent 的长期记忆">
            <input type="checkbox" v-model="useLongTermMemory" />
            <span>长期记忆</span>
          </label>
          <div class="connection-status">
            <span class="status-dot"></span>
            {{ isRestoring ? '恢复中' : '已连接' }}
          </div>
        </div>

      </header>


      <section class="chat-card">

        <div class="chat-header">

          <div>
            <div class="eyebrow">FLOWMIND AI</div>

            <h1>和 {{ currentAgentName }} 聊天</h1>

            <p>{{ currentAgentDescription }}</p>
          </div>

        </div>


        <!-- 消息区域 -->
        <div
          class="message-list"
          ref="messageList"
          @click="handleMessageListClick"
        >

          <p v-if="historyHasMore" class="history-notice">
            当前显示最近 100 条消息，较早消息可在后续版本中继续加载。
          </p>

          <div
            v-for="message in messages"
            :key="message.id"
            :class="[
              'message-row',
              message.role
            ]"
          >

            <div class="avatar">
              {{ message.role === 'assistant' ? currentAgentName.charAt(0) : '我' }}
            </div>

            <div class="message-body">

              <div class="message-author">
                {{ message.role === 'assistant' ? currentAgentName : '我' }}
              </div>

              <div
                class="message-bubble"
                v-html="renderMarkdown(message.content)"
              ></div>

            </div>

          </div>


          <!-- AI 思考提示 -->
          <div
            v-if="isSending"
            class="message-row assistant"
          >

            <div class="avatar">{{ currentAgentName.charAt(0) }}</div>

            <div class="message-body">

              <div class="message-author">
                {{ currentAgentName }}
              </div>

              <div class="message-bubble thinking">
                {{ currentAgentName }} 正在思考...
              </div>

            </div>

          </div>

        </div>


        <!-- 输入区域 -->
        <form
          class="composer"
          @submit.prevent="sendMessage"
        >

          <textarea
            v-model="inputText"
            rows="2"
            :placeholder="`给 ${currentAgentName} 发送消息...`"
            :disabled="isRestoring"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>

          <button
            class="send-button"
            type="submit"
            :disabled="
              !inputText.trim() ||
              isSending ||
              isRestoring
            "
          >
            发送
            <span>➤</span>
          </button>

        </form>


        <div class="composer-hint">
          {{
            isRestoring
              ? '正在恢复历史对话...'
              : isSending
                ? `${currentAgentName} 正在思考...`
                : 'FlowMind AI · 真实 AI 对话'
          }}
        </div>

      </section>


      <p class="footer">
        FlowMind AI · Made with Vue 3
      </p>

    </main>

  </div>
</template>




<style scoped>

* {
  box-sizing: border-box;
}

.app-shell {
  width: 100%;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  background: #f5f7fb;
  color: #1f2937;
  font-family: Inter, "Microsoft YaHei", sans-serif;
}


/* =========================
   左侧导航栏
========================= */

.sidebar {
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  padding: 22px 16px;
  background: #ffffff;
  border-right: 1px solid #e7ebf2;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 5px 25px;
}

.brand-icon {
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: #e9efff;
  color: #4669cb;
  font-size: 21px;
  font-weight: 700;
}

.brand-name {
  font-size: 17px;
  font-weight: 700;
}

.brand-subtitle {
  margin-top: 4px;
  color: #9aa3b2;
  font-size: 12px;
}

.new-chat-button {
  width: 100%;
  height: 43px;
  border: 1px solid #dce5fa;
  border-radius: 10px;
  background: #f3f6ff;
  color: #4969c4;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  padding: 0 14px;
}

.new-chat-button span {
  margin-right: 8px;
  font-size: 19px;
}

.new-chat-button:hover:not(:disabled) {
  background: #e9efff;
}

.new-chat-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sidebar-title {
  margin: 27px 8px 12px;
  color: #929cac;
  font-size: 12px;
  font-weight: 600;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.empty-history {
  padding: 20px 10px;
  color: #a0a9b8;
  font-size: 13px;
  line-height: 1.8;
}

.empty-history p {
  margin: 5px 0;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 11px 9px;
  border-radius: 9px;
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:hover {
  background: #f5f7fb;
}

.session-item.active {
  background: #edf2ff;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  color: #344054;
}

.session-meta {
  margin-top: 6px;
  color: #9aa3b2;
  font-size: 10px;
}

.delete-button {
  width: 27px;
  height: 27px;
  flex-shrink: 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: #a0a9b8;
  font-size: 19px;
  cursor: pointer;
  opacity: 0;
}

.session-item:hover .delete-button {
  opacity: 1;
}

.delete-button:hover:not(:disabled) {
  background: #fff0f0;
  color: #e45c5c;
}

.delete-button:disabled {
  cursor: not-allowed;
}

.sidebar-footer {
  padding: 16px 5px 0;
  border-top: 1px solid #edf0f5;
  color: #a0a9b8;
  font-size: 11px;
}


/* =========================
   右侧主体
========================= */

.main {
  min-width: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0 30px 20px;
}

.topbar {
  min-height: 76px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e7ebf2;
}

.current-title {
  font-size: 15px;
  font-weight: 700;
}

.current-subtitle {
  margin-top: 5px;
  color: #9aa3b2;
  font-size: 11px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #718096;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #35b77a;
}

.chat-card {
  width: 100%;
  max-width: 1000px;
  flex: 1;
  min-height: 500px;
  margin: 28px auto 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e5eaf2;
  border-radius: 19px;
  background: #ffffff;
  box-shadow: 0 8px 30px rgba(35, 55, 90, 0.04);
}

.chat-header {
  padding: 23px 28px;
  border-bottom: 1px solid #edf0f5;
}

.eyebrow {
  color: #7188ce;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
}

.chat-header h1 {
  margin: 8px 0;
  font-size: 22px;
}

.chat-header p {
  margin: 0;
  color: #8a94a6;
  font-size: 13px;
}


/* =========================
   聊天消息
========================= */

.message-list {
  flex: 1;
  min-height: 300px;
  max-height: calc(100vh - 340px);
  overflow-y: auto;
  padding: 25px;
  background: #fafbfe;
  display: flex;
  flex-direction: column;
  gap: 21px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
}

.message-row.user {
  justify-content: flex-end;
}

.avatar {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: #e9efff;
  color: #4669cb;
  font-size: 13px;
  font-weight: 700;
}

.message-row.user .avatar {
  order: 2;
  background: #e9f2ed;
  color: #43835e;
}

.message-body {
  max-width: 78%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-row.user .message-body {
  align-items: flex-end;
}

.message-author {
  color: #8792a5;
  font-size: 12px;
}

.message-bubble {
  max-width: 100%;
  padding: 12px 15px;
  border: 1px solid #e8edf4;
  border-radius: 4px 14px 14px 14px;
  background: #ffffff;
  color: #344054;
  font-size: 14px;
  line-height: 1.8;
  white-space: normal;
  overflow-wrap: anywhere;
}

.message-row.user .message-bubble {
  border-radius: 14px 4px 14px 14px;
  background: #eaf0ff;
  border-color: #dce6ff;
}

.thinking {
  color: #8a94a6;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }

  50% {
    opacity: 0.45;
  }
}


/* =========================
   Markdown 样式
========================= */

/* 段落 */
.message-bubble :deep(p) {
  margin: 0 0 12px;
  line-height: 1.8;
}

.message-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

/* 标题 */
.message-bubble :deep(h1),
.message-bubble :deep(h2),
.message-bubble :deep(h3),
.message-bubble :deep(h4) {
  margin: 18px 0 10px;
  font-weight: 700;
  line-height: 1.5;
}

.message-bubble :deep(h1) {
  font-size: 22px;
}

.message-bubble :deep(h2) {
  font-size: 19px;
}

.message-bubble :deep(h3) {
  font-size: 16px;
}

/* 粗体 */
.message-bubble :deep(strong) {
  font-weight: 700;
  color: #263b68;
}

.message-bubble :deep(em) {
  font-style: italic;
}

/* 列表 */
.message-bubble :deep(ul),
.message-bubble :deep(ol) {
  padding-left: 25px;
  margin: 10px 0;
}

.message-bubble :deep(li) {
  margin: 5px 0;
  line-height: 1.8;
}

/* 链接 */
.message-bubble :deep(a) {
  color: #5274cf;
  text-decoration: underline;
  overflow-wrap: anywhere;
}

.message-bubble :deep(a:hover) {
  color: #304fae;
}

/* 引用 */
.message-bubble :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 14px;
  border-left: 3px solid #7995df;
  background: #f3f6fc;
  color: #68758b;
  border-radius: 0 7px 7px 0;
}

/* 分割线 */
.message-bubble :deep(hr) {
  border: none;
  border-top: 1px solid #e5eaf2;
  margin: 16px 0;
}

/* 行内代码 */
.message-bubble :deep(p code),
.message-bubble :deep(li code),
.message-bubble :deep(td code) {
  padding: 2px 6px;
  border-radius: 5px;
  background: #edf1f8;
  color: #b04462;
  font-family: Consolas, monospace;
  font-size: 0.9em;
}

/* 表格 */
.message-bubble :deep(table) {
  display: block;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 13px;
}

.message-bubble :deep(th),
.message-bubble :deep(td) {
  padding: 9px 12px;
  border: 1px solid #e1e7f0;
  text-align: left;
  white-space: nowrap;
}

.message-bubble :deep(th) {
  background: #f1f4fa;
  font-weight: 700;
}

.message-bubble :deep(tr:nth-child(even)) {
  background: #f9faff;
}

/* 图片 */
.message-bubble :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}


/* =========================
   代码块和复制按钮
========================= */

.message-bubble :deep(.code-block-wrapper) {
  width: 100%;
  margin: 14px 0;
  overflow: hidden;
  border-radius: 10px;
  background: #18212f;
}

/* 代码块顶部工具栏 */
.message-bubble :deep(.code-block-toolbar) {
  height: 40px;
  padding: 0 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #111a27;
  color: #cbd5e1;
}

/* 语言名称 */
.message-bubble :deep(.code-language) {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
}

/* 复制按钮 */
.message-bubble :deep(.code-copy-button) {
  padding: 5px 11px;
  border: 1px solid #465367;
  border-radius: 6px;
  background: transparent;
  color: #dce6f5;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.message-bubble :deep(.code-copy-button:hover) {
  background: #344256;
  border-color: #7c93b5;
}

.message-bubble :deep(.code-copy-button.copied) {
  color: #68d391;
  border-color: #68d391;
}

/* 代码区域 */
.message-bubble :deep(pre.hljs) {
  margin: 0;
  padding: 16px;
  border-radius: 0 0 10px 10px;
  overflow-x: auto;
  background: #18212f;
  font-size: 13px;
  line-height: 1.7;
  max-width: 100%;
}

.message-bubble :deep(pre.hljs code) {
  font-family: Consolas, "Courier New", monospace;
  white-space: pre;
}


/* =========================
   输入区域
========================= */

.composer {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 18px 20px 8px;
}

.composer textarea {
  flex: 1;
  min-width: 0;
  min-height: 54px;
  max-height: 150px;
  resize: vertical;
  border: 1px solid #e1e7f0;
  border-radius: 12px;
  padding: 14px;
  outline: none;
  font: inherit;
  font-size: 14px;
}

.composer textarea:focus {
  border-color: #8ba3e8;
}

.composer textarea:disabled {
  background: #f5f7fb;
  cursor: not-allowed;
}

.send-button {
  height: 48px;
  padding: 0 20px;
  border: none;
  border-radius: 11px;
  background: #526fcb;
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
}

.send-button:hover:not(:disabled) {
  background: #405ebc;
}

.send-button:disabled {
  background: #b7c2dc;
  cursor: not-allowed;
}

.send-button span {
  margin-left: 5px;
}

.composer-hint {
  padding: 5px 20px 16px;
  color: #a0a9b8;
  font-size: 11px;
}

.footer {
  text-align: center;
  color: #a0a9b8;
  font-size: 11px;
  margin: 17px 0 0;
}


/* =========================
   响应式布局
========================= */

@media (max-width: 760px) {

  .app-shell {
    grid-template-columns: 210px minmax(0, 1fr);
  }

  .sidebar {
    padding: 16px 10px;
  }

  .main {
    padding: 0 12px 15px;
  }

  .chat-header {
    padding: 18px;
  }

  .message-list {
    padding: 17px;
  }

}

@media (max-width: 560px) {

  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    height: auto;
    position: static;
    border-right: none;
    border-bottom: 1px solid #e7ebf2;
  }

  .sidebar-brand {
    padding-bottom: 12px;
  }

  .sidebar-title,
  .sidebar-footer {
    display: none;
  }

  .history-list {
    max-height: 150px;
    margin-top: 12px;
  }

  .main {
    min-height: 70vh;
  }

}



/* =========================
   Phase 4 Day 1：Agent 与长期记忆
========================= */

.sidebar-agent-section {
  margin-top: 18px;
  padding: 0 2px;
}

.sidebar-agent-label {
  display: block;
  margin: 0 6px 9px;
  color: #929cac;
  font-size: 12px;
  font-weight: 600;
}

.agent-select {
  width: 100%;
  min-height: 41px;
  padding: 9px 10px;
  border: 1px solid #dce5fa;
  border-radius: 9px;
  background: #fff;
  color: #344054;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.agent-select:focus-visible {
  border-color: #6685db;
  box-shadow: 0 0 0 3px rgba(82, 111, 203, 0.12);
}

.agent-select:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.agent-error {
  margin: 8px 5px 0;
  color: #c45252;
  font-size: 11px;
  line-height: 1.5;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 24px;
}

.memory-switch {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #67758c;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.memory-switch input {
  accent-color: #526fcb;
  width: 15px;
  height: 15px;
}

.history-notice {
  margin: 0;
  padding: 9px 11px;
  border-radius: 8px;
  background: #eef3ff;
  color: #6a7b9a;
  font-size: 12px;
}

@media (max-width: 560px) {
  .sidebar-agent-section {
    margin-top: 12px;
  }

  .topbar-actions {
    gap: 10px;
  }

  .connection-status {
    font-size: 11px;
  }
}

</style>
