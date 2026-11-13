
<script setup>
import { ref, nextTick, onMounted, computed } from 'vue'

import {
  sendChat,
  getSessionHistory,
  getSessions,
  deleteSession
} from './api/chat'

import { renderMarkdown } from './utils/markdown'


// =====================================
// 1. 基础数据
// =====================================

const createWelcomeMessage = () => ({
  id: 'welcome',
  role: 'assistant',
  content: '你好呀！我是鱼鱼。有什么想法，都可以和我说。'
})

const messages = ref([createWelcomeMessage()])

const inputText = ref('')

const sessionId = ref(
  localStorage.getItem('flowmind_session_id') || null
)

const sessions = ref([])

const isRestoring = ref(Boolean(sessionId.value))
const isSending = ref(false)
const isLoadingSessions = ref(false)

const deletingSessionId = ref(null)

const listError = ref('')

const messageList = ref(null)


// 当前会话标题
const currentSessionTitle = computed(() => {
  const current = sessions.value.find(
    item => item.id === sessionId.value
  )

  return current?.title || '新对话'
})


// =====================================
// 2. 滚动到底部
// =====================================

async function scrollToBottom() {
  await nextTick()

  if (messageList.value) {
    messageList.value.scrollTop =
      messageList.value.scrollHeight
  }
}


// =====================================
// 3. Markdown 代码复制功能
// =====================================

async function handleMessageListClick(event) {
  const target = event.target

  if (!(target instanceof Element)) {
    return
  }

  const button = target.closest('.code-copy-button')

  if (!button || !messageList.value?.contains(button)) {
    return
  }

  const wrapper = button.closest('.code-block-wrapper')

  const codeElement = wrapper?.querySelector('pre code')

  if (!codeElement) {
    return
  }

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
      if (button.isConnected) {
        button.textContent = '复制'
      }
    }, 1500)
  }
}


// =====================================
// 4. 格式化时间
// =====================================

function formatDate(value) {
  if (!value) return ''

  const date = new Date(value.replace(' ', 'T'))

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}


// =====================================
// 5. 获取历史会话列表
// =====================================

async function loadSessions() {
  isLoadingSessions.value = true
  listError.value = ''

  try {
    const response = await getSessions()

    sessions.value = Array.isArray(response.data)
      ? response.data
      : []

  } catch (error) {
    console.error('获取会话列表失败：', error)

    listError.value = '历史会话加载失败，请检查后端服务。'

  } finally {
    isLoadingSessions.value = false
  }
}


// =====================================
// 6. 恢复指定会话
// =====================================

async function restoreSession(id) {
  if (!id) return

  isRestoring.value = true

  try {
    console.log('正在恢复会话：', id)

    const response = await getSessionHistory(id)

    const data = response.data

    if (!Array.isArray(data.messages)) {
      throw new Error('历史消息数据格式不正确')
    }

    messages.value = data.messages.map(message => ({
      id: message.id,
      role: message.role,
      content: message.content
    }))

    if (messages.value.length === 0) {
      messages.value = [createWelcomeMessage()]
    }

    sessionId.value = id

    localStorage.setItem(
      'flowmind_session_id',
      id
    )

    await scrollToBottom()

    console.log('会话恢复成功！')

  } catch (error) {
    console.error('恢复会话失败：', error)

    if (error.response?.status === 404) {
      if (sessionId.value === id) {
        sessionId.value = null

        localStorage.removeItem(
          'flowmind_session_id'
        )

        messages.value = [createWelcomeMessage()]
      }

      await loadSessions()

      alert('这个会话已经不存在了。')

    } else {
      alert('读取聊天记录失败，请检查后端服务。')
    }

  } finally {
    isRestoring.value = false
  }
}


// =====================================
// 7. 切换历史会话
// =====================================

async function switchSession(id) {
  if (
    id === sessionId.value ||
    isSending.value ||
    isRestoring.value
  ) {
    return
  }

  await restoreSession(id)
}


