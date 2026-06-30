<template>
  <n-space vertical>
    <n-h1>统一模型</n-h1>
    <n-data-table :columns="columns" :data="models" />
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NDataTable, NH1, NSpace } from 'naive-ui'
import { fetchUnifiedModels, type UnifiedModel } from '../api/unifiedModels'

const models = ref<UnifiedModel[]>([])
const columns = [
  { title: '名称', key: 'name' },
  { title: '描述', key: 'description' },
  { title: '启用', key: 'enabled' },
  { title: '能力', key: 'capabilities' }
]
onMounted(async () => { models.value = await fetchUnifiedModels() })
</script>
