<template>
  <n-space vertical size="large">
    <n-h1>Provider 账号与节点</n-h1>

    <n-alert type="info">
      Provider Connection 表示账号或凭据，Provider Node 表示实际请求端点。凭据只写入后端，不会在页面回显。
    </n-alert>

    <n-card title="选择 Provider">
      <n-select
        v-model:value="selectedProviderId"
        :options="providerOptions"
        placeholder="选择 Provider"
        @update:value="loadProviderData"
      />
    </n-card>

    <n-grid :cols="2" :x-gap="16" :y-gap="16">
      <n-gi>
        <n-card title="新增账号连接">
          <n-form :model="connectionForm" label-placement="left" label-width="110">
            <n-form-item label="名称"><n-input v-model:value="connectionForm.name" placeholder="personal / team" /></n-form-item>
            <n-form-item label="认证方式"><n-select v-model:value="connectionForm.auth_type" :options="authTypeOptions" /></n-form-item>
            <n-form-item label="账号标签"><n-input v-model:value="connectionForm.account_label" placeholder="可选" /></n-form-item>
            <n-form-item label="凭据"><n-input v-model:value="connectionForm.credential" type="password" show-password-on="click" /></n-form-item>
            <n-form-item label="Refresh Token"><n-input v-model:value="connectionForm.refresh_token" type="password" show-password-on="click" /></n-form-item>
            <n-form-item label="优先级"><n-input-number v-model:value="connectionForm.priority" :min="0" :max="1000" /></n-form-item>
            <n-form-item label="启用"><n-switch v-model:value="connectionForm.enabled" /></n-form-item>
            <n-button type="primary" :loading="savingConnection" @click="handleCreateConnection">创建连接</n-button>
          </n-form>
        </n-card>
      </n-gi>

      <n-gi>
        <n-card title="新增 Provider Node">
          <n-form :model="nodeForm" label-placement="left" label-width="110">
            <n-form-item label="名称"><n-input v-model:value="nodeForm.name" placeholder="official-sg" /></n-form-item>
            <n-form-item label="Base URL"><n-input v-model:value="nodeForm.base_url" /></n-form-item>
            <n-form-item label="绑定连接"><n-select v-model:value="nodeForm.connection_id" clearable :options="connectionOptions" /></n-form-item>
            <n-form-item label="Region"><n-input v-model:value="nodeForm.region" placeholder="ap-southeast-1" /></n-form-item>
            <n-form-item label="权重"><n-input-number v-model:value="nodeForm.weight" :min="0" :max="1000" /></n-form-item>
            <n-form-item label="能力"><n-input v-model:value="nodeForm.capabilities" placeholder="chat,embeddings,images" /></n-form-item>
            <n-form-item label="启用"><n-switch v-model:value="nodeForm.enabled" /></n-form-item>
            <n-button type="primary" :loading="savingNode" @click="handleCreateNode">创建节点</n-button>
          </n-form>
        </n-card>
      </n-gi>
    </n-grid>

    <n-card title="账号连接">
      <n-data-table :columns="connectionColumns" :data="connections" :loading="loading" />
    </n-card>

    <n-card title="Provider Nodes">
      <n-data-table :columns="nodeColumns" :data="nodes" :loading="loading" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NGi,
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
import { fetchProviders, type Provider } from '../api/providers'
import {
  createProviderConnection,
  createProviderNode,
  deleteProviderConnection,
  deleteProviderNode,
  fetchProviderConnections,
  fetchProviderNodes,
  updateProviderConnection,
  updateProviderNode,
  type ProviderConnection,
  type ProviderNode
} from '../api/providerConnections'

const message = useMessage()
const providers = ref<Provider[]>([])
const selectedProviderId = ref<number | null>(null)
const connections = ref<ProviderConnection[]>([])
const nodes = ref<ProviderNode[]>([])
const loading = ref(false)
const savingConnection = ref(false)
const savingNode = ref(false)

const connectionForm = reactive({
  name: '',
  auth_type: 'api_key',
  account_label: '',
  credential: '',
  refresh_token: '',
  priority: 100,
  enabled: true
})
const nodeForm = reactive({
  name: '',
  base_url: '',
  connection_id: null as number | null,
  region: '',
  weight: 100,
  capabilities: 'chat',
  enabled: true
})
const authTypeOptions = [
  { label: 'API Key', value: 'api_key' },
  { label: 'OAuth', value: 'oauth' },
  { label: 'Anonymous / Free', value: 'anonymous' }
]
const providerOptions = computed(() => providers.value.map((item) => ({ label: `${item.name} (${item.type})`, value: item.id })))
const connectionOptions = computed(() => connections.value.map((item) => ({ label: item.name, value: item.id })))

