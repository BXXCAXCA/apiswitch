<template>
  <n-space vertical>
    <n-h1>上游平台</n-h1>
    <n-data-table :columns="columns" :data="providers" />
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NDataTable, NH1, NSpace } from 'naive-ui'
import { fetchProviders, type Provider } from '../api/providers'

const providers = ref<Provider[]>([])
const columns = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: 'Base URL', key: 'base_url' },
  { title: '启用', key: 'enabled' },
  { title: '超时', key: 'timeout_seconds' }
]
onMounted(async () => { providers.value = await fetchProviders() })
</script>
