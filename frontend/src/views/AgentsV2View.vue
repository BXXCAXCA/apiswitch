<template>
  <n-space vertical size="large">
    <n-h1>Agent 配置</n-h1>
    <n-alert type="info">
      可为每个 Agent 自动创建独立 API Key，也可以手动选择已有 API Key。明文直接写入目标配置，不依赖外部环境变量；同一 Agent 可配置多个统一模型，并在写入前直接修改生成结果。
    </n-alert>
    <n-card title="生成 Agent 配置">
      <n-tabs data-testid="agent-tabs" v-model:value="form.agent_type" type="segment" animated @update:value="selectAgent">
        <n-tab v-for="item in agentTypes" :key="item.value" :name="item.value">{{ item.label }}</n-tab>
      </n-tabs>
      <n-form label-placement="left" label-width="135" style="margin-top:20px">
        <n-form-item label="配置路径">
          <n-input data-testid="agent-config-path" v-model:value="form.config_path" :placeholder="currentAgent.pathHint" />
        </n-form-item>
        <n-form-item label="默认模型">
          <n-select data-testid="agent-main-model" v-model:value="form.main_model_id" filterable clearable :options="modelOptions" :placeholder="`请选择支持 ${currentAgent.protocolLabel} 的统一模型`" @update:value="modelSelectionChanged" />
        </n-form-item>
        <n-form-item label="可用模型">
          <n-select data-testid="agent-models" v-model:value="form.model_ids" multiple filterable clearable :options="modelOptions" placeholder="可多选；默认模型会自动加入" @update:value="modelSelectionChanged" />
        </n-form-item>
        <template v-if="isClaudeCode">
          <n-form-item label="Opus 模型">
            <n-select data-testid="agent-opus-model" v-model:value="form.opus_model_id" filterable clearable :options="modelOptions" placeholder="可选；留空则使用主模型" />
          </n-form-item>
          <n-form-item label="Sonnet 模型">
            <n-select data-testid="agent-sonnet-model" v-model:value="form.sonnet_model_id" filterable clearable :options="modelOptions" placeholder="可选；留空则使用主模型" />
          </n-form-item>
          <n-form-item label="Haiku 模型">
            <n-select data-testid="agent-haiku-model" v-model:value="form.haiku_model_id" filterable clearable :options="modelOptions" placeholder="可选；留空则使用主模型" />
          </n-form-item>
        </template>
        <n-form-item label="API Key 方式">
          <n-radio-group data-testid="agent-api-key-mode" v-model:value="form.api_token_mode" @update:value="keyModeChanged">
            <n-radio-button value="auto">自动创建独立 Key</n-radio-button>
            <n-radio-button value="manual">选择现有 Key</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item v-if="form.api_token_mode === 'auto'" label="独立 API Key">
          <n-space align="center">
            <n-input data-testid="agent-api-key-status" :value="saved?.api_token_prefix ? `${saved.api_token_prefix}…（已写入配置）` : '首次写入时自动创建'" readonly style="width:300px" />
            <n-switch data-testid="agent-rotate-api-key" v-model:value="form.rotate_api_key" :disabled="!saved?.api_token_id">
              <template #checked>写入时轮换</template>
              <template #unchecked>保留当前 Key</template>
            </n-switch>
          </n-space>
        </n-form-item>
        <template v-else>
          <n-form-item label="现有 API Key">
            <n-select data-testid="agent-existing-api-key" v-model:value="form.api_token_id" filterable clearable :options="tokenOptions" placeholder="选择客户端管理中已有的 API Key" @update:value="keySelectionChanged" />
          </n-form-item>
          <n-form-item v-if="form.api_token_id" label="API Key 明文">
            <n-input data-testid="agent-existing-api-key-plain" v-model:value="form.api_token" type="password" show-password-on="click" :placeholder="manualKeyNeedsPlaintext ? '首次绑定此 Key 时请输入完整明文' : '当前配置已包含该 Key，可留空'" @update:value="previewResult = undefined" />
          </n-form-item>
          <n-alert type="warning" style="margin-bottom:16px">
            APISwitch 数据库只保存 API Key 哈希，无法反向读取明文。首次选择或更换 Key 时需输入一次明文并校验；已绑定且配置文件仍包含该 Key 时可留空。手动 Key 的模型权限不会被 Agent 配置修改。
          </n-alert>
        </template>
        <n-alert type="default" style="margin-bottom:16px">
          {{ currentAgent.description }} 需要的协议：{{ currentAgent.protocolLabel }}。明文只写入目标 Agent 配置文件；端口变化时会保留 Key 和自定义内容。
        </n-alert>
        <n-space>
          <n-button data-testid="agent-preview" :loading="working" @click="preview">预览</n-button>
          <n-button data-testid="agent-write" type="primary" :loading="working" @click="write">备份并写入</n-button>
          <n-button :disabled="!saved?.last_backup_path" @click="restore">恢复上次备份</n-button>
        </n-space>
      </n-form>
      <n-alert v-if="previewResult" type="success" style="margin-top:18px">
        <div>目标：{{ previewResult.config_path }}</div>
        <div>{{ previewResult.token_hint }}</div>
      </n-alert>
      <n-form-item v-if="previewResult" label="配置内容" label-placement="top" style="margin-top:12px">
        <n-input data-testid="agent-config-content" v-model:value="previewResult.content" type="textarea" :autosize="{ minRows: 14, maxRows: 32 }" spellcheck="false" />
      </n-form-item>
    </n-card>
    <n-card title="已写入配置">
      <n-empty v-if="!configuredAgents.length" description="尚未写入 Agent 配置" />
      <n-data-table v-else :columns="columns" :data="configuredAgents" :pagination="false" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NEmpty, NForm, NFormItem, NH1, NInput, NRadioButton, NRadioGroup, NSelect, NSpace, NSwitch, NTab, NTabs, NTag, useMessage } from 'naive-ui'
