
<script setup>
import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted
} from 'vue'

import {
  sendChat,
  getAgents,
  getSessions,
  getSessionHistory,
  deleteSession,
  extractAttachment,
  analyzeImage
} from './api/chat'

import { renderMarkdown } from './utils/markdown'

import AgentManager from './components/AgentManager.vue'
import MemoryManager from './components/MemoryManager.vue'


// ==========================================
// 1. 基础配置
// ==========================================

const DEFAULT_AGENT_ID =
  '00000000-0000-4000-8000-000000000001'

const AGENT_STORAGE_KEY = 'flowmind_agent_id'
const SESSION_STORAGE_KEY = 'flowmind_session_id'
const MEMORY_STORAGE_KEY = 'flowmind_use_memory'

const MAX_FILE_BYTES = 5 * 1024 * 1024

const IMAGE_EXTENSIONS = [
  'png', 'jpg', 'jpeg'
]

const ALLOWED_EXTENSIONS = [
  'txt', 'md', 'pdf', 'docx',
  ...IMAGE_EXTENSIONS
]


// ==========================================
// 2. 状态
// ==========================================

const agents = ref([])
const sessions = ref([])
const messages = ref([])

const inputText = ref('')

const selectedAgentId = ref(
  localStorage.getItem(AGENT_STORAGE_KEY)
  || DEFAULT_AGENT_ID
)

const sessionId = ref(
  localStorage.getItem(SESSION_STORAGE_KEY)
  || null
)

const useLongTermMemory = ref(
  localStorage.getItem(MEMORY_STORAGE_KEY) === 'true'
)

const isSending = ref(false)
const isUploading = ref(false)
const isRestoring = ref(Boolean(sessionId.value))
const isLoadingSessions = ref(false)

const deletingSessionId = ref(null)

const showAgentManager = ref(false)
const showMemoryManager = ref(false)

const selectedAttachment = ref(null)

const fileInput = ref(null)
const messageList = ref(null)

const errorText = ref('')
const agentError = ref('')
const historyHasMore = ref(false)


// ==========================================
// 3. 计算属性
// ==========================================

const currentAgent = computed(() =>
  agents.value.find(
    agent => agent.id === selectedAgentId.value
  )
)

const currentAgentName = computed(() =>
  currentAgent.value?.name || 'My Agent'
)

const currentAgentDescription = computed(() =>
  currentAgent.value?.description
  || '你的个人 AI 助手'
)

const currentSessionTitle = computed(() => {
  const current = sessions.value.find(
    item => item.id === sessionId.value
  )

  return current?.title || '新对话'
})

const filteredSessions = computed(() =>
  sessions.value.filter(session =>
    (session.agent_id || DEFAULT_AGENT_ID)
      === selectedAgentId.value
  )
)

const isBusy = computed(() =>
  isSending.value ||
  isUploading.value ||
  isRestoring.value
)

const canSend = computed(() =>
  !isBusy.value &&
  (
    Boolean(inputText.value.trim()) ||
    selectedAttachment.value !== null
  )
)

const selectedAttachmentIsImage = computed(() => {
  if (!selectedAttachment.value) return false

  return isImageFile(
    selectedAttachment.value.filename
  )
})


// ==========================================
// 4. 持久化偏好
// ==========================================

watch(selectedAgentId, id => {
  localStorage.setItem(AGENT_STORAGE_KEY, id)
})

watch(useLongTermMemory, enabled => {
  localStorage.setItem(
    MEMORY_STORAGE_KEY,
    String(enabled)
  )
})


// ==========================================
// 5. 工具函数
// ==========================================

function createWelcomeMessage() {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      currentAgentName.value === 'My Agent'
        ? '你好呀！我是鱼鱼，有什么可以帮你？'
        : `你好！我是 ${currentAgentName.value}，有什么可以帮你？`
  }
}

function getFileExtension(filename) {
  return String(filename || '')
    .split('.')
    .pop()
    .toLowerCase()
}

function isImageFile(filename) {
  return IMAGE_EXTENSIONS.includes(
    getFileExtension(filename)
  )
}

function formatRequestError(error) {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (detail) return JSON.stringify(detail)

  return error?.message || '未知错误'
}