// =====================================
// 8. 新建会话
// =====================================

function createNewSession() {
  if (isSending.value || isRestoring.value) {
    return
  }

  sessionId.value = null

  localStorage.removeItem(
    'flowmind_session_id'
  )

  messages.value = [createWelcomeMessage()]

  inputText.value = ''

  scrollToBottom()
}


// =====================================
// 9. 删除历史会话
// =====================================

async function removeSession(session) {
  if (
    isSending.value ||
    isRestoring.value ||
    deletingSessionId.value
  ) {
    return
  }

  const confirmed = window.confirm(
    `确定删除会话「${session.title}」吗？\n删除后无法恢复。`
  )

  if (!confirmed) return

  deletingSessionId.value = session.id

  try {
    await deleteSession(session.id)

    // 如果删除的是当前会话
    if (sessionId.value === session.id) {
      sessionId.value = null

      localStorage.removeItem(
        'flowmind_session_id'
      )

      messages.value = [createWelcomeMessage()]
    }

    await loadSessions()

    console.log('会话删除成功！')

  } catch (error) {
    console.error('删除会话失败：', error)

    alert(
      error.response?.data?.detail ||
      '删除失败，请检查后端服务。'
    )

  } finally {
    deletingSessionId.value = null
  }
}


// =====================================
// 10. 发送消息
// =====================================

async function sendMessage() {
  const content = inputText.value.trim()

  if (
    !content ||
    isSending.value ||
    isRestoring.value
  ) {
    return
  }

  messages.value.push({
    id: `${Date.now()}-user`,
    role: 'user',
    content
  })

  inputText.value = ''

  isSending.value = true

  await scrollToBottom()

  try {
    const response = await sendChat(
      content,
      sessionId.value
    )

    const data = response.data

    sessionId.value = data.session_id

    localStorage.setItem(
      'flowmind_session_id',
      data.session_id
    )

    messages.value.push({
      id: `${Date.now()}-assistant`,
      role: 'assistant',
      content: data.reply
    })

    // 更新左侧历史列表
    await loadSessions()

  } catch (error) {
    console.error('聊天请求失败：', error)

    const errorMessage =
      error.response?.data?.detail ||
      error.message ||
      '未知错误'

    messages.value.push({
      id: `${Date.now()}-error`,
      role: 'assistant',
      content: `请求失败：${errorMessage}`
    })

  } finally {
    isSending.value = false

    await scrollToBottom()
  }
}


// =====================================
// 11. 页面初始化
// =====================================

onMounted(async () => {
  await loadSessions()

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
          v-else-if="sessions.length === 0"
          class="empty-history"
        >
          暂无历史会话
          <p>开始聊天后会自动保存。</p>
        </div>


        <div
          v-for="session in sessions"
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

        <div class="connection-status">
          <span class="status-dot"></span>
          {{ isRestoring ? '恢复中' : '已连接' }}
        </div>

      </header>


      <section class="chat-card">

        <div class="chat-header">

          <div>
            <div class="eyebrow">FLOWMIND AI</div>

            <h1>和鱼鱼聊天</h1>

            <p>
              有什么想法，都可以和我说。
            </p>
          </div>

        </div>


        <!-- 消息区域 -->
        <div
          class="message-list"
          ref="messageList"
          @click="handleMessageListClick"
        >

          <div
            v-for="message in messages"
            :key="message.id"
            :class="[
              'message-row',
              message.role
            ]"
          >

            <div class="avatar">
              {{ message.role === 'assistant' ? '鱼' : '我' }}
            </div>

            <div class="message-body">

              <div class="message-author">
                {{ message.role === 'assistant' ? '鱼鱼' : '我' }}
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

            <div class="avatar">鱼</div>

            <div class="message-body">

              <div class="message-author">
                鱼鱼
              </div>

              <div class="message-bubble thinking">
                鱼鱼正在思考...
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
            placeholder="给鱼鱼发送消息..."
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
                ? '鱼鱼正在思考...'
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

</style>
