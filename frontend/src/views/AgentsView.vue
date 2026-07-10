<template>
  <n-space vertical size="large">
    <n-h1>Agent 配置</n-h1>

    <n-alert type="info">
      Claude Code 已支持生成独立 Profile。配置文件不会保存 API Token，启动时通过 ANTHROPIC_AUTH_TOKEN 注入。
    </n-alert>

    <n-card title="Claude Code Profile 写入">
      <n-form :model="claudeForm" label-placement="left" label-width="150">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="Profile 名称">
            <n-input v-model:value="claudeForm.profile_name" placeholder="apiswitch" />
          </n-form-item-gi>
          <n-form-item-gi label="APISwitch Base URL">
            <n-input v-model:value="claudeForm.base_url" placeholder="http://127.0.0.1:8080" />
          </n-form-item-gi>
          <n-form-item-gi label="统一模型">
            <n-input v-model:value="claudeForm.model" placeholder="code-best" />
          </n-form-item-gi>
          <n-form-item-gi label="推理强度">
            <n-select v-model:value="claudeForm.effort_level" clearable :options="effortOptions" />
          </n-form-item-gi>
          <n-form-item-gi label="最大输出 Token">
            <n-input-number v-model:value="claudeForm.max_output_tokens" :min="1" clearable />
          </n-form-item-gi>
          <n-form-item-gi label="自动压缩窗口">
            <n-input-number v-model:value="claudeForm.auto_compact_window" :min="1" clearable />
          </n-form-item-gi>
        </n-grid>
        <n-space>
          <n-button :loading="writingClaude" @click="handleClaudeCode(true)">预览配置</n-button>
          <n-button type="primary" :loading="writingClaude" @click="handleClaudeCode(false)">写入 Profile</n-button>
        </n-space>
      </n-form>

      <n-alert v-if="claudeResult" :type="claudeResult.written ? 'success' : 'info'" style="margin-top: 16px">
        <n-space vertical>
          <div><strong>{{ claudeResult.message }}</strong></div>
          <div>配置目录：{{ claudeResult.config_dir }}</div>
          <div>配置文件：{{ claudeResult.settings_path }}</div>
          <div v-if="claudeResult.backup_path">原配置备份：{{ claudeResult.backup_path }}</div>
          <div>PowerShell 启动命令：</div>
          <n-code :code="claudeResult.powershell_command" word-wrap />
          <div>POSIX 启动命令：</div>
          <n-code :code="claudeResult.posix_command" word-wrap />
          <div>settings.json：</div>
          <n-code :code="claudeSettingsText" language="json" word-wrap />
        </n-space>
      </n-alert>
    </n-card>

    <n-card title="手动新增 Agent 配置">
      <n-form :model="form" label-placement="left" label-width="120">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="Agent 类型"><n-select v-model:value="form.agent_type" :options="agentTypeOptions" /></n-form-item-gi>
          <n-form-item-gi label="配置路径"><n-input v-model:value="form.config_path" placeholder="例如 ~/.claude/settings.json 或 mock://agent" /></n-form-item-gi>
          <n-form-item-gi label="备份路径"><n-input v-model:value="form.last_backup_path" placeholder="可选" /></n-form-item-gi>
          <n-form-item-gi label="备注"><n-input v-model:value="form.notes" placeholder="可选" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建 Agent 配置</n-button>
      </n-form>
    </n-card>

    <n-card title="Agent 配置列表">
      <n-data-table :columns="columns" :data="agents" :loading="loading" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCode,
  NDataTable,
  NForm,
  NFormItemGi,
  NGrid,
  NH1,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  useMessage
} from 'naive-ui'
import {
  checkAgent,
  createAgent,
  deleteAgent,
  fetchAgents,
  updateAgent,
  writeClaudeCodeProfile,
  type AgentConfig,
  type ClaudeCodeProfileWriteResult
} from '../api/agents'

const message = useMessage()
const agents = ref<AgentConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const writingClaude = ref(false)
const checkingId = ref<number | null>(null)
const updatingId = ref<number | null>(null)
const claudeResult = ref<ClaudeCodeProfileWriteResult | null>(null)
const claudeSettingsText = computed(() => JSON.stringify(claudeResult.value?.settings ?? {}, null, 2))

const claudeForm = reactive({
  profile_name: 'apiswitch',
  base_url: 'http://127.0.0.1:8080',
  model: 'code-best',
  effort_level: null as string | null,
  max_output_tokens: null as number | null,
  auto_compact_window: null as number | null
})
const effortOptions = [
  { label: 'low', value: 'low' },
  { label: 'medium', value: 'medium' },
  { label: 'high', value: 'high' },
  { label: 'xhigh', value: 'xhigh' }
]

