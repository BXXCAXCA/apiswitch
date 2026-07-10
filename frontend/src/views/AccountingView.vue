<template>
  <n-space vertical size="large">
    <n-h1>价格、额度与用量</n-h1>

    <n-grid :cols="4" :x-gap="16">
      <n-gi><n-statistic label="请求数" :value="summary.request_count" /></n-gi>
      <n-gi><n-statistic label="输入 Token" :value="summary.input_tokens" /></n-gi>
      <n-gi><n-statistic label="输出 Token" :value="summary.output_tokens" /></n-gi>
      <n-gi><n-statistic label="估算成本 USD" :value="summary.estimated_cost" :precision="6" /></n-gi>
    </n-grid>

    <n-card title="新增模型价格">
      <n-form :model="pricingForm" label-placement="left" label-width="140">
        <n-grid :cols="3" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="Provider"><n-select v-model:value="pricingForm.provider_id" clearable :options="providerOptions" /></n-form-item-gi>
          <n-form-item-gi label="上游模型"><n-input v-model:value="pricingForm.model_name" placeholder="mock-chat" /></n-form-item-gi>
          <n-form-item-gi label="币种"><n-input v-model:value="pricingForm.currency" /></n-form-item-gi>
          <n-form-item-gi label="输入/百万 Token"><n-input-number v-model:value="pricingForm.input_cost_per_million" :min="0" clearable /></n-form-item-gi>
          <n-form-item-gi label="输出/百万 Token"><n-input-number v-model:value="pricingForm.output_cost_per_million" :min="0" clearable /></n-form-item-gi>
          <n-form-item-gi label="缓存输入/百万"><n-input-number v-model:value="pricingForm.cached_input_cost_per_million" :min="0" clearable /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="savingPricing" @click="handleCreatePricing">保存价格</n-button>
      </n-form>
    </n-card>

    <n-card title="模型价格">
      <n-data-table :columns="pricingColumns" :data="pricing" :loading="loading" />
    </n-card>

    <n-card title="手动记录额度快照">
      <n-alert type="info" style="margin-bottom: 12px">
        当前支持手动录入；后续 Provider Adapter 会自动轮询官方额度接口。
      </n-alert>
      <n-form :model="quotaForm" label-placement="left" label-width="150">
        <n-grid :cols="4" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="Connection ID"><n-input-number v-model:value="quotaForm.provider_connection_id" :min="1" /></n-form-item-gi>
          <n-form-item-gi label="剩余请求"><n-input-number v-model:value="quotaForm.remaining_requests" :min="0" clearable /></n-form-item-gi>
          <n-form-item-gi label="剩余 Token"><n-input-number v-model:value="quotaForm.remaining_tokens" :min="0" clearable /></n-form-item-gi>
          <n-form-item-gi label="剩余 Credit"><n-input-number v-model:value="quotaForm.remaining_credit" :min="0" clearable /></n-form-item-gi>
        </n-grid>
        <n-button :loading="savingQuota" @click="handleCreateQuota">记录快照</n-button>
      </n-form>
    </n-card>

    <n-card title="最近额度快照">
      <n-data-table :columns="quotaColumns" :data="quotaSnapshots" :loading="loading" />
    </n-card>

    <n-card title="最近用量">
      <n-space style="margin-bottom: 12px">
        <n-button :loading="loading" @click="loadData">刷新</n-button>
        <n-tag type="info">有价格配置的请求：{{ summary.priced_request_count }}</n-tag>
      </n-space>
      <n-data-table :columns="usageColumns" :data="usage" :loading="loading" />
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
  NFormItemGi,
  NGi,
  NGrid,
  NH1,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NStatistic,
  NTag,
  useMessage
} from 'naive-ui'
import { fetchProviders, type Provider } from '../api/providers'
import {
  createModelPricing,
  createQuotaSnapshot,
  deleteModelPricing,
  fetchModelPricing,
  fetchQuotaSnapshots,
  fetchUsageHistory,
  fetchUsageSummary,
  type ModelPricing,
  type QuotaSnapshot,
  type UsageHistory,
  type UsageSummary
} from '../api/accounting'

