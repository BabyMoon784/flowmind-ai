<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import { getAgentDetail, createAgent, updateAgent } from '../api/agents'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  selectedAgentId: { type: String, required: true }
})

const emit = defineEmits(['close', 'saved', 'switch-agent'])

const TOOL_OPTIONS = [
  { id: 'get_task_summary', name: '任务统计', description: '读取任务数量和完成情况' },
  { id: 'list_tasks', name: '查看任务', description: '允许 AI 读取任务列表' },
  { id: 'create_task', name: '创建任务', description: '允许 AI 新建任务' },
  { id: 'update_task_status', name: '更新任务状态', description: '允许 AI 修改任务完成状态' }
]
const KNOWN_TOOL_IDS = new Set(TOOL_OPTIONS.map(item => item.id))

const DEFAULT_TOOLS = TOOL_OPTIONS.map(item => item.id)

const mode = ref('edit')
const editingId = ref(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorText = ref('')
const successText = ref('')
let loadVersion = 0

const form = reactive({
  name: '',
  description: '',
  personality: '',
  response_style: '',
  custom_instructions: '',
  enabled_tools: []
})

const isEditing = computed(() => mode.value === 'edit' && Boolean(editingId.value))
const canSave = computed(() => form.name.trim().length > 0 && !isLoading.value && !isSaving.value)
const unknownTools = computed(() => form.enabled_tools.filter(id => !KNOWN_TOOL_IDS.has(id)))

function resetForm(agent = null) {
  form.name = agent?.name ?? ''
  form.description = agent?.description ?? ''
  form.personality = ['companion', 'creative', 'efficient', 'professional'].includes(agent?.personality)
    ? agent.personality
    : 'professional'
  form.response_style = ['balanced', 'concise', 'detailed'].includes(agent?.response_style)
    ? agent.response_style
    : 'balanced'
  form.custom_instructions = agent?.custom_instructions ?? ''
  form.enabled_tools = Array.isArray(agent?.enabled_tools)
    ? [...agent.enabled_tools]
    : [...DEFAULT_TOOLS]
}

function startCreate() {
  if (isSaving.value) return
  loadVersion += 1
  isLoading.value = false
  mode.value = 'create'
  editingId.value = null
  errorText.value = ''
  successText.value = ''
  resetForm()
}

function requestErrorMessage(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail) return JSON.stringify(detail)
  return err?.message || '请求失败，请检查后端服务。'
}

async function openAgent(agentId) {
  if (!agentId || isSaving.value) return
  const currentVersion = ++loadVersion
  mode.value = 'edit'
  editingId.value = agentId
  errorText.value = ''
  successText.value = ''
  isLoading.value = true

  try {
    // 获取完整配置，避免 Agent 列表只返回摘要时误覆盖字段。
    const response = await getAgentDetail(agentId)
    if (currentVersion !== loadVersion) return
    const agent = response.data?.agent ?? response.data
    if (!agent || typeof agent !== 'object' || !agent.id) {
      throw new Error('Agent 详情数据格式不正确')
    }
    const fromList = props.agents.find(item => item.id === agentId) || {}
    resetForm({ ...fromList, ...agent })
  } catch (err) {
    if (currentVersion !== loadVersion) return
    errorText.value = `加载 Agent 失败：${requestErrorMessage(err)}`
  } finally {
    if (currentVersion === loadVersion) isLoading.value = false
  }
}

function toggleTool(toolId, checked) {
  if (checked && !form.enabled_tools.includes(toolId)) {
    form.enabled_tools = [...form.enabled_tools, toolId]
  } else if (!checked) {
    form.enabled_tools = form.enabled_tools.filter(id => id !== toolId)
  }
}

