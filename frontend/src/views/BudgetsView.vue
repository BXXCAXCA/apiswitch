<template>
  <n-space vertical size="large">
    <n-h1>预算控制</n-h1>

    <n-card title="创建预算">
      <n-form :model="form" label-placement="left" label-width="120">
        <n-grid :cols="3" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="form.name" placeholder="global-monthly" /></n-form-item-gi>
          <n-form-item-gi label="范围"><n-select v-model:value="form.scope" :options="scopeOptions" /></n-form-item-gi>
          <n-form-item-gi label="范围 ID"><n-input v-model:value="form.scope_id" placeholder="可选，例如 provider id" /></n-form-item-gi>
          <n-form-item-gi label="月度上限"><n-input-number v-model:value="form.monthly_limit" :min="0" clearable /></n-form-item-gi>
          <n-form-item-gi label="已用额度"><n-input-number v-model:value="form.spent_amount" :min="0" /></n-form-item-gi>
          <n-form-item-gi label="币种"><n-input v-model:value="form.currency" /></n-form-item-gi>
          <n-form-item-gi label="告警阈值 %"><n-input-number v-model:value="form.alert_threshold_percent" :min="1" :max="100" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="saving" @click="handleCreate">创建预算</n-button>
      </n-form>
    </n-card>

    <n-card title="预算列表">
      <n-data-table :columns="columns" :data="budgets" :loading="loading" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NPopconfirm, NProgress, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { createBudget, deleteBudget, fetchBudgets, updateBudget, type Budget } from '../api/budgets'

const message = useMessage()
const budgets = ref<Budget[]>([])
const loading = ref(false)
const saving = ref(false)
const updatingId = ref<number | null>(null)
const form = reactive({
  name: '',
  scope: 'global',
  scope_id: '',
  monthly_limit: 100,
  currency: 'USD',
  enabled: true,
  spent_amount: 0,
  alert_threshold_percent: 80
})
const scopeOptions = [
  { label: '全局', value: 'global' },
  { label: 'Provider', value: 'provider' },
  { label: 'API Token', value: 'api_token' },
  { label: '统一模型', value: 'unified_model' }
]
const columns = [
  { title: '名称', key: 'name' },
  { title: '范围', key: 'scope' },
  { title: '范围 ID', key: 'scope_id', render: (row: Budget) => row.scope_id || '-' },
  {
    title: '状态',
    key: 'enabled',
    render(row: Budget) {
      return h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
  { title: '月度上限', key: 'monthly_limit', render: (row: Budget) => row.monthly_limit === null ? '无限制' : `${row.monthly_limit} ${row.currency}` },
  { title: '已用', key: 'spent_amount', render: (row: Budget) => `${row.spent_amount} ${row.currency}` },
  {
    title: '使用率',
    key: 'usage_percent',
    render(row: Budget) {
      if (row.usage_percent === null) return '-'
      const status = row.alert_triggered ? 'error' : 'success'
      return h(NProgress, { type: 'line', percentage: Math.min(row.usage_percent, 100), status, indicatorPlacement: 'inside' })
    }
  },
  { title: '告警阈值', key: 'alert_threshold_percent', render: (row: Budget) => `${row.alert_threshold_percent}%` },
  {
    title: '操作',
    key: 'actions',
    render(row: Budget) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', loading: updatingId.value === row.id, onClick: () => toggleBudget(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NButton, { size: 'small', onClick: () => markSpent(row) }, { default: () => '同步已用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            default: () => '删除后不可恢复，是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
    }
  }
]

async function loadBudgets() {
  loading.value = true
  try {
    budgets.value = await fetchBudgets()
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.name) {
    message.warning('请填写预算名称')
    return
  }
  saving.value = true
  try {
    await createBudget({
      name: form.name,
      scope: form.scope,
      scope_id: form.scope_id || null,
      monthly_limit: form.monthly_limit,
      currency: form.currency,
      enabled: form.enabled,
      spent_amount: form.spent_amount,
      alert_threshold_percent: form.alert_threshold_percent
    })
    form.name = ''
    form.scope = 'global'
    form.scope_id = ''
    form.monthly_limit = 100
    form.currency = 'USD'
    form.enabled = true
    form.spent_amount = 0
    form.alert_threshold_percent = 80
    message.success('预算已创建')
    await loadBudgets()
  } finally {
    saving.value = false
  }
}

async function toggleBudget(row: Budget) {
  updatingId.value = row.id
  try {
    await updateBudget(row.id, { enabled: !row.enabled })
    message.success(row.enabled ? '预算已禁用' : '预算已启用')
    await loadBudgets()
  } finally {
    updatingId.value = null
  }
}

async function markSpent(row: Budget) {
  const spent = window.prompt('输入新的已用额度', String(row.spent_amount))
  if (spent === null) return
  const nextValue = Number(spent)
  if (Number.isNaN(nextValue) || nextValue < 0) {
    message.warning('请输入有效的非负数字')
    return
  }
  await updateBudget(row.id, { spent_amount: nextValue })
  message.success('已用额度已更新')
  await loadBudgets()
}

async function handleDelete(row: Budget) {
  await deleteBudget(row.id)
  message.success('预算已删除')
  await loadBudgets()
}

onMounted(loadBudgets)
</script>