function formatDate(value) {
  if (!value) return ''

  const date = new Date(
    String(value).replace(' ', 'T')
  )

  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function scrollToBottom() {
  await nextTick()

  if (messageList.value) {
    messageList.value.scrollTop =
      messageList.value.scrollHeight
  }
}


// ==========================================
// 6. Agent 列表
// ==========================================

async function loadAgents() {
  agentError.value = ''

  try {
    const response = await getAgents()
    const payload = response.data

    const list = Array.isArray(payload)
      ? payload
      : payload?.agents || payload?.items || []

    if (!Array.isArray(list)) {
      throw new Error('Agent 列表格式不正确')
    }

    agents.value = list

    if (
      list.length &&
      !list.some(
        agent => agent.id === selectedAgentId.value
      )
    ) {
      selectedAgentId.value =
        list.some(
          agent => agent.id === DEFAULT_AGENT_ID
        )
          ? DEFAULT_AGENT_ID
          : list[0].id
    }

    if (
      !sessionId.value &&
      messages.value.length <= 1
    ) {
      messages.value = [createWelcomeMessage()]
    }

  } catch (error) {
    console.error('加载 Agent 失败：', error)

    agentError.value = formatRequestError(error)
  }
}


// ==========================================
// 7. 历史会话列表
// ==========================================

async function loadSessions() {
  isLoadingSessions.value = true

  try {
    const response = await getSessions()
    const payload = response.data

    const list = Array.isArray(payload)
      ? payload
      : payload?.sessions || []

    if (!Array.isArray(list)) {
      throw new Error('会话列表格式不正确')
    }

    sessions.value = list.map(item => ({
      ...item,
      id: item.id || item.session_id
    }))

  } catch (error) {
    console.error('加载会话失败：', error)

    errorText.value =
      `加载会话失败：${formatRequestError(error)}`

  } finally {
    isLoadingSessions.value = false
  }
}


// ==========================================
// 8. 新建聊天
// ==========================================

function createNewSession(force = false) {
  if (!force && isBusy.value) return

  sessionId.value = null

  localStorage.removeItem(SESSION_STORAGE_KEY)

  inputText.value = ''
  errorText.value = ''
  historyHasMore.value = false

  clearAttachment()

  messages.value = [createWelcomeMessage()]

  scrollToBottom()
}

function handleAgentChange() {
  // 切换 Agent 必须新建会话
  createNewSession()
}


// ==========================================
// 9. Agent 管理
// ==========================================

async function handleAgentSaved() {
  await loadAgents()
}

function switchToManagedAgent(agentId) {
  if (isBusy.value || !agentId) return

  if (agentId !== selectedAgentId.value) {
    selectedAgentId.value = agentId
    createNewSession()
  }

  showAgentManager.value = false
}


// ==========================================
// 10. 长期记忆管理
// ==========================================

function openMemoryManager() {
  if (isBusy.value) return

  showMemoryManager.value = true
}

function closeMemoryManager() {
  showMemoryManager.value = false
}


// ==========================================
// 11. 恢复历史会话
// ==========================================

async function restoreSession(id) {
  if (
    !id ||
    isSending.value ||
    isUploading.value
  ) {
    return
  }

  isRestoring.value = true
  errorText.value = ''

  try {
    const response = await getSessionHistory(id)
    const data = response.data

    if (!Array.isArray(data.messages)) {
      throw new Error('历史消息格式不正确')
    }

    const fromList = sessions.value.find(
      item => item.id === id
    )

    const boundAgentId =
      data.agent_id || fromList?.agent_id

    if (
      boundAgentId &&
      boundAgentId !== selectedAgentId.value
    ) {
      selectedAgentId.value = boundAgentId
    }

    messages.value = [...data.messages]
      .sort(
        (a, b) => Number(a.id) - Number(b.id)
      )
      .map(message => ({
        id: message.id,
        role: message.role,
        content: message.content
      }))

    if (messages.value.length === 0) {
      messages.value = [createWelcomeMessage()]
    }

    historyHasMore.value = Boolean(data.has_more)

    sessionId.value = id

    localStorage.setItem(
      SESSION_STORAGE_KEY,
      id
    )

    inputText.value = ''
    clearAttachment()

    await scrollToBottom()

  } catch (error) {
    console.error('恢复会话失败：', error)

    errorText.value =
      `恢复会话失败：${formatRequestError(error)}`

    if (error?.response?.status === 404) {
      createNewSession(true)
      await loadSessions()
    }

  } finally {
    isRestoring.value = false
  }
}

async function switchSession(id) {
  if (
    id === sessionId.value ||
    isBusy.value
  ) {
    return
  }

  await restoreSession(id)
}


// ==========================================
// 12. 删除会话
// ==========================================

async function removeSession(session) {
  if (isBusy.value || deletingSessionId.value) {
    return
  }

  const confirmed = window.confirm(
    `确定删除会话「${session.title || '新对话'}」吗？`
  )

  if (!confirmed) return

  deletingSessionId.value = session.id

  try {
    await deleteSession(session.id)

    if (sessionId.value === session.id) {
      createNewSession()
    }

    await loadSessions()

  } catch (error) {
    errorText.value =
      `删除失败：${formatRequestError(error)}`

  } finally {
    deletingSessionId.value = null
  }
}


// ==========================================
// 13. 文档和图片附件
// ==========================================

function clearAttachment() {
  selectedAttachment.value = null

  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

async function handleFileSelected(event) {
  const file = event.target.files?.[0]

  if (!file) return

  if (isBusy.value) {
    event.target.value = ''
    return
  }

  const extension = getFileExtension(file.name)

  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    errorText.value =
      '仅支持 TXT、MD、PDF、DOCX、PNG、JPG、JPEG'

    event.target.value = ''
    return
  }

  if (file.size > MAX_FILE_BYTES) {
    errorText.value = '文件大小不能超过 5 MB'
    event.target.value = ''
    return
  }

  if (file.size === 0) {
    errorText.value = '不能上传空文件'
    event.target.value = ''
    return
  }

  const isImage =
    IMAGE_EXTENSIONS.includes(extension)

  errorText.value = ''
  isUploading.value = true
  selectedAttachment.value = null

  try {
    const response = isImage
      ? await analyzeImage(file)
      : await extractAttachment(file)

    const data = response.data

    if (
      !data ||
      typeof data.text !== 'string' ||
      !data.text.trim()
    ) {
      throw new Error('附件没有返回有效内容')
    }

    selectedAttachment.value = {
      ...data,
      filename: data.filename || file.name
    }

    if (data.truncated) {
      errorText.value = isImage
        ? '图片分析结果较长，部分内容已截断。'
        : '文档较长，仅提取前 16000 个字符。'
    }

  } catch (error) {
    console.error('附件处理失败：', error)

    errorText.value =
      `附件处理失败：${formatRequestError(error)}`

    selectedAttachment.value = null

  } finally {
    isUploading.value = false
    event.target.value = ''
  }
}


// ==========================================
// 14. Markdown 代码块复制
// ==========================================

async function handleMessageListClick(event) {
  const target = event.target

  if (!(target instanceof Element)) return

  const button = target.closest(
    '.code-copy-button'
  )

  if (
    !button ||
    !messageList.value?.contains(button)
  ) {
    return
  }

  const wrapper = button.closest(
    '.code-block-wrapper'
  )

  const code = wrapper?.querySelector(
    'pre code'
  )?.textContent

  if (code == null) return

  try {
    await navigator.clipboard.writeText(code)

    button.textContent = '已复制'

    window.setTimeout(() => {
      if (button.isConnected) {
        button.textContent = '复制'
      }
    }, 1500)

  } catch (error) {
    console.error('复制代码失败：', error)

    button.textContent = '复制失败'

    window.setTimeout(() => {
      if (button.isConnected) {
        button.textContent = '复制'
      }
    }, 1500)
  }
}


// ==========================================
// 15. 发送聊天消息
// ==========================================

async function sendMessage() {
  if (!canSend.value) return

  const attachment = selectedAttachment.value

  const question =
    inputText.value.trim() ||
    (
      attachment
        ? (
            isImageFile(attachment.filename)
              ? '请详细分析这张图片。'
              : '请总结这份文档。'
          )
        : ''
    )

  if (!question) return

  const attachmentPayload = attachment
    ? {
        filename: attachment.filename,
        text: attachment.text
      }
    : null

  const attachmentLabel = attachment
    ? (
        isImageFile(attachment.filename)
          ? '🖼️ 图片'
          : '📎 附件'
      )
    : ''

  const displayText = attachment
    ? (
        `${question}\n\n` +
        `${attachmentLabel}：${attachment.filename}` +
        '（仅本轮可读取）'
      )
    : question

  const tempId = `user-${Date.now()}`

  messages.value.push({
    id: tempId,
    role: 'user',
    content: displayText
  })

  inputText.value = ''
  errorText.value = ''
  isSending.value = true

  await scrollToBottom()

  try {
    const response = await sendChat(
      question,
      sessionId.value,
      {
        agentId: selectedAgentId.value,
        useLongTermMemory:
          useLongTermMemory.value,
        attachment: attachmentPayload
      }
    )

    const data = response.data

    sessionId.value = data.session_id

    localStorage.setItem(
      SESSION_STORAGE_KEY,
      data.session_id
    )

    messages.value.push({
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: data.reply
    })

    clearAttachment()

    await loadSessions()

  } catch (error) {
    console.error('发送消息失败：', error)

    messages.value = messages.value.filter(
      item => item.id !== tempId
    )

    inputText.value = question

    errorText.value =
      `发送失败：${formatRequestError(error)}`

  } finally {
    isSending.value = false
    await scrollToBottom()
  }
}


// ==========================================
// 16. 页面初始化
// ==========================================

onMounted(async () => {
  await Promise.all([
    loadAgents(),
    loadSessions()
  ])

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

    <!-- 左侧导航 -->
    <aside class="sidebar">

      <div class="sidebar-brand">
        <div class="brand-icon">鱼</div>

        <div>
          <div class="brand-name">
            FlowMind AI
          </div>

          <div class="brand-subtitle">
            你的个人 AI 助手
          </div>
        </div>
      </div>

      <button
        type="button"
        class="sidebar-button"
        :disabled="isBusy"
        @click="createNewSession()"
      >
        ＋ 新建对话
      </button>


      <!-- Agent 切换 -->
      <div class="sidebar-agent-section">

        <label
          class="sidebar-agent-label"
          for="agent-select"
        >
          当前 Agent
        </label>

        <select
          id="agent-select"
          v-model="selectedAgentId"
          class="agent-select"
          :disabled="isBusy"
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

        <p
          v-if="agentError"
          class="agent-error"
        >
          {{ agentError }}
        </p>


        <!-- Agent 管理 -->
        <button
          type="button"
          class="sidebar-button manage-button"
          :disabled="isBusy"
          @click="showAgentManager = true"
        >
          ⚙ 管理 Agent
        </button>


        <!-- Day 3 新增：长期记忆管理 -->
        <button
          type="button"
          class="sidebar-button manage-button memory-button"
          :disabled="isBusy"
          @click="openMemoryManager"
        >
          🧠 管理长期记忆
        </button>

      </div>


      <!-- 历史会话 -->
      <div class="sidebar-title">
        最近对话
      </div>

      <div class="history-list">

        <div
          v-if="isLoadingSessions && !sessions.length"
          class="empty-history"
        >
          正在加载会话...
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
            type="button"
            class="delete-button"
            title="删除会话"
            :disabled="isBusy || deletingSessionId !== null"
            @click.stop="removeSession(session)"
          >
            {{
              deletingSessionId === session.id
                ? '…'
                : '×'
            }}
          </button>
        </div>

      </div>

      <div class="sidebar-footer">
        FlowMind AI · Personal Agent
      </div>

    </aside>


    <!-- 右侧聊天工作台 -->
    <main class="main">

      <header class="topbar">

        <div>
          <div class="current-title">
            {{ currentSessionTitle }}
          </div>

          <div class="current-subtitle">
            FlowMind AI · 多 Agent 工作台
          </div>
        </div>

        <div class="topbar-actions">

          <label
            class="memory-switch"
            title="启用当前 Agent 的长期记忆检索"
          >
            <input
              v-model="useLongTermMemory"
              type="checkbox"
            />

            <span>长期记忆</span>
          </label>

          <div class="connection-status">
            <span class="status-dot"></span>

            {{
              isRestoring
                ? '恢复中'
                : '已连接'
            }}
          </div>

        </div>
      </header>


      <section class="chat-card">

        <div class="chat-header">

          <div class="eyebrow">
            FLOWMIND AI
          </div>

          <h1>
            和 {{ currentAgentName }} 聊天
          </h1>

          <p>
            {{ currentAgentDescription }}
          </p>

        </div>


        <!-- 消息区域 -->
        <div
          ref="messageList"
          class="message-list"
          @click="handleMessageListClick"
        >

          <p
            v-if="historyHasMore"
            class="history-notice"
          >
            当前显示最近 100 条消息。
          </p>

          <div
            v-for="message in messages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >

            <div class="avatar">
              {{
                message.role === 'assistant'
                  ? currentAgentName.charAt(0)
                  : '我'
              }}
            </div>

            <div class="message-body">

              <div class="message-author">
                {{
                  message.role === 'assistant'
                    ? currentAgentName
                    : '我'
                }}
              </div>

              <div
                class="message-bubble"
                v-html="renderMarkdown(message.content)"
              ></div>

            </div>
          </div>


          <!-- 思考状态 -->
          <div
            v-if="isSending"
            class="message-row assistant"
          >
            <div class="avatar">
              {{ currentAgentName.charAt(0) }}
            </div>

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


        <!-- 错误提示 -->
        <div
          v-if="errorText"
          class="error-banner"
          role="alert"
        >
          <span>{{ errorText }}</span>

          <button
            type="button"
            class="error-close"
            @click="errorText = ''"
          >
            ×
          </button>
        </div>


        <!-- 输入框 -->
        <form
          class="composer"
          @submit.prevent="sendMessage"
        >

          <!-- 附件 -->
          <div class="attachment-toolbar">

            <input
              id="flowmind-attachment"
              ref="fileInput"
              type="file"
              accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg"
              class="attachment-file-input"
              :disabled="isBusy"
              @change="handleFileSelected"
            />

            <label
              for="flowmind-attachment"
              class="attachment-button"
              :class="{ disabled: isBusy }"
            >
              📎 上传文件 / 图片
            </label>

            <div
              v-if="isUploading"
              class="attachment-processing"
            >
              <span class="loading-spinner"></span>
              正在解析附件或识别图片...
            </div>

            <div
              v-else-if="selectedAttachment"
              class="attachment-chip"
            >
              <span class="attachment-type">
                {{
                  selectedAttachmentIsImage
                    ? '🖼️'
                    : '📄'
                }}
              </span>

              <div class="attachment-info">
                <div class="attachment-name">
                  {{ selectedAttachment.filename }}
                </div>

                <div class="attachment-meta">
                  {{
                    selectedAttachmentIsImage
                      ? '图片分析完成'
                      : '文本提取完成'
                  }}
                  ·
                  {{ selectedAttachment.character_count }} 字
                </div>
              </div>

              <button
                type="button"
                class="attachment-remove"
                title="移除附件"
                :disabled="isBusy"
                @click="clearAttachment"
              >
                ×
              </button>

            </div>

          </div>


          <!-- 发送文字 -->
          <div class="composer-main">

            <textarea
              v-model="inputText"
              rows="2"
              maxlength="2000"
              :placeholder="`给 ${currentAgentName} 发送消息...`"
              :disabled="isBusy"
              @keydown.enter.exact.prevent="sendMessage"
            ></textarea>

            <button
              type="submit"
              class="send-button"
              :disabled="!canSend"
            >
              {{ isSending ? '发送中' : '发送' }}
              <span>➤</span>
            </button>

          </div>

        </form>

        <div class="composer-hint">
          {{
            isUploading
              ? '正在处理附件...'
              : isSending
                ? `${currentAgentName} 正在思考...`
                : '支持 PDF、Word、TXT、Markdown、PNG、JPG · 最大 5 MB'
          }}
        </div>

      </section>

      <p class="footer">
        FlowMind AI · Made with Vue 3
      </p>

    </main>


    <!-- Agent 管理弹窗 -->
    <AgentManager
      v-if="showAgentManager"
      :agents="agents"
      :selected-agent-id="selectedAgentId"
      @close="showAgentManager = false"
      @saved="handleAgentSaved"
      @switch-agent="switchToManagedAgent"
    />


    <!-- Day 3：长期记忆管理弹窗 -->
    <MemoryManager
      v-if="showMemoryManager"
      :agent-id="selectedAgentId"
      :agent-name="currentAgentName"
      :session-id="sessionId"
      @close="closeMemoryManager"
    />

  </div>
</template>


<style scoped>
* {
  box-sizing: border-box;
}

.app-shell {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  width: 100%;
  min-height: 100vh;
  background: #f5f7fb;
  color: #263246;
  font-family: Inter, "Microsoft YaHei", sans-serif;
}

/* ==========================================
   侧边栏
========================================== */

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 22px 16px;
  background: #fff;
  border-right: 1px solid #e5eaf2;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 5px 24px;
}

.brand-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
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
  color: #98a2b3;
  font-size: 12px;
}

.sidebar-button {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #dce5fa;
  border-radius: 10px;
  background: #f3f6ff;
  color: #4969c4;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.sidebar-button:hover:not(:disabled) {
  background: #e8eeff;
}

.sidebar-button:disabled {
  opacity: .5;
  cursor: not-allowed;
}

.sidebar-agent-section {
  margin-top: 22px;
}

.sidebar-agent-label {
  display: block;
  margin-bottom: 9px;
  color: #8995a8;
  font-size: 12px;
}

.agent-select {
  width: 100%;
  padding: 10px 11px;
  border: 1px solid #dce3ee;
  border-radius: 9px;
  background: #fff;
  color: #344054;
  font-size: 13px;
}

.agent-error {
  margin-top: 8px;
  color: #d74646;
  font-size: 12px;
}

.manage-button {
  margin-top: 10px;
}

.memory-button {
  background: #f5f7ff;
}

.sidebar-title {
  margin: 27px 8px 12px;
  color: #929cac;
  font-size: 12px;
  font-weight: 600;
}

.history-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-height: 0;
  overflow-y: auto;
}

