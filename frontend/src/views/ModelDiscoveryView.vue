<template>
  <n-space vertical size="large">
    <n-h1>模型发现</n-h1>

    <n-card title="Provider 模型发现">
      <n-space vertical>
        <n-form label-placement="left" label-width="100">
          <n-form-item label="Provider">
            <n-select v-model:value="selectedProviderId" :options="providerOptions" placeholder="选择 Provider" @update:value="loadModels" />
          </n-form-item>
          <n-form-item label="添加到统一模型">
            <n-select v-model:value="targetUnifiedModelId" :options="unifiedModelOptions" placeholder="选择统一模型" />
          </n-form-item>
          <n-space>
            <n-button :disabled="!selectedProviderId" :loading="testing" @click="handleTest">测试连接</n-button>
            <n-button type="primary" :disabled="!selectedProviderId" :loading="discovering" @click="handleDiscover">拉取模型列表</n-button>
          </n-space>
        </n-form>
        <n-alert v-if="connectionMessage" :type="connectionOk ? 'success' : 'error'">{{ connectionMessage }}</n-alert>
      </n-space>
    </n-card>

    <n-card title="已发现模型">
      <n-data-table :columns="columns" :data="models" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NForm, NFormItem, NH1, NSelect, NSpace, NTag, useMessage } from 'naive-ui'
import {
  discoverProviderModels,
  fetchProviderModels,
  fetchProviders,
  testProvider,
  type Provider,
  type ProviderModel
} from '../api/providers'
import { createUnifiedModelCandidate, fetchUnifiedModels, type UnifiedModel } from '../api/unifiedModels'

const message = useMessage()
const providers = ref<Provider[]>([])
const unifiedModels = ref<UnifiedModel[]>([])
const models = ref<ProviderModel[]>([])
const selectedProviderId = ref<number | null>(null)
const targetUnifiedModelId = ref<number | null>(null)
const testing = ref(false)
const discovering = ref(false)
const addingCandidateId = ref<number | null>(null)
const connectionMessage = ref('')
const connectionOk = ref(false)
const providerOptions = computed(() => providers.value.map((provider) => ({ label: `${provider.name} (${provider.type})`, value: provider.id })))
const unifiedModelOptions = computed(() => unifiedModels.value.map((model) => ({ label: `${model.name} (#${model.id})`, value: model.id })))
const columns = [
  { title: 'ID', key: 'id' },
  { title: 'Provider ID', key: 'provider_id' },
  { title: '模型名', key: 'model_name' },
  { title: 'Owned By', key: 'owned_by' },
  {
    title: '启用',
    key: 'enabled',
    render(row: ProviderModel) {
      return h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  {
    title: '能力',
    key: 'capabilities',
    render(row: ProviderModel) {
      return row.capabilities.map((capability) => h(NTag, { size: 'small', style: 'margin-right: 4px' }, { default: () => capability }))
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: ProviderModel) {
      return h(NButton, {
        size: 'small',
        type: 'primary',
        disabled: !targetUnifiedModelId.value || !selectedProviderId.value,
        loading: addingCandidateId.value === row.id,
        onClick: () => handleAddCandidate(row)
      }, { default: () => '添加为候选' })
    }
  }
]

async function loadProviders() {
  const [providerResult, unifiedModelResult] = await Promise.all([fetchProviders(), fetchUnifiedModels()])
  providers.value = providerResult
  unifiedModels.value = unifiedModelResult
  if (!selectedProviderId.value && providers.value.length > 0) {
    selectedProviderId.value = providers.value[0].id
  }
  if (!targetUnifiedModelId.value && unifiedModels.value.length > 0) {
    targetUnifiedModelId.value = unifiedModels.value[0].id
  }
  await loadModels()
}

async function loadModels() {
  if (!selectedProviderId.value) {
    models.value = []
    return
  }
  models.value = await fetchProviderModels(selectedProviderId.value)
}

async function handleTest() {
  if (!selectedProviderId.value) return
  testing.value = true
  try {
    const result = await testProvider(selectedProviderId.value)
    connectionOk.value = result.ok
    connectionMessage.value = result.message
  } finally {
    testing.value = false
  }
}

async function handleDiscover() {
  if (!selectedProviderId.value) return
  discovering.value = true
  try {
    const result = await discoverProviderModels(selectedProviderId.value)
    message.success(`已发现 ${result.models.length} 个模型`)
    await loadModels()
  } finally {
    discovering.value = false
  }
}

async function handleAddCandidate(row: ProviderModel) {
  if (!targetUnifiedModelId.value || !selectedProviderId.value) {
    message.warning('请先选择目标统一模型和 Provider')
    return
  }
  addingCandidateId.value = row.id
  try {
    await createUnifiedModelCandidate(targetUnifiedModelId.value, {
      provider_id: selectedProviderId.value,
      upstream_model: row.model_name,
      manual_priority: 100,
      enabled: true,
      capabilities: row.capabilities.length > 0 ? row.capabilities : ['text']
    })
    message.success('候选模型已添加')
    unifiedModels.value = await fetchUnifiedModels()
  } finally {
    addingCandidateId.value = null
  }
}

onMounted(loadProviders)
</script>