import { getJson, postJson } from '../api/client'

const message = useMessage()
const models = ref<any[]>([])
const agents = ref<any[]>([])
const tokens = ref<any[]>([])
const previewResult = ref<any>()
const working = ref(false)
const agentTypes = [
  { label: 'Claude Code', value: 'claude-code', protocol: 'anthropic_messages', protocolLabel: 'Anthropic Messages', pathHint: '~/.claude/settings.json', description: '配置可用模型及可选的 Opus、Sonnet、Haiku 模型映射。' },
  { label: 'Codex', value: 'codex', protocol: 'openai_responses', protocolLabel: 'OpenAI Responses', pathHint: '~/.codex/config.toml', description: '写入独立 model_provider、默认模型和明文 Bearer Token。' },
  { label: 'OpenCode', value: 'opencode', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.config/opencode/opencode.json', description: '写入 OpenAI-compatible provider、多个模型和默认模型。' },
  { label: '龙虾（OpenClaw）', value: 'openclaw', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.openclaw/openclaw.json', description: '合并 APISwitch provider、所选模型目录和默认 Agent 模型。' },
  { label: 'DeepSeek Harness', value: 'deepseek-harness', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.dsh/settings.yaml', description: '同步所选模型，并写入明文 Authorization 请求头和图像输入能力。' },
  { label: 'Hermes', value: 'hermes', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.hermes/config.yaml', description: '写入 custom provider、默认模型与 OpenAI-compatible 地址。' },
  { label: 'Gemini CLI', value: 'gemini-cli', protocol: 'gemini_v1beta', protocolLabel: 'Gemini v1beta', pathHint: '~/.gemini/.env', description: '写入 Gemini API Base URL、默认模型和可选客户端 Token。' },
  { label: 'Langcli', value: 'langcli', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.langcli/settings.json', description: '合并 modelProviders.openai、自定义统一模型和 APISwitch 网关地址。' }
]
const form = reactive<any>({ agent_type: 'codex', config_path: '', main_model_id: null, model_ids: [], opus_model_id: null, sonnet_model_id: null, haiku_model_id: null, api_token_mode: 'auto', api_token_id: null, api_token: '', rotate_api_key: false })
const currentAgent = computed(() => agentTypes.find(item => item.value === form.agent_type) || agentTypes[0])
const isClaudeCode = computed(() => form.agent_type === 'claude-code')
const saved = computed(() => agents.value.find(item => item.agent_type === form.agent_type))
const configuredAgents = computed(() => agents.value
  .filter(item => agentTypes.some(agent => agent.value === item.agent_type))
  .map(item => ({ ...item, label: agentTypes.find(agent => agent.value === item.agent_type)?.label || item.agent_type })))
const modelOptions = computed(() => models.value
  .filter(item => item.enabled && (item.enabled_protocols || []).includes(currentAgent.value.protocol))
  .map(item => ({ label: item.name, value: item.id })))
const selectedAgentModelIds = computed(() => Array.from(new Set([
  form.main_model_id,
  ...(form.model_ids || []),
  ...(isClaudeCode.value ? [form.opus_model_id, form.sonnet_model_id, form.haiku_model_id] : [])
].filter(Boolean))))
const tokenOptions = computed(() => tokens.value
  .filter(item => item.enabled && (item.scopes || []).includes('gateway:invoke'))
  .map(item => {
    const allowed = new Set(item.unified_model_ids || [])
    const missing = selectedAgentModelIds.value.some(id => !allowed.has(id))
    return {
      label: `${item.name} · ${item.prefix}…${missing ? '（缺少所选模型权限）' : ''}`,
      value: item.id,
      disabled: missing
    }
  }))
const manualKeyNeedsPlaintext = computed(() => form.api_token_mode === 'manual' && !!form.api_token_id && saved.value?.api_token_id !== form.api_token_id)
const columns: any[] = [
  { title: 'Agent', key: 'label' },
  { title: '模型数', key: 'model_ids', render: (row: any) => row.model_ids?.length || 0 },
  { title: 'API Key', key: 'api_token_prefix', render: (row: any) => row.api_token_prefix ? `${row.api_token_mode === 'manual' ? '手动' : '独立'} · ${row.api_token_name || row.api_token_prefix} (${row.api_token_prefix}…)` : '-' },
  { title: '配置路径', key: 'config_path', ellipsis: { tooltip: true } },
  { title: '状态', key: 'enabled', render: (row: any) => h(NTag, { type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '已启用' : '未启用' }) },
  { title: '最后网关地址', key: 'last_written_base_url', render: (row: any) => row.last_written_base_url || '-' },
  { title: '最近备份', key: 'last_backup_path', ellipsis: { tooltip: true }, render: (row: any) => row.last_backup_path || '-' }
]

function payload(includeContent = false) {
  const modelIds = Array.from(new Set([form.main_model_id, ...(form.model_ids || [])].filter(Boolean)))
  const result: any = { config_path: form.config_path.trim() || undefined, main_model_id: form.main_model_id, model_ids: modelIds, api_token_mode: form.api_token_mode, rotate_api_key: form.api_token_mode === 'auto' && form.rotate_api_key }
  if (form.api_token_mode === 'manual') {
    result.api_token_id = form.api_token_id
    if (form.api_token.trim()) result.api_token = form.api_token.trim()
  }
  if (isClaudeCode.value) {
    result.opus_model_id = form.opus_model_id
    result.sonnet_model_id = form.sonnet_model_id
    result.haiku_model_id = form.haiku_model_id
  }
  if (includeContent && previewResult.value?.content) result.content = previewResult.value.content
  return result
}
function modelSelectionChanged() { previewResult.value = undefined }
function keyModeChanged() {
  previewResult.value = undefined
  form.api_token = ''
  form.rotate_api_key = false
  form.api_token_id = form.api_token_mode === 'manual' && saved.value?.api_token_mode === 'manual' ? saved.value.api_token_id : null
}
function keySelectionChanged() { previewResult.value = undefined; form.api_token = '' }
function validateKeySelection() {
  if (form.api_token_mode !== 'manual') return true
  if (!form.api_token_id) { message.warning('请选择现有 API Key'); return false }
  if (manualKeyNeedsPlaintext.value && !form.api_token.trim()) { message.warning('首次绑定此 API Key 时请输入完整明文'); return false }
  return true
}
function selectAgent() {
  previewResult.value = undefined
  form.config_path = saved.value?.config_path || ''
  form.main_model_id = saved.value?.main_model_id || null
  form.model_ids = saved.value?.model_ids || (saved.value?.main_model_id ? [saved.value.main_model_id] : [])
  form.opus_model_id = saved.value?.opus_model_id || null
  form.sonnet_model_id = saved.value?.sonnet_model_id || null
  form.haiku_model_id = saved.value?.haiku_model_id || null
  form.api_token_mode = saved.value?.api_token_mode || 'auto'
  form.api_token_id = form.api_token_mode === 'manual' ? saved.value?.api_token_id || null : null
  form.api_token = ''
  form.rotate_api_key = false
}
async function load() {
  const [modelRows, agentRows, tokenRows]: any[] = await Promise.all([getJson('/api/admin/unified-models'), getJson('/api/admin/agents'), getJson('/api/admin/tokens')])
  models.value = modelRows
  agents.value = agentRows
  tokens.value = tokenRows
  selectAgent()
}
async function preview() {
  if (!form.main_model_id) return message.warning('请选择主模型')
  if (!validateKeySelection()) return
  working.value = true
  try {
    const result: any = await postJson(`/api/admin/agents/${form.agent_type}/preview`, payload())
    previewResult.value = {
      ...result,
      content: typeof result.content === 'string' ? result.content : JSON.stringify(result.content, null, 2),
      language: result.language || 'json',
      token_hint: result.token_hint || '可自动创建独立 API Key，也可选择已有 Key；明文直接写入目标配置。'
    }
  }
  catch (error) { message.error(String(error)) }
  finally { working.value = false }
}
async function write() {
  if (!form.main_model_id) return message.warning('请选择主模型')
  if (!validateKeySelection()) return
  working.value = true
  try {
    const result: any = await postJson(`/api/admin/agents/${form.agent_type}/write`, payload(true))
    message.success(`配置已写入 ${result.path}`)
    form.rotate_api_key = false
    await load()
    await preview()
  } catch (error) { message.error(String(error)) }
  finally { working.value = false }
}
async function restore() {
  if (!saved.value?.config_path || !saved.value?.last_backup_path) return
  try {
    await postJson(`/api/admin/agents/${form.agent_type}/restore`, { config_path: saved.value.config_path, backup_path: saved.value.last_backup_path })
    message.success('已恢复上次备份')
  } catch (error) { message.error(String(error)) }
}
onMounted(load)
</script>