.empty-history {
  padding: 15px 10px;
  color: #98a2b3;
  font-size: 13px;
  line-height: 1.7;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 9px;
  border-radius: 9px;
  cursor: pointer;
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
  color: #344054;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  margin-top: 6px;
  color: #9aa3b2;
  font-size: 10px;
}

.delete-button {
  border: none;
  background: transparent;
  color: #a0a9b8;
  font-size: 19px;
  cursor: pointer;
}

.sidebar-footer {
  padding: 16px 5px 0;
  border-top: 1px solid #edf0f5;
  color: #a0a9b8;
  font-size: 11px;
}

/* ==========================================
   主区域
========================================== */

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100vh;
  padding: 0 28px 15px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 76px;
  flex-shrink: 0;
  border-bottom: 1px solid #e5eaf2;
}

.current-title {
  font-size: 15px;
  font-weight: 700;
}

.current-subtitle {
  margin-top: 5px;
  color: #98a2b3;
  font-size: 11px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.memory-switch,
.connection-status {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #718096;
  font-size: 12px;
}

.memory-switch input {
  accent-color: #526fcb;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #35b77a;
}

/* ==========================================
   聊天卡片
========================================== */

.chat-card {
  display: flex;
  flex: 1;
  flex-direction: column;
  width: 100%;
  max-width: 1000px;
  min-height: 0;
  margin: 20px auto 0;
  overflow: hidden;
  border: 1px solid #e5eaf2;
  border-radius: 17px;
  background: #fff;
  box-shadow: 0 8px 30px rgba(35, 55, 90, .04);
}

.chat-header {
  padding: 22px 26px;
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

/* ==========================================
   消息区域
========================================== */

.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  min-height: 0;
  padding: 24px;
  overflow-y: auto;
  background: #fafbfe;
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
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
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
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  max-width: 78%;
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
  background: #fff;
  color: #344054;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}

.message-row.user .message-bubble {
  border-color: #dce6ff;
  border-radius: 14px 4px 14px 14px;
  background: #eaf0ff;
}

.thinking {
  color: #8a94a6;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .45; }
}

.history-notice {
  color: #718096;
  font-size: 12px;
  text-align: center;
}

/* ==========================================
   错误提示
========================================== */

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 10px 20px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff0f0;
  color: #c54444;
  font-size: 12px;
}

.error-close {
  border: none;
  background: transparent;
  color: #c54444;
  font-size: 18px;
  cursor: pointer;
}

/* ==========================================
   输入框
========================================== */

.composer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 15px 20px;
  border-top: 1px solid #edf0f5;
}

