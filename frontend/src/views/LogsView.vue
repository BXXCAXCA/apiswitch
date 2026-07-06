<template>
  <n-space vertical size="large">
    <n-space justify="space-between" align="center">
      <n-h1>调用日志</n-h1>
      <n-space align="center">
        <n-select v-model:value="limit" :options="limitOptions" style="width: 120px" @update:value="loadLogs" />
        <n-button :loading="loading" @click="loadLogs">刷新</n-button>
      </n-space>
    </n-space>

    <n-card title="最近请求">
      <n-data-table :columns="columns" :data="logs" :loading="loading" />
    </n-card>

    <n-modal v-model:show="detailVisible" preset="card" title="日志详情" style="max-width: 900px">
      <n-descriptions v-if="selectedLog" bordered :column="2" size="small">
        <n-descriptions-item label="Request ID">{{ selectedLog.request_id }}</n-descriptions-item>
        <n-descriptions-item label="协议">{{ selectedLog.inbound_protocol }}</n-descriptions-item>
        <n-descriptions-item label="统一模型">{{ selectedLog.unified_model }}</n-descriptions-item>
        <n-descriptions-item label="Provider">{{ selectedLog.final_provider || '-' }}</n-descriptions-item>
        <n-descriptions-item label="上游模型">{{ selectedLog.final_upstream_model || '-' }}</n-descriptions-item>
        <n-descriptions-item label="状态">{{ selectedLog.success ? '成功' : '失败' }}</n-descriptions-item>
        <n-descriptions-item label="开始时间">{{ selectedLog.started_at }}</n-descriptions-item>
        <n-descriptions-item label="结束时间">{{ selectedLog.finished_at || '-' }}</n-descriptions-item>
        <n-descriptions-item label="延迟">{{ formatLatency(selectedLog.latency_ms) }}</n-descriptions-item>
        <n-descriptions-item label="首 Token 延迟">{{ formatLatency(selectedLog.first_token_latency_ms) }}</n-descriptions-item>
        <n-descriptions-item label="输入 Tokens">{{ selectedLog.input_tokens ?? '-' }}</n-descriptions-item>
        <n-descriptions-item label="输出 Tokens">{{ selectedLog.output_tokens ?? '-' }}</n-descriptions-item>
        <n-descriptions-item label="错误类型">{{ selectedLog.error_type || '-' }}</n-descriptions-item>
        <n-descriptions-item label="错误信息">{{ selectedLog.error_message || '-' }}</n-descriptions-item>
      </n-descriptions>
      <n-h3>Retry Chain</n-h3>
      <n-code :code="retryChainText" language="json" word-wrap />
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NCard, NCode, NDataTable, NDescriptions, NDescriptionsItem, NH1, NH3, NModal, NSelect, NSpace, NTag, useMessage } from 'naive-ui'
import { fetchRequestLogs, type RequestLogItem } from '../api/logs'

const message = useMessage()
const logs = ref<RequestLogItem[]>([])
const loading = ref(false)
const limit = ref(50)
const detailVisible = ref(false)
const selectedLog = ref<RequestLogItem | null>(null)
const limitOptions = [
  { label: '最近 20 条', value: 20 },
  { label: '最近 50 条', value: 50 },
  { label: '最近 100 条', value: 100 },
  { label: '最近 200 条', value: 200 }
]
const retryChainText = computed(() => JSON.stringify(selectedLog.value?.retry_chain ?? {}, null, 2))

const columns = [
  { title: '时间', key: 'started_at', render: (row: RequestLogItem) => formatTime(row.started_at) },
  {
    title: '状态',
    key: 'success',
    render(row: RequestLogItem) {
      return h(NTag, { type: row.success ? 'success' : 'error', size: 'small' }, { default: () => row.success ? '成功' : '失败' })
    }
  },
  { title: '协议', key: 'inbound_protocol' },
  { title: '统一模型', key: 'unified_model' },
  { title: 'Provider', key: 'final_provider' },
  { title: '上游模型', key: 'final_upstream_model' },
  { title: '延迟', key: 'latency_ms', render: (row: RequestLogItem) => formatLatency(row.latency_ms) },
  { title: 'Tokens', key: 'tokens', render: (row: RequestLogItem) => `${row.input_tokens ?? '-'} / ${row.output_tokens ?? '-'}` },
  {
    title: '错误',
    key: 'error_type',
    render(row: RequestLogItem) {
      if (!row.error_type) return '-'
      return h(NTag, { type: 'error', size: 'small' }, { default: () => row.error_type })
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: RequestLogItem) {
      return h(NButton, { size: 'small', onClick: () => openDetail(row) }, { default: () => '详情' })
    }
  }
]

function formatTime(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatLatency(value: number | null) {
  if (value === null || value === undefined) return '-'
  return `${Math.round(value)} ms`
}

function openDetail(row: RequestLogItem) {
  selectedLog.value = row
  detailVisible.value = true
}

async function loadLogs() {
  loading.value = true
  try {
    const response = await fetchRequestLogs(limit.value)
    logs.value = response.items
  } catch (error) {
    message.error(`加载日志失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadLogs)
</script>
