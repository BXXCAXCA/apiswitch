<template>
  <n-space vertical size="large">
    <n-h1>上游平台</n-h1>

    <n-card title="新增 Provider">
      <n-form :model="form" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="openai-main" /></n-form-item-gi>
          <n-form-item-gi label="类型"><n-select v-model:value="form.type" :options="typeOptions" /></n-form-item-gi>
          <n-form-item-gi label="Base URL"><n-input v-model:value="form.base_url" placeholder="https://api.openai.com/v1" /></n-form-item-gi>
          <n-form-item-gi label="超时秒数"><n-input-number v-model:value="form.timeout_seconds" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建 Provider</n-button>
      </n-form>
    </n-card>

    <n-card title="Provider 列表">
      <n-data-table :columns="columns" :data="providers" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGi, NGrid, NH1, NInput, NInputNumber, NSelect, NSpace, NSwitch, useMessage } from 'naive-ui'
import { createProvider, fetchProviders, type Provider, type ProviderCreate } from '../api/providers'

const message = useMessage()
const providers = ref<Provider[]>([])
const saving = ref(false)
const form = reactive<ProviderCreate>({
  name: '',
  type: 'mock',
  base_url: 'mock://local',
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
  { title: '启用', key: 'enabled' },
  { title: '超时', key: 'timeout_seconds' }
]

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
    await createProvider({ ...form })
    message.success('Provider 已创建')
    form.name = ''
    await loadProviders()
  } finally {
    saving.value = false
  }
}

onMounted(loadProviders)
</script>
