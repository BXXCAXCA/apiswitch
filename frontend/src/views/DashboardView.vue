<template>
  <n-space vertical size="large">
    <n-h1>仪表盘</n-h1>
    <n-grid responsive="screen" :cols="'1 s:2 l:4'" :x-gap="16" :y-gap="16">
      <n-gi v-for="item in cards" :key="item.label">
        <n-card :title="item.label"><n-statistic :value="item.value" /></n-card>
      </n-gi>
    </n-grid>
    <n-card title="最近错误"><n-empty v-if="!summary?.recent_errors?.length" description="最近没有错误"/><n-list v-else><n-list-item v-for="(error,index) in summary?.recent_errors" :key="index">{{ error }}</n-list-item></n-list></n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NCard, NEmpty, NGi, NGrid, NH1, NList, NListItem, NSpace, NStatistic } from 'naive-ui'
import { fetchDashboardSummary, type DashboardSummary } from '../api/dashboard'

const summary = ref<DashboardSummary | null>(null)
onMounted(async () => { summary.value = await fetchDashboardSummary() })
const cards = computed(() => [
  { label: '供应商实例', value: summary.value?.provider_instances ?? 0 },
  { label: '可用上游模型', value: summary.value?.available_upstream_models ?? 0 },
  { label: '统一模型', value: summary.value?.unified_models ?? 0 },
  { label: '辅助模型', value: summary.value?.auxiliary_models ?? 0 },
  { label: '近 24 小时调用', value: summary.value?.requests_24h ?? 0 },
  { label: '成功率', value: summary.value ? `${(summary.value.success_rate * 100).toFixed(1)}%` : '0%' },
  { label: '近 24 小时成本', value: `$${Number(summary.value?.cost_24h || 0).toFixed(6)}` },
  { label: '预算告警', value: summary.value?.budget_alerts ?? 0 },
  { label: '平均延迟', value: `${summary.value?.average_latency_ms ?? 0} ms` },
  { label: '首 Token 延迟', value: `${summary.value?.first_token_latency_ms ?? 0} ms` },
  { label: '熔断数量', value: summary.value?.open_circuit_breakers ?? 0 },
  { label: '请求总量', value: summary.value?.requests_total ?? 0 }
])
</script>