async function saveAgent() {
  if (!canSave.value) return
  errorText.value = ''
  successText.value = ''
  isSaving.value = true

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    personality: form.personality.trim(),
    response_style: form.response_style.trim(),
    custom_instructions: form.custom_instructions.trim(),
    enabled_tools: [...form.enabled_tools]
  }

  try {
    const creating = !isEditing.value
    const response = creating
      ? await createAgent(payload)
      : await updateAgent(editingId.value, payload)
    const record = response.data?.agent ?? response.data
    const savedId = record?.id || editingId.value

    if (!savedId) throw new Error('保存成功，但服务器未返回 Agent ID')

    mode.value = 'edit'
    editingId.value = savedId
    successText.value = creating ? 'Agent 创建成功！现在可以切换到它聊天。' : 'Agent 配置已保存。'
    emit('saved', { id: savedId, created: creating })
  } catch (err) {
    errorText.value = requestErrorMessage(err)
  } finally {
    isSaving.value = false
  }
}

function chooseForChat() {
  if (!editingId.value || isSaving.value) return
  emit('switch-agent', editingId.value)
}

function close() {
  if (!isSaving.value) emit('close')
}

onMounted(() => {
  const initialId = props.agents.some(agent => agent.id === props.selectedAgentId)
    ? props.selectedAgentId
    : props.agents[0]?.id
  if (initialId) openAgent(initialId)
  else startCreate()
})
</script>

