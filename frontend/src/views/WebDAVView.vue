<template>
  <n-space vertical size="large">
    <n-h1>WebDAV 导入导出</n-h1>

    <n-alert type="info">
      当前阶段支持 WebDAV 配置管理和连接测试；密码只写入后端，不会在列表中回显。
    </n-alert>

    <n-card title="创建 WebDAV 配置">
      <n-form :model="form" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="坚果云 / Nextcloud" /></n-form-item-gi>
          <n-form-item-gi label="URL"><n-input v-model:value="form.url" placeholder="https://example.com/dav/path 或 mock://webdav" /></n-form-item-gi>
          <n-form-item-gi label="用户名"><n-input v-model:value="form.username" placeholder="可选" /></n-form-item-gi>
          <n-form-item-gi label="密码"><n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="可选" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建配置</n-button>
      </n-form>
    </n-card>

    <n-card title="WebDAV 配置列表">
      <n-data-table :columns="columns" :data="profiles" :loading="loading" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NPopconfirm, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { createWebDAVProfile, deleteWebDAVProfile, fetchWebDAVProfiles, testWebDAVProfile, updateWebDAVProfile, type WebDAVProfile } from '../api/webdav'

const message = useMessage()
const profiles = ref<WebDAVProfile[]>([])
const loading = ref(false)
const saving = ref(false)
const testingId = ref<number | null>(null)
const updatingId = ref<number | null>(null)
const form = reactive({
  name: '',
  url: '',
  username: '',
  password: '',
  enabled: true
})
const columns = [
  { title: '名称', key: 'name' },
  { title: 'URL', key: 'url' },
  { title: '用户名', key: 'username', render: (row: WebDAVProfile) => row.username || '-' },
  {
    title: '密码',
    key: 'password_configured',
    render(row: WebDAVProfile) {
      return h(NTag, { size: 'small', type: row.password_configured ? 'success' : 'default' }, { default: () => row.password_configured ? '已配置' : '未配置' })
    }
  },
  {
    title: '状态',
    key: 'enabled',
    render(row: WebDAVProfile) {
      return h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: WebDAVProfile) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', loading: testingId.value === row.id, onClick: () => handleTest(row) }, { default: () => '测试连接' }),
          h(NButton, { size: 'small', loading: updatingId.value === row.id, onClick: () => toggleProfile(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NButton, { size: 'small', onClick: () => clearPassword(row) }, { default: () => '清除密码' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            default: () => '删除后不可恢复，是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

async function loadProfiles() {
  loading.value = true
  try {
    profiles.value = await fetchWebDAVProfiles()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.name || !form.url) {
    message.warning('请填写名称和 URL')
    return
  }
  saving.value = true
  try {
    await createWebDAVProfile({
      name: form.name,
      url: form.url,
      username: form.username || null,
      password: form.password || null,
      enabled: form.enabled
    })
    form.name = ''
    form.url = ''
    form.username = ''
    form.password = ''
    form.enabled = true
    message.success('WebDAV 配置已创建')
    await loadProfiles()
  } finally {
    saving.value = false
  }
}

async function handleTest(row: WebDAVProfile) {
  testingId.value = row.id
  try {
    const result = await testWebDAVProfile(row.id)
    if (result.ok) {
      message.success(result.message)
    } else {
      message.error(result.status_code ? `${result.message} (${result.status_code})` : result.message)
    }
  } finally {
    testingId.value = null
  }
}

async function toggleProfile(row: WebDAVProfile) {
  updatingId.value = row.id
  try {
    await updateWebDAVProfile(row.id, { enabled: !row.enabled })
    message.success(row.enabled ? '配置已禁用' : '配置已启用')
    await loadProfiles()
  } finally {
    updatingId.value = null
  }
}

async function clearPassword(row: WebDAVProfile) {
  await updateWebDAVProfile(row.id, { password: null })
  message.success('密码已清除')
  await loadProfiles()
}

async function handleDelete(row: WebDAVProfile) {
  await deleteWebDAVProfile(row.id)
  message.success('WebDAV 配置已删除')
  await loadProfiles()
}

onMounted(loadProfiles)
</script>
