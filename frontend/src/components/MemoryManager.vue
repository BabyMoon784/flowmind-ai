
<script setup>
import {
  ref,
  reactive,
  computed,
  watch
} from 'vue'

import {
  getMemories,
  createMemory,
  updateMemory,
  deleteMemory,
  extractMemoryCandidates
} from '../api/memories'


// ==========================================
// 1. Props / Emits
// ==========================================

const props = defineProps({
  agentId: {
    type: String,
    required: true
  },
  agentName: {
    type: String,
    default: 'My Agent'
  },
  sessionId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['close'])


// ==========================================
// 2. 配置
// ==========================================

const MEMORY_TYPES = [
  { value: 'profile', label: '个人资料' },
  { value: 'preference', label: '偏好习惯' },
  { value: 'project', label: '项目经历' },
  { value: 'fact', label: '事实信息' },
  { value: 'goal', label: '目标计划' }
]

const VALID_TYPES = MEMORY_TYPES.map(
  item => item.value
)

const SOURCE_NAMES = {
  manual: '手动创建',
  conversation: '对话提取',
  import: '导入',
  system: '系统'
}

const PAGE_SIZE = 100


// ==========================================
// 3. 页面状态
// ==========================================

const activeTab = ref('list')

const memories = ref([])
const candidates = ref([])

const loading = ref(false)
const loadingMore = ref(false)
const saving = ref(false)
const extracting = ref(false)
const deletingId = ref(null)

const hasMore = ref(false)
const searchText = ref('')
const typeFilter = ref('all')

const errorText = ref('')
const noticeText = ref('')

const editorOpen = ref(false)
const editingId = ref(null)
const candidateIndex = ref(null)

const extractMode = ref(
  props.sessionId ? 'session' : 'text'
)

const extractText = ref('')

const form = reactive({
  memory_key: '',
  content: '',
  memory_type: 'fact',
  importance: 3
})


// ==========================================
// 4. 计算属性
// ==========================================

const filteredMemories = computed(() => {
  const keyword = searchText.value
    .trim()
    .toLowerCase()

  return memories.value.filter(memory => {
    const matchesType =
      typeFilter.value === 'all'
      || memory.memory_type === typeFilter.value

    const text = (
      String(memory.memory_key || '') + ' ' +
      String(memory.content || '')
    ).toLowerCase()

    const matchesSearch =
      !keyword || text.includes(keyword)

    return matchesType && matchesSearch
  })
})

const isEditing = computed(
  () => editingId.value !== null
)

const canExtract = computed(() => {
  if (extracting.value) return false

  if (extractMode.value === 'session') {
    return Boolean(props.sessionId)
  }

  return extractText.value.trim().length > 0
})


// ==========================================
// 5. 工具函数
// ==========================================

function getMemoryId(memory) {
  return memory.id || memory.memory_id || null
}

function getTypeName(type) {
  return MEMORY_TYPES.find(
    item => item.value === type
  )?.label || '事实信息'
}

function getSourceName(source) {
  return SOURCE_NAMES[source] || '未知来源'
}

function getErrorMessage(error) {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (detail) {
    return JSON.stringify(detail)
  }

  return error?.message || '操作失败'
}

function clearMessages() {
  errorText.value = ''
  noticeText.value = ''
}

function resetForm() {
  form.memory_key = ''
  form.content = ''
  form.memory_type = 'fact'
  form.importance = 3

  editingId.value = null
  candidateIndex.value = null
}

function closeEditor() {
  if (saving.value) return

  editorOpen.value = false
  resetForm()
}

function switchTab(tab) {
  if (saving.value || extracting.value) return

  activeTab.value = tab
  clearMessages()
}


// ==========================================
// 6. 读取当前 Agent 的记忆
// ==========================================

// 防止切换 Agent 后旧请求覆盖新数据
let requestVersion = 0

async function loadMemories() {
  const version = ++requestVersion
  const agentId = props.agentId

  loading.value = true
  errorText.value = ''

  try {
    const response = await getMemories(
      agentId,
      {
        limit: PAGE_SIZE,
        offset: 0
      }
    )

    if (
      version !== requestVersion
      || agentId !== props.agentId
    ) {
      return
    }

    const list = response.data?.memories

    if (!Array.isArray(list)) {
      throw new Error('记忆列表格式不正确')
    }

    memories.value = list
    hasMore.value = list.length === PAGE_SIZE

  } catch (error) {
    if (version === requestVersion) {
      errorText.value =
        `读取记忆失败：${getErrorMessage(error)}`
    }

  } finally {
    if (version === requestVersion) {
      loading.value = false
    }
  }
}

async function loadMore() {
  if (
    !hasMore.value ||
    loading.value ||
    loadingMore.value
  ) {
    return
  }

  const agentId = props.agentId

  loadingMore.value = true

  try {
    const response = await getMemories(
      agentId,
      {
        limit: PAGE_SIZE,
        offset: memories.value.length
      }
    )

    if (agentId !== props.agentId) return

    const list = response.data?.memories || []

    memories.value.push(...list)
    hasMore.value = list.length === PAGE_SIZE

  } catch (error) {
    errorText.value =
      `加载更多失败：${getErrorMessage(error)}`

  } finally {
    loadingMore.value = false
  }
}


// ==========================================
// 7. 新增记忆
// ==========================================

function openCreate() {
  clearMessages()
  resetForm()
  editorOpen.value = true
}


// ==========================================
// 8. 编辑记忆
// ==========================================

function openEdit(memory) {
  clearMessages()
  resetForm()

  const id = getMemoryId(memory)

  if (!id) {
    errorText.value =
      '这条记忆缺少 ID，无法编辑'
    return
  }

  editingId.value = id

  form.memory_key = memory.memory_key || ''
  form.content = memory.content || ''

  form.memory_type =
    VALID_TYPES.includes(memory.memory_type)
      ? memory.memory_type
      : 'fact'

  form.importance = Number(
    memory.importance ?? 3
  )

  editorOpen.value = true
}


// ==========================================
// 9. 保存记忆
// ==========================================

async function saveMemory() {
  if (saving.value) return

  const agentId = props.agentId

  const memoryKey = form.memory_key.trim()
  const content = form.content.trim()
  const importance = Number(form.importance)

  if (!memoryKey || !content) {
    errorText.value = '记忆名称和内容不能为空'
    return
  }

  if (memoryKey.length > 100) {
    errorText.value = '记忆名称不能超过 100 字'
    return
  }

  if (content.length > 3000) {
    errorText.value = '记忆内容不能超过 3000 字'
    return
  }

  if (
    !Number.isInteger(importance)
    || importance < 1
    || importance > 5
  ) {
    errorText.value = '重要程度必须是 1 到 5'
    return
  }

  const data = {
    memory_key: memoryKey,
    content,
    memory_type: form.memory_type,
    importance
  }

  saving.value = true
  errorText.value = ''

  try {
    if (isEditing.value) {
      await updateMemory(
        agentId,
        editingId.value,
        data
      )

      noticeText.value = '记忆已更新'

    } else {
      // AI 候选记忆经过用户审核后才保存
      const source = candidateIndex.value !== null
        ? 'conversation'
        : 'manual'

      await createMemory(agentId, {
        ...data,
        source
      })

      noticeText.value = '记忆已保存'

      if (candidateIndex.value !== null) {
        candidates.value.splice(
          candidateIndex.value,
          1
        )
      }
    }

    editorOpen.value = false
    resetForm()

    await loadMemories()

  } catch (error) {
    errorText.value =
      `保存失败：${getErrorMessage(error)}`

  } finally {
    saving.value = false
  }
}


// ==========================================
// 10. 删除记忆
// ==========================================

async function removeMemory(memory) {
  const id = getMemoryId(memory)

  if (!id || deletingId.value !== null) return

  const confirmed = window.confirm(
    `确定删除「${memory.memory_key}」吗？\n删除后无法恢复。`
  )

  if (!confirmed) return

  deletingId.value = id
  clearMessages()

  try {
    await deleteMemory(props.agentId, id)

    noticeText.value = '记忆已删除'

    await loadMemories()

  } catch (error) {
    errorText.value =
      `删除失败：${getErrorMessage(error)}`

  } finally {
    deletingId.value = null
  }
}


// ==========================================
// 11. AI 记忆候选规范化
// ==========================================

function normalizeCandidate(item, index) {
  const raw = (
    item && typeof item === 'object'
  ) ? item : {
    content: String(item ?? '')
  }

  const type =
    raw.memory_type || raw.type || 'fact'

  const importance = Number(
    raw.importance ?? 3
  )

  return {
    candidateId: index,
    memory_key: String(
      raw.memory_key ||
      raw.key ||
      raw.title ||
      `候选记忆${index + 1}`
    ),
    content: String(
      raw.content ||
      raw.value ||
      raw.memory ||
      raw.text ||
      ''
    ),
    memory_type: VALID_TYPES.includes(type)
      ? type
      : 'fact',
    importance: (
      Number.isInteger(importance)
      && importance >= 1
      && importance <= 5
    ) ? importance : 3
  }
}


// ==========================================
// 12. AI 提取候选记忆
// ==========================================

async function runExtraction() {
  if (!canExtract.value) return

  clearMessages()
  extracting.value = true
  candidates.value = []

  const agentId = props.agentId

  try {
    const options = extractMode.value === 'session'
      ? {
          sessionId: props.sessionId
        }
      : {
          text: extractText.value.trim()
        }

    const response = await extractMemoryCandidates(
      agentId,
      options
    )

    if (agentId !== props.agentId) return

    const rawCandidates =
      response.data?.candidates || []

    if (!Array.isArray(rawCandidates)) {
      throw new Error('AI 候选记忆格式不正确')
    }

    candidates.value = rawCandidates
      .map(normalizeCandidate)
      .filter(item => item.content.trim())

    noticeText.value = candidates.value.length
      ? `提取到 ${candidates.value.length} 条候选记忆，请逐条审核。`
      : '没有提取到适合长期保存的记忆。'

  } catch (error) {
    errorText.value =
      `AI 提取失败：${getErrorMessage(error)}`

  } finally {
    extracting.value = false
  }
}


// ==========================================
// 13. 审核 AI 候选
// ==========================================

function reviewCandidate(index) {
  const candidate = candidates.value[index]
  if (!candidate) return

  clearMessages()
  resetForm()

  candidateIndex.value = index

  form.memory_key = candidate.memory_key
  form.content = candidate.content
  form.memory_type = candidate.memory_type
  form.importance = candidate.importance

  editorOpen.value = true
}

function ignoreCandidate(index) {
  candidates.value.splice(index, 1)
}


// ==========================================
// 14. Agent 切换与初始化
// ==========================================

watch(
  () => props.agentId,
  () => {
    requestVersion++

    memories.value = []
    candidates.value = []
    editorOpen.value = false

    searchText.value = ''
    typeFilter.value = 'all'

    extractMode.value = props.sessionId
      ? 'session'
      : 'text'

    resetForm()
    clearMessages()

    loadMemories()
  },
  { immediate: true }
)
</script>


<template>
  <div
    class="memory-overlay"
    @click.self="emit('close')"
  >
    <section
      class="memory-panel"
      role="dialog"
      aria-modal="true"
      aria-label="长期记忆管理"
    >

      <!-- 顶部 -->
      <header class="memory-header">
        <div>
          <div class="eyebrow">FLOWMIND MEMORY</div>
          <h2>长期记忆管理</h2>
          <p>
            当前 Agent：<strong>{{ agentName }}</strong>
          </p>
        </div>

        <button
          type="button"
          class="icon-button"
          aria-label="关闭记忆管理"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <!-- Tab -->
      <div class="memory-tabs">
        <button
          type="button"
          :class="{ active: activeTab === 'list' }"
          @click="switchTab('list')"
        >
          已保存的记忆
        </button>

        <button
          type="button"
          :class="{ active: activeTab === 'extract' }"
          @click="switchTab('extract')"
        >
          AI 记忆提取
        </button>
      </div>

      <!-- 消息 -->
      <p v-if="errorText" class="alert error">
        {{ errorText }}
      </p>

      <p v-if="noticeText" class="alert success">
        {{ noticeText }}
      </p>


      <!-- ===================================
           已保存的记忆
      ==================================== -->
      <main
        v-if="activeTab === 'list'"
        class="memory-content"
      >
        <div class="memory-toolbar">
          <input
            v-model="searchText"
            type="search"
            placeholder="搜索记忆名称或内容..."
          />

          <select v-model="typeFilter">
            <option value="all">全部类型</option>
            <option
              v-for="type in MEMORY_TYPES"
              :key="type.value"
              :value="type.value"
            >
              {{ type.label }}
            </option>
          </select>

          <button
            type="button"
            class="primary-button"
            @click="openCreate"
          >
            ＋ 新增记忆
          </button>
        </div>

        <div class="memory-summary">
          已加载 {{ memories.length }} 条记忆
          <span>· 搜索当前已加载的记录</span>
        </div>

        <p v-if="loading" class="empty-text">
          正在加载记忆...
        </p>

        <p
          v-else-if="filteredMemories.length === 0"
          class="empty-text"
        >
          {{ memories.length === 0
            ? '这个 Agent 还没有保存长期记忆。'
            : '没有找到符合条件的记忆。'
          }}
        </p>

        <div
          v-for="memory in filteredMemories"
          :key="getMemoryId(memory)"
          class="memory-card"
        >
          <div class="memory-card-top">
            <div>
              <h3>
                {{ memory.memory_key }}
              </h3>

              <div class="memory-meta">
                <span class="type-tag">
                  {{ getTypeName(memory.memory_type) }}
                </span>

                <span>
                  重要程度 {{ memory.importance ?? 3 }}/5
                </span>

                <span>
                  {{ getSourceName(memory.source) }}
                </span>
              </div>
            </div>

            <div class="card-actions">
              <button
                type="button"
                @click="openEdit(memory)"
              >
                编辑
              </button>

              <button
                type="button"
                class="danger-button"
                :disabled="deletingId !== null"
                @click="removeMemory(memory)"
              >
                删除
              </button>
            </div>
          </div>

          <p class="memory-body">
            {{ memory.content }}
          </p>
        </div>

        <button
          v-if="hasMore && !loading"
          class="more-button"
          type="button"
          :disabled="loadingMore"
          @click="loadMore"
        >
          {{ loadingMore ? '加载中...' : '加载更多记忆' }}
        </button>
      </main>


      <!-- ===================================
           AI 记忆提取
      ==================================== -->
      <main
        v-else
        class="memory-content"
      >
        <div class="extract-intro">
          <h3>从聊天中提取值得记住的信息</h3>

          <p>
            AI 只生成候选记忆，不会自动保存。
            你可以修改内容、类型和重要程度，
            确认后才会写入当前 Agent 的数据库。
          </p>
        </div>

        <div class="extract-options">
          <label>
            <input
              v-model="extractMode"
              type="radio"
              value="session"
              :disabled="!sessionId"
            />
            从当前聊天会话提取
          </label>

          <label>
            <input
              v-model="extractMode"
              type="radio"
              value="text"
            />
            从指定文字提取
          </label>
        </div>

        <div
          v-if="extractMode === 'session'"
          class="source-info"
        >
          <p v-if="sessionId">
            将分析当前 Agent 的这一段会话，
            只从用户消息中提取长期记忆。
          </p>

          <p v-else>
            当前没有已保存的聊天会话。
            请先聊天，或选择从指定文字提取。
          </p>
        </div>

        <div v-else class="source-text">
          <label for="memory-extract-text">
            待提取文本
          </label>

          <textarea
            id="memory-extract-text"
            v-model="extractText"
            maxlength="4000"
            rows="5"
            placeholder="例如：我主要使用 C++ 学习算法，准备参加 CSP 比赛，希望 AI 用中文分步骤讲解。"
          ></textarea>

          <span>
            {{ extractText.length }}/4000
          </span>
        </div>

        <button
          type="button"
          class="primary-button extract-button"
          :disabled="!canExtract"
          @click="runExtraction"
        >
          {{
            extracting
              ? 'AI 正在分析...'
              : '开始 AI 提取'
          }}
        </button>

        <div
          v-if="candidates.length"
          class="candidate-section"
        >
          <h3>
            待审核候选（{{ candidates.length }}）
          </h3>

          <div
            v-for="(candidate, index) in candidates"
            :key="candidate.candidateId"
            class="memory-card candidate-card"
          >
            <div class="memory-card-top">
              <h3>
                {{ candidate.memory_key }}
              </h3>

              <span class="type-tag">
                {{ getTypeName(candidate.memory_type) }}
              </span>
            </div>

            <p class="memory-body">
              {{ candidate.content }}
            </p>

            <div class="candidate-actions">
              <button
                type="button"
                class="primary-button"
                @click="reviewCandidate(index)"
              >
                审核并保存
              </button>

              <button
                type="button"
                class="secondary-button"
                @click="ignoreCandidate(index)"
              >
                忽略
              </button>
            </div>
          </div>
        </div>
      </main>


      <!-- ===================================
           新增 / 编辑 / 审核弹窗
      ==================================== -->
      <div
        v-if="editorOpen"
        class="editor-overlay"
      >
        <form
          class="editor-card"
          @submit.prevent="saveMemory"
        >
          <div class="editor-title">
            <h3>
              {{
                isEditing
                  ? '编辑记忆'
                  : candidateIndex !== null
                    ? '审核候选记忆'
                    : '新增记忆'
              }}
            </h3>

            <button
              type="button"
              class="icon-button"
              @click="closeEditor"
            >
              ×
            </button>
          </div>

          <label for="memory-key">记忆名称 *</label>

          <input
            id="memory-key"
            v-model="form.memory_key"
            maxlength="100"
            required
            placeholder="例如：CSP 学习偏好"
          />

          <label for="memory-content">
            记忆内容 *
          </label>

          <textarea
            id="memory-content"
            v-model="form.content"
            maxlength="3000"
            rows="6"
            required
            placeholder="请输入需要长期保存的具体信息"
          ></textarea>

          <div class="editor-grid">
            <div>
              <label for="memory-type">
                记忆类型
              </label>

              <select
                id="memory-type"
                v-model="form.memory_type"
              >
                <option
                  v-for="type in MEMORY_TYPES"
                  :key="type.value"
                  :value="type.value"
                >
                  {{ type.label }}
                </option>
              </select>
            </div>

            <div>
              <label for="memory-importance">
                重要程度
              </label>

              <select
                id="memory-importance"
                v-model.number="form.importance"
              >
                <option
                  v-for="level in 5"
                  :key="level"
                  :value="level"
                >
                  {{ level }}/5
                </option>
              </select>
            </div>
          </div>

          <p class="editor-note">
            这条记忆仅属于 {{ agentName }}。
            保存后会持久化到 SQLite。
          </p>

          <div class="editor-actions">
            <button
              type="button"
              class="secondary-button"
              :disabled="saving"
              @click="closeEditor"
            >
              取消
            </button>

            <button
              type="submit"
              class="primary-button"
              :disabled="saving"
            >
              {{
                saving
                  ? '保存中...'
                  : '确认保存'
              }}
            </button>
          </div>
        </form>
      </div>

    </section>
  </div>
</template>


<style scoped>
* {
  box-sizing: border-box;
}

.memory-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(20, 32, 55, 0.45);
}

