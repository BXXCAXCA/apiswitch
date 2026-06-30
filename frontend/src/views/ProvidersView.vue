<template>
  <n-space vertical size="large">
    <n-h1>上游平台</n-h1>

    <n-card title="新增 Provider">
      <n-form :model="form" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="openai-main" /></n-form-item-gi>
          <n-form-item-gi label="类型"><n-select v-model:value="form.type" :options="typeOptions" @update:value="handleCreateTypeChange" /></n-form-item-gi>
          <n-form-item-gi label="Base URL"><n-input v-model:value="form.base_url" placeholder="https://api.openai.com/v1" /></n-form-item-gi>
          <n-form-item-gi label="API Key"><n-input v-model:value="form.api_key" type="password" show-password-on="click" placeholder="仅保存，不会明文返回" /></n-form-item-gi>
          <n-form-item-gi label="超时秒数"><n-input-number v-model:value="form.timeout_seconds" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建 Provider</n-button>
      </n-form>
    </n-card>

    <n-card title="Provider 列表">
      <n-data-table :columns="columns" :data="providers" />
    </n-card>

    <n-modal v-model:show="editing" preset="card" title="编辑 Provider" style="max-width: 760px">
      <n-form :model="editForm" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="editForm.name" /></n-form-item-gi>
          <n-form-item-gi label="类型"><n-select v-model:value="editForm.type" :options="typeOptions" @update:value="handleEditTypeChange" /></n-form-item-gi>
          <n-form-item-gi label="Base URL"><n-input v-model:value="editForm.base_url" /></n-form-item-gi>
          <n-form-item-gi label="新 API Key"><n-input v-model:value="editForm.api_key" type="password" show-password-on="click" placeholder="留空则不修改" /></n-form-item-gi>
          <n-form-item-gi label="超时秒数"><n-input-number v-model:value="editForm.timeout_seconds" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="editForm.enabled" /></n-form-item-gi>
        </n-grid>
        <n-space>
          <n-button type="primary" :loading="saving" @click="handleUpdate">保存</n-button>
          <n-button @click="editing = false">取消</n-button>
        </n-space>
      </n-form>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { createProvider, deleteProvider, fetchProviders, updateProvider, type Provider, type ProviderCreate } from '../api/providers'

const message = useMessage()
const providers = ref<Provider[]>([])
const saving = ref(false)
const editing = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<ProviderCreate>({
  name: '',
  type: 'mock',
  base_url: 'mock://local',
  api_key: '',
  enabled: true,
  timeout_seconds: 120,
  proxy_type: null,
  proxy_url: null
})
const editForm = reactive<ProviderCreate>({
  name: '',
  type: 'mock',
  base_url: 'mock://local',
  api_key: '',
  enabled: true,
  timeout_seconds: 120,
  proxy_type: null,
  proxy_url: null
})
const typeOptions = [
  { label: 'Mock', value: 'mock' },
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'OpenAI Compatible', value: 'compatible' }
]
const columns = [
  { title: 'ID', key: 'id' },
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: 'Base URL', key: 'base_url' },
  {
    title: 'API Key',
    key: 'api_key_configured',
    render(row: Provider) {
      return h(NTag, { type: row.api_key_configured ? 'success' : 'warning', size: 'small' }, { default: () => row.api_key_configured ? '已配置' : '未配置' })
    }
  },
  {
    title: '启用',
    key: 'enabled',
    render(row: Provider) {
      return h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  { title: '超时', key: 'timeout_seconds' },
  {
    title: '操作',
    key: 'actions',
    render(row: Provider) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
          h(NButton, { size: 'small', onClick: () => toggleEnabled(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            default: () => '删除后不可恢复，且正在被候选模型引用的 Provider 无法删除。',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

function defaultBaseUrl(type: string) {
  if (type === 'mock') return 'mock://local'
  if (type === 'openai') return 'https://api.openai.com/v1'
  if (type === 'anthropic') return 'https://api.anthropic.com/v1'
  if (type === 'gemini') return 'https://generativelanguage.googleapis.com/v1beta'
  if (type === 'compatible') return 'http://127.0.0.1:3000/v1'
  return ''
}

function handleCreateTypeChange(value: string) {
  form.base_url = defaultBaseUrl(value)
}

function handleEditTypeChange(value: string) {
  editForm.base_url = defaultBaseUrl(value)
}

async function loadProviders() {
  providers.value = await fetchProviders()
}

async function handleCreate() {
  if (!form.name || !form.type || !form.base_url) {
    message.warning('请填写名称、类型和 Base URL')
    return
  }
  saving.value = true
  try {
    await createProvider({ ...form, api_key: form.api_key || null })
    message.success('Provider 已创建')
    form.name = ''
    form.api_key = ''
    await loadProviders()
  } finally {
    saving.value = false
  }
}

function openEdit(row: Provider) {
  editingId.value = row.id
  editForm.name = row.name
  editForm.type = row.type
  editForm.base_url = row.base_url
  editForm.api_key = ''
  editForm.enabled = row.enabled
  editForm.timeout_seconds = row.timeout_seconds
  editForm.proxy_type = row.proxy_type ?? null
  editForm.proxy_url = row.proxy_url ?? null
  editing.value = true
}

async function handleUpdate() {
  if (!editingId.value) return
  if (!editForm.name || !editForm.type || !editForm.base_url) {
    message.warning('请填写名称、类型和 Base URL')
    return
  }
  saving.value = true
  try {
    const payload = { ...editForm, api_key: editForm.api_key || undefined }
    await updateProvider(editingId.value, payload)
    message.success('Provider 已更新')
    editing.value = false
    await loadProviders()
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: Provider) {
  await updateProvider(row.id, { enabled: !row.enabled })
  message.success(row.enabled ? 'Provider 已禁用' : 'Provider 已启用')
  await loadProviders()
}

async function handleDelete(row: Provider) {
  try {
    await deleteProvider(row.id)
    message.success('Provider 已删除')
    await loadProviders()
  } catch (error) {
    message.error(`删除失败：${error instanceof Error ? error.message : '未知错误'}`)
  }
}

onMounted(loadProviders)
</script>