.composer-main {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.composer textarea {
  flex: 1;
  min-width: 0;
  min-height: 62px;
  padding: 12px;
  resize: vertical;
  border: 1px solid #e0e6f0;
  border-radius: 10px;
  outline: none;
  color: #344054;
  font-size: 14px;
  font-family: inherit;
}

.composer textarea:focus {
  border-color: #8199dd;
}

.send-button {
  flex-shrink: 0;
  padding: 13px 18px;
  border: none;
  border-radius: 10px;
  background: #526fcb;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.send-button:disabled {
  opacity: .5;
  cursor: not-allowed;
}

.composer-hint,
.footer {
  margin: 0;
  padding: 10px;
  color: #98a2b3;
  font-size: 11px;
  text-align: center;
}

/* ==========================================
   附件
========================================== */

.attachment-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  width: 100%;
}

.attachment-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.attachment-button {
  padding: 8px 12px;
  border: 1px solid #dbe4f5;
  border-radius: 9px;
  background: #f3f6ff;
  color: #4969c4;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.attachment-button:hover {
  background: #e9efff;
}

.attachment-button.disabled {
  opacity: .5;
  cursor: not-allowed;
  pointer-events: none;
}

.attachment-processing {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #718096;
  font-size: 12px;
}

.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #d7e0f3;
  border-top-color: #526fcb;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  padding: 8px 12px;
  border: 1px solid #dce6ff;
  border-radius: 9px;
  background: #eef3ff;
}

