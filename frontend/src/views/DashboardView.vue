<template>
  <n-space vertical size="large">
    <n-h1>仪表盘</n-h1>
    <n-grid :cols="4" :x-gap="16" :y-gap="16">
      <n-gi v-for="item in cards" :key="item.label">
        <n-card :title="item.label"><n-statistic :value="item.value" /></n-card>
      </n-gi>
    </n-grid>
  </n-space>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NCard, NGi, NGrid, NH1, NSpace, NStatistic } from 'naive-ui'
import { fetchDashboardSummary, type DashboardSummary } from '../api/dashboard'

const summary = ref<DashboardSummary | null>(null)
onMounted(async () => { summary.value = await fetchDashboardSummary() })
const cards = computed(() => [
  { label: '请求总量', value: summary.value?.requests_total ?? 0 },
  { label: '成功率', value: summary.value ? `${(summary.value.success_rate * 100).toFixed(1)}%` : '0%' },
  { label: '平均延迟', value: `${summary.value?.average_latency_ms ?? 0} ms` },
  { label: '熔断数量', value: summary.value?.open_circuit_breakers ?? 0 }
])
</script>
