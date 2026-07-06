<template>
  <n-space vertical size="large">
    <n-h1>Agent 配置</n-h1>

    <n-alert type="info">
      当前阶段用于记录本机 Agent 配置路径和备份状态；后续会接入实际导入、导出和同步流程。
    </n-alert>

    <n-card title="新增 Agent 配置">
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
import { h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NPopconfirm, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { checkAgent, createAgent, deleteAgent, fetchAgents, updateAgent, type AgentConfig } from '../api/agents'

const message = useMessage()
const agents = ref<AgentConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const checkingId = ref<number | null>(null)
const updatingId = ref<number | null>(null)
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