.memory-panel {
  display: flex;
  flex-direction: column;
  width: min(880px, 100%);
  height: min(830px, 92vh);
  min-height: 0;
  overflow: hidden;
  border: 1px solid #e4e9f2;
  border-radius: 18px;
  background: #fff;
  color: #344054;
  box-shadow: 0 22px 70px rgba(20, 32, 55, .18);
}

.memory-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px 18px;
  border-bottom: 1px solid #edf0f5;
}

.eyebrow {
  color: #7188ce;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
}

.memory-header h2 {
  margin: 8px 0;
  font-size: 23px;
}

.memory-header p {
  margin: 0;
  color: #8a94a6;
  font-size: 13px;
}

.icon-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #8490a4;
  font-size: 23px;
  cursor: pointer;
}

.icon-button:hover {
  background: #f2f5fb;
}

.memory-tabs {
  display: flex;
  gap: 10px;
  padding: 12px 28px 0;
  border-bottom: 1px solid #edf0f5;
}

.memory-tabs button {
  padding: 12px 15px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #8a94a6;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.memory-tabs button.active {
  border-bottom-color: #526fcb;
  color: #526fcb;
}

.memory-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px 28px 30px;
}

.memory-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.memory-toolbar input {
  flex: 1;
  min-width: 170px;
}

