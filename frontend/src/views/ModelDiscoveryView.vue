<template>
  <n-space vertical size="large">
    <n-h1>模型发现</n-h1>

    <n-card title="Provider 模型发现">
      <n-space vertical>
        <n-form label-placement="left" label-width="100">
          <n-form-item label="Provider">
            <n-select v-model:value="selectedProviderId" :options="providerOptions" placeholder="选择 Provider" />
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

const message = useMessage()
const providers = ref<Provider[]>([])
const models = ref<ProviderModel[]>([])
const selectedProviderId = ref<number | null>(null)
const testing = ref(false)
const discovering = ref(false)
const connectionMessage = ref('')
const connectionOk = ref(false)
const providerOptions = computed(() => providers.value.map((provider) => ({ label: `${provider.name} (${provider.type})`, value: provider.id })))
const columns = [
  { title: 'ID', key: 'id' },
  { title: 'Provider ID', key: 'provider_id' },
  { title: '模型名', key: 'model_name' },
  { title: 'Owned By', key: 'owned_by' },
  { title: '启用', key: 'enabled' },
  {
    title: '能力',
    key: 'capabilities',
    render(row: ProviderModel) {
      return row.capabilities.map((capability) => h(NTag, { size: 'small', style: 'margin-right: 4px' }, { default: () => capability }))
    }
  }
]

async function loadProviders() {
  providers.value = await fetchProviders()
  if (!selectedProviderId.value && providers.value.length > 0) {
    selectedProviderId.value = providers.value[0].id
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

onMounted(loadProviders)
</script>