<template>
  <div class="agent-overlay" @click.self="close">
    <section class="agent-dialog" role="dialog" aria-modal="true" aria-label="Agent 管理中心">
      <header class="agent-dialog-header">
        <div>
          <div class="agent-eyebrow">FLOWMIND AI / AGENTS</div>
          <h2>Agent 管理中心</h2>
          <p>定制每个 AI 助手的定位、性格、回复方式与工具权限。</p>
        </div>
        <button class="agent-close" type="button" aria-label="关闭管理中心" @click="close">×</button>
      </header>

      <div class="agent-dialog-body">
        <aside class="agent-manager-list">
          <div class="agent-list-heading">我的 Agent <span>{{ agents.length }}</span></div>
          <button type="button" class="agent-add" :disabled="isSaving" @click="startCreate">＋ 创建新 Agent</button>
          <button
            v-for="agent in agents"
            :key="agent.id"
            type="button"
            class="agent-list-row"
            :class="{ active: isEditing && editingId === agent.id }"
            :disabled="isSaving"
            @click="openAgent(agent.id)"
          >
            <span class="agent-list-avatar">{{ (agent.name || 'A').slice(0, 1).toUpperCase() }}</span>
            <span class="agent-list-info">
              <strong>{{ agent.name }}</strong>
              <small>{{ agent.description || '尚未填写介绍' }}</small>
            </span>
          </button>
        </aside>

        <div class="agent-editor">
          <div class="agent-editor-top">
            <div>
              <h3>{{ isEditing ? '编辑 Agent' : '创建 Agent' }}</h3>
              <p>{{ isEditing ? '修改会影响该 Agent 今后的回复，不会删除历史对话。' : '创建后即可在聊天工作台中切换使用。' }}</p>
            </div>
            <span class="agent-mode-label">{{ isEditing ? 'EDIT' : 'NEW' }}</span>
          </div>

          <div v-if="errorText" class="agent-alert error" role="alert">{{ errorText }}</div>
          <div v-if="successText" class="agent-alert success" role="status">{{ successText }}</div>
          <div v-if="isLoading" class="agent-loading">正在加载 Agent 配置...</div>

          <form v-else class="agent-form" @submit.prevent="saveAgent">
            <label class="agent-field">
              <span>Agent 名称 <em>*</em></span>
              <input v-model="form.name" maxlength="60" required placeholder="例如：CodeMate" />
            </label>

            <label class="agent-field">
              <span>一句话介绍</span>
              <input v-model="form.description" maxlength="240" placeholder="例如：专注 Python 与 AI 应用开发" />
            </label>

            <div class="agent-field-grid">
              <label class="agent-field">
                <span>人格类型</span>
                <select v-model="form.personality" required>
                  <option value="professional">专业型 · 严谨、准确</option>
                  <option value="companion">陪伴型 · 耐心、亲和</option>
                  <option value="creative">创意型 · 灵活、发散</option>
                  <option value="efficient">高效型 · 简洁、直接</option>
                </select>
                <small>具体性格描述可写在下方「自定义指令」中。</small>
              </label>
              <label class="agent-field">
                <span>回复风格</span>
                <select v-model="form.response_style" required>
                  <option value="balanced">均衡 · 详略适中</option>
                  <option value="concise">简洁 · 突出重点</option>
                  <option value="detailed">详细 · 分步骤讲解</option>
                </select>
                <small>如需固定中文或讲解顺序，也请写在「自定义指令」中。</small>
              </label>
            </div>

            <label class="agent-field">
              <span>自定义指令</span>
              <textarea
                v-model="form.custom_instructions"
                rows="4"
                placeholder="例如：讲解代码时先解释思路，再给完整示例。不要编造运行结果。"
              ></textarea>
              <small>这里是发送给 Agent 的持久指令，不要填写密码、密钥或个人隐私。</small>
            </label>

            <fieldset class="agent-tools">
              <legend>工具权限</legend>
              <p>取消勾选可以限制该 Agent 使用对应工具。</p>
              <div class="agent-tool-grid">
                <label v-for="tool in TOOL_OPTIONS" :key="tool.id" class="agent-tool">
                  <input
                    type="checkbox"
                    :checked="form.enabled_tools.includes(tool.id)"
                    @change="toggleTool(tool.id, $event.target.checked)"
                  />
                  <span>
                    <strong>{{ tool.name }}</strong>
                    <small>{{ tool.description }}</small>
                  </span>
                </label>
              </div>
              <p v-if="unknownTools.length" class="agent-unknown">
                另外保留了当前 Agent 的其他工具权限：{{ unknownTools.join('、') }}
              </p>
            </fieldset>

            <div class="agent-editor-actions">
              <button type="button" class="agent-secondary" @click="close" :disabled="isSaving">关闭</button>
              <button
                v-if="isEditing"
                type="button"
                class="agent-secondary"
                @click="chooseForChat"
                :disabled="isSaving"
              >切换到此 Agent 聊天</button>
              <button type="submit" class="agent-primary" :disabled="!canSave">
                {{ isSaving ? '保存中...' : isEditing ? '保存修改' : '创建 Agent' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.agent-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(19, 32, 55, 0.48);
  display: grid;
  place-items: center;
  padding: 22px;
}
.agent-dialog {
  width: min(1020px, 100%);
  height: min(760px, 94vh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 17px;
  box-shadow: 0 24px 70px rgba(0, 20, 65, 0.18);
  color: #273348;
}
.agent-dialog-header {
  padding: 22px 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid #e9edf5;
}
.agent-dialog-header h2 { margin: 5px 0 6px; font-size: 21px; }
.agent-dialog-header p { margin: 0; color: #8794aa; font-size: 13px; }
.agent-eyebrow { font-size: 10px; letter-spacing: 1.8px; font-weight: 700; color: #6680c5; }
.agent-close { border: 0; background: #f3f6fb; color: #71809b; width: 35px; height: 35px; border-radius: 9px; font-size: 24px; cursor: pointer; }
.agent-dialog-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 228px minmax(0, 1fr); }
.agent-manager-list { overflow-y: auto; background: #f8faff; padding: 20px 12px; border-right: 1px solid #e9edf5; }
.agent-list-heading { display: flex; justify-content: space-between; margin: 3px 8px 15px; color: #7c899f; font-size: 12px; font-weight: 700; }
.agent-list-heading span { background: #e7edfb; color: #526cb4; border-radius: 20px; padding: 2px 7px; }
.agent-add { width: 100%; padding: 12px 11px; border: 1px dashed #a0b2e9; border-radius: 10px; background: #edf2ff; color: #4567bc; font-size: 13px; font-weight: 600; text-align: left; cursor: pointer; }
.agent-list-row { width: 100%; display: flex; align-items: center; gap: 9px; margin-top: 9px; padding: 10px 8px; background: transparent; border: 1px solid transparent; border-radius: 10px; text-align: left; cursor: pointer; color: #32415a; }
.agent-list-row:hover { background: #eef2fc; }
.agent-list-row.active { background: #e9efff; border-color: #cfdbfa; }
.agent-list-avatar { width: 34px; height: 34px; border-radius: 9px; background: #dce6ff; display: grid; place-items: center; flex: 0 0 auto; color: #5673c1; font-weight: 700; }
.agent-list-info { display: grid; gap: 3px; overflow: hidden; }
.agent-list-info strong, .agent-list-info small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-list-info strong { font-size: 13px; }
.agent-list-info small { color: #8b97aa; font-size: 11px; }
.agent-editor { min-width: 0; min-height: 0; padding: 23px 28px 26px; overflow-y: auto; }
.agent-editor-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
.agent-editor-top h3 { font-size: 18px; margin: 0 0 6px; }
.agent-editor-top p { font-size: 12px; color: #8a96aa; margin: 0; line-height: 1.7; }
.agent-mode-label { font-size: 11px; color: #6a83c8; font-weight: 700; letter-spacing: 1px; }
.agent-alert { padding: 12px 14px; border-radius: 9px; font-size: 12px; line-height: 1.6; margin-bottom: 16px; }
.agent-alert.error { background: #fff0f0; color: #bf4747; }
.agent-alert.success { background: #e9f8ef; color: #308659; }
.agent-loading { color: #7d8ca3; padding: 20px 0; font-size: 13px; }
.agent-form { display: grid; gap: 16px; }
.agent-field { display: grid; gap: 8px; font-size: 12px; font-weight: 600; color: #526078; }
.agent-field em { color: #d55055; font-style: normal; }
.agent-field input, .agent-field textarea, .agent-field select { font: inherit; font-weight: 400; color: #28364e; padding: 11px 12px; border: 1px solid #dce4f1; border-radius: 9px; outline: none; background: #fff; width: 100%; }
.agent-field textarea { resize: vertical; }
.agent-field select { min-height: 44px; cursor: pointer; }
.agent-field input:focus, .agent-field textarea:focus, .agent-field select:focus { border-color: #6787da; box-shadow: 0 0 0 3px #6787da20; }
.agent-field small { color: #95a0b2; font-size: 11px; font-weight: 400; line-height: 1.6; }
.agent-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.agent-tools { min-width: 0; margin: 2px 0 0; padding: 13px 15px 15px; border: 1px solid #e1e8f3; border-radius: 10px; }
.agent-tools legend { color: #526078; padding: 0 5px; font-size: 12px; font-weight: 700; }
.agent-tools > p { font-size: 11px; color: #909caf; margin: 0 0 12px; }
.agent-tool-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.agent-tool { display: flex; align-items: flex-start; gap: 8px; padding: 10px; border: 1px solid #e8edf5; border-radius: 9px; cursor: pointer; }
.agent-tool input { width: 15px; height: 15px; flex: 0 0 auto; accent-color: #5b78d0; margin-top: 1px; }
.agent-tool span { display: grid; gap: 4px; }
.agent-tool strong { color: #42516b; font-size: 12px; }
.agent-tool small { color: #9aa5b7; font-size: 11px; line-height: 1.4; }
.agent-unknown { margin-top: 10px !important; word-break: break-all; }
.agent-editor-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 9px; padding-top: 9px; }
.agent-secondary, .agent-primary { padding: 10px 14px; font-size: 12px; border-radius: 9px; cursor: pointer; }
.agent-secondary { background: #fff; border: 1px solid #d8e1f1; color: #52617b; }
.agent-primary { background: #5679db; border: 1px solid #5679db; color: #fff; font-weight: 600; }
.agent-primary:disabled, .agent-secondary:disabled { opacity: 0.55; cursor: not-allowed; }
@media (max-width: 740px) {
  .agent-overlay { padding: 0; }
  .agent-dialog { height: 100dvh; border-radius: 0; }
  .agent-dialog-header { padding: 18px; }
  .agent-dialog-body { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .agent-manager-list { display: flex; gap: 7px; align-items: center; overflow-x: auto; padding: 10px; border-right: 0; border-bottom: 1px solid #e9edf5; }
  .agent-list-heading { display: none; }
  .agent-add { width: auto; flex: 0 0 auto; white-space: nowrap; }
  .agent-list-row { width: auto; flex: 0 0 auto; margin: 0; max-width: 180px; }
  .agent-list-info small { display: none; }
  .agent-editor { padding: 20px 16px; }
  .agent-field-grid, .agent-tool-grid { grid-template-columns: 1fr; }
}
</style>