const form = reactive({
  agent_type: 'claude-code',
  config_path: '',
  last_backup_path: '',
  enabled: true,
  notes: ''
})
const agentTypeOptions = [
  { label: 'Claude Code', value: 'claude-code' },
  { label: 'Gemini CLI', value: 'gemini-cli' },
  { label: 'Codex CLI', value: 'codex-cli' },
  { label: 'Cursor', value: 'cursor' },
  { label: '自定义', value: 'custom' }
]
const columns = [
  { title: 'Agent 类型', key: 'agent_type' },
  { title: '配置路径', key: 'config_path', render: (row: AgentConfig) => row.config_path || '-' },
  { title: '备份路径', key: 'last_backup_path', render: (row: AgentConfig) => row.last_backup_path || '-' },
  {
    title: '配置存在',
    key: 'config_exists',
    render(row: AgentConfig) {
      return h(NTag, { size: 'small', type: row.config_exists ? 'success' : 'warning' }, { default: () => row.config_exists ? '存在' : '未找到' })
    }
  },
  {
    title: '备份状态',
    key: 'backup_configured',
    render(row: AgentConfig) {
      return h(NTag, { size: 'small', type: row.backup_configured ? 'success' : 'default' }, { default: () => row.backup_configured ? '已记录' : '未记录' })
    }
  },
  {
    title: '状态',
    key: 'enabled',
    render(row: AgentConfig) {
      return h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  { title: '备注', key: 'notes', render: (row: AgentConfig) => row.notes || '-' },
  {
    title: '操作',
    key: 'actions',
    render(row: AgentConfig) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', loading: checkingId.value === row.id, onClick: () => handleCheck(row) }, { default: () => '检查路径' }),
          h(NButton, { size: 'small', loading: updatingId.value === row.id, onClick: () => toggleAgent(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NButton, { size: 'small', onClick: () => markBackup(row) }, { default: () => '记录备份' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            default: () => '删除后不可恢复，是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

async function loadAgents() {
  loading.value = true
  try {
    agents.value = await fetchAgents()
  } finally {
    loading.value = false
  }
}

async function handleClaudeCode(dryRun: boolean) {
  if (!claudeForm.profile_name || !claudeForm.base_url || !claudeForm.model) {
    message.warning('请填写 Profile 名称、Base URL 和统一模型')
    return
  }
  writingClaude.value = true
  try {
    claudeResult.value = await writeClaudeCodeProfile({
      profile_name: claudeForm.profile_name,
      base_url: claudeForm.base_url,
      model: claudeForm.model,
      effort_level: claudeForm.effort_level,
      max_output_tokens: claudeForm.max_output_tokens,
      auto_compact_window: claudeForm.auto_compact_window,
      dry_run: dryRun
    })
    message.success(dryRun ? 'Claude Code 配置预览已生成' : 'Claude Code Profile 已写入')
    if (!dryRun) await loadAgents()
  } catch (error) {
    message.error(`Claude Code 配置失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    writingClaude.value = false
  }
}

async function handleCreate() {
  if (!form.agent_type) {
    message.warning('请选择 Agent 类型')
    return
  }
  saving.value = true
  try {
    await createAgent({
      agent_type: form.agent_type,
      config_path: form.config_path || null,
      last_backup_path: form.last_backup_path || null,
      enabled: form.enabled,
      notes: form.notes || null,
      settings: {}
    })
    form.agent_type = 'claude-code'
    form.config_path = ''
    form.last_backup_path = ''
    form.enabled = true
    form.notes = ''
    message.success('Agent 配置已创建')
    await loadAgents()
  } finally {
    saving.value = false
  }
}

async function handleCheck(row: AgentConfig) {
  checkingId.value = row.id
  try {
    const result = await checkAgent(row.id)
    if (result.ok) {
      message.success(result.message)
    } else {
      message.warning(result.message)
    }
    await loadAgents()
  } finally {
    checkingId.value = null
  }
}

async function toggleAgent(row: AgentConfig) {
  updatingId.value = row.id
  try {
    await updateAgent(row.id, { enabled: !row.enabled })
    message.success(row.enabled ? 'Agent 已禁用' : 'Agent 已启用')
    await loadAgents()
  } finally {
    updatingId.value = null
  }
}

async function markBackup(row: AgentConfig) {
  const backupPath = window.prompt('输入最近备份路径', row.last_backup_path || '')
  if (backupPath === null) return
  await updateAgent(row.id, { last_backup_path: backupPath || null })
  message.success('备份路径已记录')
  await loadAgents()
}

async function handleDelete(row: AgentConfig) {
  await deleteAgent(row.id)
  message.success('Agent 配置已删除')
  await loadAgents()
}

onMounted(loadAgents)
</script>
