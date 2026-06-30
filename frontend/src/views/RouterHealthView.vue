<template>
  <n-space vertical>
    <n-h1>路由 / 熔断状态</n-h1>
    <n-data-table :columns="columns" :data="items" />
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NDataTable, NH1, NSpace } from 'naive-ui'
import { fetchRouterHealth, type RouterHealthItem } from '../api/routerHealth'

const items = ref<RouterHealthItem[]>([])
const columns = [
  { title: '统一模型', key: 'unified_model' },
  { title: 'Provider', key: 'provider' },
  { title: '上游模型', key: 'upstream_model' },
  { title: '分数', key: 'score' },
  { title: '成功', key: 'success_count' },
  { title: '失败', key: 'failure_count' },
  { title: '连续失败', key: 'consecutive_failures' },
  { title: '平均延迟', key: 'avg_latency_ms' },
  { title: '熔断状态', key: 'circuit_state' }
]

onMounted(async () => {
  const response = await fetchRouterHealth()
  items.value = response.items
})
</script>