input,
textarea,
select {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid #dce3ee;
  border-radius: 9px;
  outline: none;
  background: #fff;
  color: #344054;
  font: inherit;
  font-size: 13px;
}

input:focus,
textarea:focus,
select:focus {
  border-color: #7188ce;
}

.memory-toolbar select {
  width: 145px;
}

.primary-button,
.secondary-button,
.more-button,
.card-actions button {
  padding: 10px 14px;
  border: 1px solid #dbe4f5;
  border-radius: 9px;
  font-size: 13px;
  cursor: pointer;
}

.primary-button {
  border-color: #526fcb;
  background: #526fcb;
  color: #fff;
  font-weight: 600;
}

.secondary-button,
.more-button,
.card-actions button {
  background: #f3f6ff;
  color: #4969c4;
}

button:disabled {
  opacity: .5;
  cursor: not-allowed;
}

.memory-summary {
  margin: 17px 0;
  color: #6c788d;
  font-size: 12px;
}

.memory-summary span {
  color: #a0a9b8;
}

.memory-card {
  margin-bottom: 12px;
  padding: 18px;
  border: 1px solid #e5eaf2;
  border-radius: 12px;
  background: #fff;
}

.memory-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.memory-card h3 {
  margin: 0 0 10px;
  font-size: 15px;
}

