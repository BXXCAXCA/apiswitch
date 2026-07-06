<template>
  <n-space vertical size="large">
    <n-h1>API Token 管理</n-h1>

    <n-alert v-if="createdToken" type="success" title="Token 已创建，请立即复制保存">
      <n-space vertical>
        <n-code :code="createdToken" word-wrap />
        <n-button size="small" @click="createdToken = ''">我已保存，隐藏</n-button>
      </n-space>
    </n-alert>

    <n-card title="创建 Token">
      <n-form :model="form" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="local-dev" /></n-form-item-gi>
          <n-form-item-gi label="权限"><n-select v-model:value="form.scopes" multiple :options="scopeOptions" /></n-form-item-gi>
          <n-form-item-gi label="过期时间"><n-date-picker v-model:value="expiresAtMs" type="datetime" clearable /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建 Token</n-button>
      </n-form>
    </n-card>

    <n-card title="Token 列表">
      <n-data-table :columns="columns" :data="tokens" :loading="loading" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NCode, NDataTable, NDatePicker, NForm, NFormItemGi, NGrid, NH1, NInput, NPopconfirm, NSelect, NSpace, NTag, useMessage } from 'naive-ui'
import { createApiToken, deleteApiToken, fetchApiTokens, updateApiToken, type ApiToken } from '../api/tokens'

const message = useMessage()
const tokens = ref<ApiToken[]>([])
const loading = ref(false)
const saving = ref(false)
const createdToken = ref('')
const expiresAtMs = ref<number | null>(null)
const form = reactive({
  name: '',
  scopes: ['gateway:invoke']
})
const scopeOptions = [
  { label: 'gateway:invoke', value: 'gateway:invoke' },
  { label: 'gateway:read', value: 'gateway:read' },
  { label: 'admin:read', value: 'admin:read' }
]
const columns = [
  { title: 'ID', key: 'id' },
  { title: '名称', key: 'name' },
  { title: '前缀', key: 'token_prefix' },
  {
    title: '状态',
    key: 'enabled',
    render(row: ApiToken) {
      return h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  {
    title: '权限',
    key: 'scopes',
    render(row: ApiToken) {
      return row.scopes.map((scope) => h(NTag, { size: 'small', style: 'margin-right: 4px' }, { default: () => scope }))
    }
  },
  { title: '过期时间', key: 'expires_at', render: (row: ApiToken) => formatTime(row.expires_at) },
  { title: '最后使用', key: 'last_used_at', render: (row: ApiToken) => formatTime(row.last_used_at) },
  {
    title: '操作',
    key: 'actions',
    render(row: ApiToken) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => toggleToken(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            default: () => '删除后不可恢复，是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

function formatTime(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

async function loadTokens() {
  loading.value = true
  try {
    tokens.value = await fetchApiTokens()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.name) {
    message.warning('请填写 Token 名称')
    return
  }
  saving.value = true
  try {
    const created = await createApiToken({
      name: form.name,
      scopes: form.scopes,
      expires_at: expiresAtMs.value ? new Date(expiresAtMs.value).toISOString() : null
    })
    createdToken.value = created.token
    form.name = ''
    form.scopes = ['gateway:invoke']
    expiresAtMs.value = null
    message.success('Token 已创建')
    await loadTokens()
  } finally {
    saving.value = false
  }
}

async function toggleToken(row: ApiToken) {
  await updateApiToken(row.id, { enabled: !row.enabled })
  message.success(row.enabled ? 'Token 已禁用' : 'Token 已启用')
  await loadTokens()
}

async function handleDelete(row: ApiToken) {
  await deleteApiToken(row.id)
  message.success('Token 已删除')
  await loadTokens()
}

onMounted(loadTokens)
</script>
