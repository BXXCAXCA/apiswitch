<template>
  <n-space vertical size="large">
    <n-h1>Agent 配置</n-h1>
    <n-alert type="info">
      已实现 Codex、OpenCode、龙虾（OpenClaw）、Hermes Agent 和 Gemini CLI。写入前会自动备份并合并现有配置；客户端 Token 只写入目标文件，不保存到 APISwitch 数据库。
    </n-alert>
    <n-card title="生成 Agent 配置">
      <n-tabs v-model:value="form.agent_type" type="segment" animated @update:value="selectAgent">
        <n-tab v-for="item in agentTypes" :key="item.value" :name="item.value">{{ item.label }}</n-tab>
      </n-tabs>
      <n-form label-placement="left" label-width="135" style="margin-top:20px">
        <n-form-item label="配置路径">
          <n-input data-testid="agent-config-path" v-model:value="form.config_path" :placeholder="currentAgent.pathHint" />
        </n-form-item>
        <n-form-item label="主模型">
          <n-select data-testid="agent-main-model" v-model:value="form.main_model_id" filterable clearable :options="modelOptions" :placeholder="`请选择支持 ${currentAgent.protocolLabel} 的统一模型`" />
        </n-form-item>
        <n-form-item label="客户端 Token">
          <n-input data-testid="agent-api-token" v-model:value="form.api_token" type="password" show-password-on="click" placeholder="可选；留空则保留现有值或使用环境变量" />
        </n-form-item>
        <n-alert type="default" style="margin-bottom:16px">
          {{ currentAgent.description }} 需要的协议：{{ currentAgent.protocolLabel }}。端口变化时，已启用配置会再次备份并只更新网关地址。
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
      <n-code v-if="previewResult" :code="previewResult.content" :language="previewResult.language" word-wrap style="margin-top:12px" />
    </n-card>
    <n-card title="已写入配置">
      <n-empty v-if="!configuredAgents.length" description="尚未写入 Agent 配置" />
      <n-data-table v-else :columns="columns" :data="configuredAgents" :pagination="false" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NCode, NDataTable, NEmpty, NForm, NFormItem, NH1, NInput, NSelect, NSpace, NTab, NTabs, NTag, useMessage } from 'naive-ui'
import { getJson, postJson } from '../api/client'

const message = useMessage()
const models = ref<any[]>([])
const agents = ref<any[]>([])
const previewResult = ref<any>()
const working = ref(false)
const agentTypes = [
  { label: 'Codex', value: 'codex', protocol: 'openai_responses', protocolLabel: 'OpenAI Responses', pathHint: '~/.codex/config.toml', description: '写入自定义 model_provider，并选择 APISwitch 统一模型。' },
  { label: 'OpenCode', value: 'opencode', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.config/opencode/opencode.json', description: '写入 OpenAI-compatible provider 和全局默认模型。' },
  { label: '龙虾（OpenClaw）', value: 'openclaw', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.openclaw/openclaw.json', description: '合并 APISwitch provider、模型目录和默认 Agent 模型。' },
  { label: 'Hermes', value: 'hermes', protocol: 'openai_chat', protocolLabel: 'OpenAI Chat Completions', pathHint: '~/.hermes/config.yaml', description: '写入 custom provider、默认模型与 OpenAI-compatible 地址。' },
  { label: 'Gemini CLI', value: 'gemini-cli', protocol: 'gemini_v1beta', protocolLabel: 'Gemini v1beta', pathHint: '~/.gemini/.env', description: '写入 Gemini API Base URL、默认模型和可选客户端 Token。' }
]
const form = reactive<any>({ agent_type: 'codex', config_path: '', main_model_id: null, api_token: '' })
const currentAgent = computed(() => agentTypes.find(item => item.value === form.agent_type) || agentTypes[0])
const saved = computed(() => agents.value.find(item => item.agent_type === form.agent_type))
const configuredAgents = computed(() => agents.value.filter(item => agentTypes.some(agent => agent.value === item.agent_type)))
const modelOptions = computed(() => models.value
  .filter(item => item.enabled && (item.enabled_protocols || []).includes(currentAgent.value.protocol))
  .map(item => ({ label: item.name, value: item.id })))
const columns: any[] = [
  { title: 'Agent', key: 'label' },
  { title: '配置路径', key: 'config_path', ellipsis: { tooltip: true } },
  { title: '状态', key: 'enabled', render: (row: any) => h(NTag, { type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '已启用' : '未启用' }) },
  { title: '最后网关地址', key: 'last_written_base_url', render: (row: any) => row.last_written_base_url || '-' },
  { title: '最近备份', key: 'last_backup_path', ellipsis: { tooltip: true }, render: (row: any) => row.last_backup_path || '-' }
]

function payload() {
  return { config_path: form.config_path.trim() || undefined, main_model_id: form.main_model_id, api_token: form.api_token.trim() || undefined }
}
function selectAgent() {
  previewResult.value = undefined
  form.api_token = ''
  form.config_path = saved.value?.config_path || ''
  form.main_model_id = saved.value?.main_model_id || null
}
async function load() {
  const [modelRows, agentRows]: any[] = await Promise.all([getJson('/api/admin/unified-models'), getJson('/api/admin/agents')])
  models.value = modelRows
  agents.value = agentRows
  selectAgent()
}
async function preview() {
  if (!form.main_model_id) return message.warning('请选择主模型')
  working.value = true
  try { previewResult.value = await postJson(`/api/admin/agents/${form.agent_type}/preview`, payload()) }
  catch (error) { message.error(String(error)) }
  finally { working.value = false }
}
async function write() {
  if (!form.main_model_id) return message.warning('请选择主模型')
  working.value = true
  try {
    const result: any = await postJson(`/api/admin/agents/${form.agent_type}/write`, payload())
    message.success(`配置已写入 ${result.path}`)
    form.api_token = ''
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