.attachment-type {
  font-size: 20px;
}

.attachment-info {
  min-width: 0;
}

.attachment-name {
  overflow: hidden;
  color: #455d98;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-meta {
  margin-top: 4px;
  color: #8595b4;
  font-size: 11px;
}

.attachment-remove {
  border: none;
  background: transparent;
  color: #dc5555;
  font-size: 20px;
  cursor: pointer;
}

/* ==========================================
   Markdown、代码和数学公式
========================================== */

.message-bubble :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
}

.message-bubble :deep(.code-block-wrapper) {
  max-width: 100%;
  overflow: hidden;
  border-radius: 9px;
  background: #0d1117;
}

.message-bubble :deep(.code-block-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 12px;
  color: #c9d1d9;
}

.message-bubble :deep(.code-copy-button) {
  padding: 4px 10px;
  border: 1px solid #444c56;
  border-radius: 6px;
  background: #21262d;
  color: #e6edf3;
  cursor: pointer;
}

.message-bubble :deep(.katex-display) {
  max-width: 100%;
  overflow-x: auto;
}

.message-bubble :deep(img) {
  max-width: 100%;
}

/* ==========================================
   响应式
========================================== */

@media (max-width: 900px) {
  .app-shell {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .main {
    padding: 0 12px 12px;
  }
}

@media (max-width: 650px) {
  .app-shell {
    grid-template-columns: 165px minmax(0, 1fr);
  }

  .sidebar {
    padding: 15px 8px;
  }

  .main {
    padding: 0 8px 8px;
  }

  .topbar-actions {
    gap: 8px;
  }

  .chat-header {
    padding: 16px;
  }

  .message-list {
    padding: 12px;
  }

  .message-body {
    max-width: 92%;
  }

  .composer {
    padding: 10px;
  }

  .composer-main {
    gap: 6px;
  }

  .send-button {
    padding: 12px;
  }
}
</style>
