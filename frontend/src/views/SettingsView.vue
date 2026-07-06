<template>
  <n-space vertical size="large">
    <n-h1>系统设置</n-h1>

    <n-card title="运行配置">
      <n-alert type="info" style="margin-bottom: 16px">
        部分运行配置例如监听地址和端口需要重启服务后才会完全生效。
      </n-alert>
      <n-form :model="form" label-placement="left" label-width="150">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="监听地址"><n-input v-model:value="form.listen_host" /></n-form-item-gi>
          <n-form-item-gi label="端口"><n-input-number v-model:value="form.port" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="默认超时秒数"><n-input-number v-model:value="form.default_timeout_seconds" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="日志保留天数"><n-input-number v-model:value="form.request_log_retention_days" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="Stream 失败模式"><n-select v-model:value="form.stream_failure_mode" :options="streamFailureModeOptions" /></n-form-item-gi>
          <n-form-item-gi label="默认 Provider 类型"><n-select v-model:value="form.default_provider_type" :options="providerTypeOptions" /></n-form-item-gi>
          <n-form-item-gi label="默认统一模型"><n-input v-model:value="form.default_unified_model" /></n-form-item-gi>
          <n-form-item-gi label="启用认证"><n-switch v-model:value="form.auth_enabled" /></n-form-item-gi>
          <n-form-item-gi label="保存调试请求体"><n-switch v-model:value="form.record_full_request" /></n-form-item-gi>
          <n-form-item-gi label="保存调试响应体"><n-switch v-model:value="form.record_full_response" /></n-form-item-gi>
        </n-grid>
        <n-space>
          <n-button type="primary" :loading="saving" @click="handleSave">保存设置</n-button>
          <n-button :loading="loading" @click="loadSettings">重新加载</n-button>
        </n-space>
      </n-form>
    </n-card>

    <n-card title="原始配置">
      <n-code :code="rawText" language="json" word-wrap />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NCode, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NSelect, NSpace, NSwitch, useMessage } from 'naive-ui'
import { fetchSettings, updateSettings, type SystemSettings } from '../api/settings'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const raw = ref<Record<string, unknown>>({})
const form = reactive<SystemSettings>({
  listen_host: '127.0.0.1',
  port: 8080,
  auth_enabled: true,
  stream_failure_mode: 'strict',
  default_timeout_seconds: 120,
  request_log_retention_days: 30,
  record_full_request: false,
  record_full_response: false,
  default_provider_type: 'mock',
  default_unified_model: 'code-best'
})
const streamFailureModeOptions = [
  { label: 'strict', value: 'strict' },
  { label: 'best_effort', value: 'best_effort' }
]
const providerTypeOptions = [
  { label: 'Mock', value: 'mock' },
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'OpenAI Compatible', value: 'compatible' }
]
const rawText = computed(() => JSON.stringify(raw.value, null, 2))

function assignSettings(settings: SystemSettings) {
  Object.assign(form, settings)
}

async function loadSettings() {
  loading.value = true
  try {
    const response = await fetchSettings()
    assignSettings(response.settings)
    raw.value = response.raw
  } catch (error) {
    message.error(`加载设置失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const response = await updateSettings({ ...form })
    assignSettings(response.settings)
    raw.value = response.raw
    message.success('设置已保存')
  } catch (error) {
    message.error(`保存设置失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>