const connectionColumns = [
  { title: '名称', key: 'name' },
  { title: '认证', key: 'auth_type' },
  { title: '账号标签', key: 'account_label', render: (row: ProviderConnection) => row.account_label || '-' },
  { title: '优先级', key: 'priority' },
  {
    title: '凭据',
    key: 'credential_configured',
    render: (row: ProviderConnection) => h(NTag, { size: 'small', type: row.credential_configured ? 'success' : 'default' }, { default: () => row.credential_configured ? '已配置' : '未配置' })
  },
  {
    title: '状态',
    key: 'enabled',
    render: (row: ProviderConnection) => h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '禁用' })
  },
  {
    title: '操作',
    key: 'actions',
    render(row: ProviderConnection) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => toggleConnection(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDeleteConnection(row) }, {
            default: () => '节点仍绑定此连接时不能删除。是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

const nodeColumns = [
  { title: '名称', key: 'name' },
  { title: 'Base URL', key: 'base_url' },
  { title: 'Region', key: 'region', render: (row: ProviderNode) => row.region || '-' },
  { title: '连接 ID', key: 'connection_id', render: (row: ProviderNode) => row.connection_id || '-' },
  { title: '权重', key: 'weight' },
  { title: '能力', key: 'capabilities', render: (row: ProviderNode) => row.capabilities.join(', ') || '-' },
  {
    title: '状态',
    key: 'enabled',
    render: (row: ProviderNode) => h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '禁用' })
  },
  {
    title: '操作',
    key: 'actions',
    render(row: ProviderNode) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => toggleNode(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDeleteNode(row) }, {
            default: () => '删除此节点？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

async function loadProviderData() {
  if (!selectedProviderId.value) {
    connections.value = []
    nodes.value = []
    return
  }
  loading.value = true
  try {
    const [connectionItems, nodeItems] = await Promise.all([
      fetchProviderConnections(selectedProviderId.value),
      fetchProviderNodes(selectedProviderId.value)
    ])
    connections.value = connectionItems
    nodes.value = nodeItems
  } finally {
    loading.value = false
  }
}

async function handleCreateConnection() {
  if (!selectedProviderId.value || !connectionForm.name) {
    message.warning('请选择 Provider 并填写连接名称')
    return
  }
  savingConnection.value = true
  try {
    await createProviderConnection(selectedProviderId.value, {
      name: connectionForm.name,
      auth_type: connectionForm.auth_type,
      account_label: connectionForm.account_label || null,
      credential: connectionForm.credential || null,
      refresh_token: connectionForm.refresh_token || null,
      priority: connectionForm.priority,
      enabled: connectionForm.enabled,
      metadata: {}
    })
    connectionForm.name = ''
    connectionForm.account_label = ''
    connectionForm.credential = ''
    connectionForm.refresh_token = ''
    message.success('Provider Connection 已创建')
    await loadProviderData()
  } finally {
    savingConnection.value = false
  }
}

async function handleCreateNode() {
  if (!selectedProviderId.value || !nodeForm.name || !nodeForm.base_url) {
    message.warning('请选择 Provider 并填写节点名称与 Base URL')
    return
  }
  savingNode.value = true
  try {
    await createProviderNode(selectedProviderId.value, {
      name: nodeForm.name,
      base_url: nodeForm.base_url,
      connection_id: nodeForm.connection_id,
      region: nodeForm.region || null,
      weight: nodeForm.weight,
      enabled: nodeForm.enabled,
      capabilities: nodeForm.capabilities.split(',').map((item) => item.trim()).filter(Boolean),
      metadata: {}
    })
    nodeForm.name = ''
    nodeForm.base_url = ''
    nodeForm.region = ''
    message.success('Provider Node 已创建')
    await loadProviderData()
  } finally {
    savingNode.value = false
  }
}

async function toggleConnection(row: ProviderConnection) {
  if (!selectedProviderId.value) return
  await updateProviderConnection(selectedProviderId.value, row.id, { enabled: !row.enabled })
  await loadProviderData()
}

async function toggleNode(row: ProviderNode) {
  if (!selectedProviderId.value) return
  await updateProviderNode(selectedProviderId.value, row.id, { enabled: !row.enabled })
  await loadProviderData()
}

async function handleDeleteConnection(row: ProviderConnection) {
  if (!selectedProviderId.value) return
  try {
    await deleteProviderConnection(selectedProviderId.value, row.id)
    message.success('连接已删除')
    await loadProviderData()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '删除连接失败')
  }
}

async function handleDeleteNode(row: ProviderNode) {
  if (!selectedProviderId.value) return
  await deleteProviderNode(selectedProviderId.value, row.id)
  message.success('节点已删除')
  await loadProviderData()
}

onMounted(async () => {
  providers.value = await fetchProviders()
  selectedProviderId.value = providers.value[0]?.id ?? null
  await loadProviderData()
})
</script>
