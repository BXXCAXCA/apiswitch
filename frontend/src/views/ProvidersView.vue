<template>
  <n-space vertical size="large">
    <n-h1>上游平台</n-h1>

    <n-card title="新增 Provider">
      <n-form :model="form" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="openai-main" /></n-form-item-gi>
          <n-form-item-gi label="类型"><n-select v-model:value="form.type" :options="typeOptions" @update:value="handleTypeChange" /></n-form-item-gi>
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
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { createProvider, fetchProviders, type Provider, type ProviderCreate } from '../api/providers'

const message = useMessage()
const providers = ref<Provider[]>([])
const saving = ref(false)
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
  { title: '启用', key: 'enabled' },
  { title: '超时', key: 'timeout_seconds' }
]

function handleTypeChange(value: string) {
  if (value === 'mock') {
    form.base_url = 'mock://local'
  } else if (value === 'openai') {
    form.base_url = 'https://api.openai.com/v1'
  } else if (value === 'anthropic') {
    form.base_url = 'https://api.anthropic.com/v1'
  } else if (value === 'gemini') {
    form.base_url = 'https://generativelanguage.googleapis.com/v1beta'
  } else if (value === 'compatible') {
    form.base_url = 'http://127.0.0.1:3000/v1'
  }
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

onMounted(loadProviders)
</script>