.memory-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  color: #8995a8;
  font-size: 11px;
}

.type-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 6px;
  background: #eef2ff;
  color: #526fcb;
  font-size: 11px;
}

.memory-body {
  margin: 15px 0 0;
  color: #48566c;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.card-actions,
.candidate-actions,
.editor-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.card-actions .danger-button {
  border-color: #f9e0e0;
  background: #fff3f3;
  color: #d95353;
}

.more-button {
  display: block;
  width: 100%;
  margin-top: 15px;
}

.empty-text {
  padding: 50px 20px;
  color: #98a2b3;
  font-size: 13px;
  text-align: center;
}

.alert {
  margin: 12px 28px 0;
  padding: 11px 13px;
  border-radius: 9px;
  font-size: 12px;
}

.alert.error {
  background: #fff0f0;
  color: #c54444;
}

.alert.success {
  background: #f0f7ff;
  color: #4264b3;
}

.extract-intro {
  padding: 16px;
  border-radius: 11px;
  background: #f6f8fd;
}

.extract-intro h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.extract-intro p,
.source-info p {
  margin: 0;
  color: #748198;
  font-size: 13px;
  line-height: 1.8;
}

.extract-options {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin: 24px 0;
  font-size: 13px;
}

.extract-options label {
  display: flex;
  align-items: center;
  gap: 7px;
}

.extract-options input {
  width: auto;
  accent-color: #526fcb;
}

.source-text label {
  display: block;
  margin-bottom: 9px;
  font-size: 13px;
  font-weight: 600;
}

.source-text textarea {
  resize: vertical;
}

.source-text span {
  display: block;
  margin-top: 5px;
  color: #a0a9b8;
  font-size: 11px;
  text-align: right;
}

.extract-button {
  margin-top: 18px;
}

.candidate-section {
  margin-top: 28px;
}

.candidate-section > h3 {
  font-size: 15px;
}

.candidate-card {
  background: #fafbff;
}

.candidate-actions {
  margin-top: 15px;
}

/* 编辑弹窗 */

.editor-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(20, 32, 55, .45);
}

.editor-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(530px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 25px;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 15px 40px rgba(20, 32, 55, .15);
}

.editor-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.editor-title h3 {
  margin: 0;
  font-size: 19px;
}

.editor-card label {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
}

.editor-card textarea {
  resize: vertical;
}

.editor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.editor-note {
  color: #98a2b3;
  font-size: 12px;
}

.editor-actions {
  justify-content: flex-end;
  margin-top: 8px;
}

@media (max-width: 650px) {
  .memory-overlay {
    padding: 6px;
  }

  .memory-panel {
    height: 96vh;
  }

  .memory-header,
  .memory-content {
    padding-left: 15px;
    padding-right: 15px;
  }

  .memory-tabs {
    padding-left: 15px;
    padding-right: 15px;
  }

  .memory-card-top {
    flex-direction: column;
  }

  .memory-toolbar select {
    flex: 1;
  }

  .editor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
