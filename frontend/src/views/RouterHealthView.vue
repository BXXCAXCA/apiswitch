<template>
  <n-space vertical>
    <n-h1>路由 / 熔断状态</n-h1>
    <n-data-table :columns="columns" :data="items" />

    <n-modal v-model:show="showScoreDetails">
      <n-card style="width: 720px" title="自动评分构成" closable @close="showScoreDetails = false">
        <n-code :code="scoreDetailsText" language="json" word-wrap />
      </n-card>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NCode, NDataTable, NH1, NModal, NSpace, NTag } from 'naive-ui'
import { fetchRouterHealth, type RouterHealthItem } from '../api/routerHealth'

const items = ref<RouterHealthItem[]>([])
const selectedItem = ref<RouterHealthItem | null>(null)
const showScoreDetails = ref(false)
const scoreDetailsText = computed(() => JSON.stringify(selectedItem.value?.score_breakdown ?? {}, null, 2))

function openScoreDetails(row: RouterHealthItem) {
  selectedItem.value = row
  showScoreDetails.value = true
}

const columns = [
  { title: '统一模型', key: 'unified_model' },
  { title: 'Provider', key: 'provider' },
  { title: '上游模型', key: 'upstream_model' },
  { title: '分数', key: 'score' },
  {
    title: '评分构成',
    key: 'score_breakdown',
    render(row: RouterHealthItem) {
      return h(
        NButton,
        { size: 'small', disabled: !row.score_breakdown, onClick: () => openScoreDetails(row) },
        { default: () => '查看' }
      )
    }
  },
  {
    title: '可用',
    key: 'available',
    render(row: RouterHealthItem) {
      return h(NTag, { type: row.available ? 'success' : 'error', size: 'small' }, { default: () => row.available ? '可用' : '不可用' })
    }
  },
  {
    title: '熔断状态',
    key: 'circuit_state',
    render(row: RouterHealthItem) {
      const tagType = row.circuit_state === 'closed' ? 'success' : row.circuit_state === 'half_open' ? 'warning' : 'error'
      return h(NTag, { type: tagType, size: 'small' }, { default: () => row.circuit_state })
    }
  },
  { title: '成功', key: 'success_count' },
  { title: '失败', key: 'failure_count' },
  { title: '连续失败', key: 'consecutive_failures' },
  { title: '失败阈值', key: 'failure_threshold' },
  { title: '冷却秒数', key: 'cooldown_seconds' },
  { title: '平均延迟', key: 'avg_latency_ms' },
  { title: '最近失败原因', key: 'last_failure_reason' }
]

onMounted(async () => {
  const response = await fetchRouterHealth()
  items.value = response.items
})
</script>