const message = useMessage()
const providers = ref<Provider[]>([])
const pricing = ref<ModelPricing[]>([])
const usage = ref<UsageHistory[]>([])
const quotaSnapshots = ref<QuotaSnapshot[]>([])
const loading = ref(false)
const savingPricing = ref(false)
const savingQuota = ref(false)
const summary = reactive<UsageSummary>({
  request_count: 0,
  input_tokens: 0,
  output_tokens: 0,
  estimated_cost: 0,
  priced_request_count: 0
})
const pricingForm = reactive({
  provider_id: null as number | null,
  model_name: '',
  input_cost_per_million: null as number | null,
  output_cost_per_million: null as number | null,
  cached_input_cost_per_million: null as number | null,
  currency: 'USD'
})
const quotaForm = reactive({
  provider_connection_id: null as number | null,
  remaining_requests: null as number | null,
  remaining_tokens: null as number | null,
  remaining_credit: null as number | null
})
const providerOptions = computed(() => providers.value.map((item) => ({ label: item.name, value: item.id })))
const providerNames = computed(() => Object.fromEntries(providers.value.map((item) => [item.id, item.name])))

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}

const pricingColumns = [
  { title: 'Provider', key: 'provider_id', render: (row: ModelPricing) => row.provider_id ? providerNames.value[row.provider_id] ?? row.provider_id : '全局默认' },
  { title: '模型', key: 'model_name' },
  { title: '输入/百万', key: 'input_cost_per_million' },
  { title: '输出/百万', key: 'output_cost_per_million' },
  { title: '缓存输入/百万', key: 'cached_input_cost_per_million' },
  { title: '币种', key: 'currency' },
  {
    title: '操作',
    key: 'actions',
    render(row: ModelPricing) {
      return h(NPopconfirm, { onPositiveClick: () => handleDeletePricing(row) }, {
        default: () => '删除此价格记录？',
        trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
      })
    }
  }
]
const quotaColumns = [
  { title: '时间', key: 'captured_at', render: (row: QuotaSnapshot) => formatTime(row.captured_at) },
  { title: 'Connection ID', key: 'provider_connection_id' },
  { title: '剩余请求', key: 'remaining_requests' },
  { title: '剩余 Token', key: 'remaining_tokens' },
  { title: '剩余 Credit', key: 'remaining_credit' },
  { title: '重置时间', key: 'reset_at', render: (row: QuotaSnapshot) => formatTime(row.reset_at) }
]
const usageColumns = [
  { title: '时间', key: 'created_at', render: (row: UsageHistory) => formatTime(row.created_at) },
  { title: '请求 ID', key: 'request_id' },
  { title: 'API Token ID', key: 'api_token_id', render: (row: UsageHistory) => row.api_token_id ?? '-' },
  { title: '统一模型', key: 'unified_model' },
  { title: '上游模型', key: 'upstream_model' },
  { title: '输入 Token', key: 'input_tokens' },
  { title: '输出 Token', key: 'output_tokens' },
  {
    title: '估算成本',
    key: 'estimated_cost',
    render(row: UsageHistory) {
      return row.estimated_cost === null
        ? h(NTag, { size: 'small', type: 'warning' }, { default: () => '未定价' })
        : row.estimated_cost.toFixed(8)
    }
  }
]

async function loadData() {
  loading.value = true
  try {
    const [providerItems, pricingItems, usageItems, quotaItems, summaryItem] = await Promise.all([
      fetchProviders(),
      fetchModelPricing(),
      fetchUsageHistory(100),
      fetchQuotaSnapshots(100),
      fetchUsageSummary()
    ])
    providers.value = providerItems
    pricing.value = pricingItems
    usage.value = usageItems
    quotaSnapshots.value = quotaItems
    Object.assign(summary, summaryItem)
  } finally {
    loading.value = false
  }
}

async function handleCreatePricing() {
  if (!pricingForm.model_name) {
    message.warning('请填写上游模型名')
    return
  }
  savingPricing.value = true
  try {
    await createModelPricing({ ...pricingForm })
    pricingForm.model_name = ''
    pricingForm.input_cost_per_million = null
    pricingForm.output_cost_per_million = null
    pricingForm.cached_input_cost_per_million = null
    message.success('模型价格已保存')
    await loadData()
  } finally {
    savingPricing.value = false
  }
}

async function handleDeletePricing(row: ModelPricing) {
  await deleteModelPricing(row.id)
  message.success('模型价格已删除')
  await loadData()
}

async function handleCreateQuota() {
  if (!quotaForm.provider_connection_id) {
    message.warning('请填写 Provider Connection ID')
    return
  }
  savingQuota.value = true
  try {
    await createQuotaSnapshot({
      provider_connection_id: quotaForm.provider_connection_id,
      remaining_requests: quotaForm.remaining_requests,
      remaining_tokens: quotaForm.remaining_tokens,
      remaining_credit: quotaForm.remaining_credit,
      raw: { source: 'manual' }
    })
    message.success('额度快照已记录')
    await loadData()
  } finally {
    savingQuota.value = false
  }
}

onMounted(loadData)
</script>
