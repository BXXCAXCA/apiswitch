<template>
  <n-space vertical size="large">
    <n-h1>统一模型</n-h1>

    <n-card title="新增统一模型">
      <n-form :model="modelForm" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="modelForm.name" placeholder="code-best" /></n-form-item-gi>
          <n-form-item-gi label="描述"><n-input v-model:value="modelForm.description" placeholder="适合代码任务的模型" /></n-form-item-gi>
          <n-form-item-gi label="能力"><n-select v-model:value="modelForm.capabilities" multiple :options="capabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="modelForm.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="savingModel" @click="handleCreateModel">创建统一模型</n-button>
      </n-form>
    </n-card>

    <n-card title="新增候选模型">
      <n-form :model="candidateForm" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="统一模型"><n-select v-model:value="selectedModelId" :options="modelOptions" /></n-form-item-gi>
          <n-form-item-gi label="Provider"><n-select v-model:value="candidateForm.provider_id" :options="providerOptions" /></n-form-item-gi>
          <n-form-item-gi label="上游模型"><n-input v-model:value="candidateForm.upstream_model" placeholder="mock-chat" /></n-form-item-gi>
          <n-form-item-gi label="优先级"><n-input-number v-model:value="candidateForm.manual_priority" :min="0" /></n-form-item-gi>
          <n-form-item-gi label="能力"><n-select v-model:value="candidateForm.capabilities" multiple :options="capabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="candidateForm.enabled" /></n-form-item-gi>
        </n-grid>
        <n-button type="primary" :loading="savingCandidate" @click="handleCreateCandidate">添加候选</n-button>
      </n-form>
    </n-card>

    <n-card title="统一模型列表">
      <n-data-table :columns="columns" :data="models" />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { fetchProviders, type Provider } from '../api/providers'
import {
  createUnifiedModel,
  createUnifiedModelCandidate,
  fetchUnifiedModels,
  type UnifiedModel,
  type UnifiedModelCandidateCreate,
  type UnifiedModelCreate
} from '../api/unifiedModels'

const message = useMessage()
const models = ref<UnifiedModel[]>([])
const providers = ref<Provider[]>([])
const selectedModelId = ref<number | null>(null)
const savingModel = ref(false)
const savingCandidate = ref(false)
const modelForm = reactive<UnifiedModelCreate>({
  name: '',
  description: '',
  enabled: true,
  capabilities: ['text']
})
const candidateForm = reactive<UnifiedModelCandidateCreate>({
  provider_id: 0,
  upstream_model: 'mock-chat',
  manual_priority: 100,
  enabled: true,
  capabilities: ['text']
})
const capabilityOptions = [
  { label: 'text', value: 'text' },
  { label: 'tools', value: 'tools' },
  { label: 'files', value: 'files' },
  { label: 'vision', value: 'vision' },
  { label: 'embeddings', value: 'embeddings' }
]
const modelOptions = computed(() => models.value.map((model) => ({ label: `${model.name} (#${model.id})`, value: model.id })))
const providerOptions = computed(() => providers.value.map((provider) => ({ label: `${provider.name} (${provider.type})`, value: provider.id })))
const columns = [
  { title: 'ID', key: 'id' },
  { title: '名称', key: 'name' },
  { title: '描述', key: 'description' },
  { title: '启用', key: 'enabled' },
  {
    title: '能力',
    key: 'capabilities',
    render(row: UnifiedModel) {
      return row.capabilities.map((capability) => h(NTag, { size: 'small', style: 'margin-right: 4px' }, { default: () => capability }))
    }
  },
  {
    title: '候选',
    key: 'candidates',
    render(row: UnifiedModel) {
      return row.candidates.map((candidate) => `${candidate.provider_name}:${candidate.upstream_model}`).join(', ')
    }
  }
]

async function loadAll() {
  const [modelResult, providerResult] = await Promise.all([fetchUnifiedModels(), fetchProviders()])
  models.value = modelResult
  providers.value = providerResult
  if (!selectedModelId.value && models.value.length > 0) {
    selectedModelId.value = models.value[0].id
  }
  if (!candidateForm.provider_id && providers.value.length > 0) {
    candidateForm.provider_id = providers.value[0].id
  }
}

async function handleCreateModel() {
  if (!modelForm.name) {
    message.warning('请填写统一模型名称')
    return
  }
  savingModel.value = true
  try {
    const created = await createUnifiedModel({ ...modelForm })
    selectedModelId.value = created.id
    modelForm.name = ''
    modelForm.description = ''
    message.success('统一模型已创建')
    await loadAll()
  } finally {
    savingModel.value = false
  }
}

async function handleCreateCandidate() {
  if (!selectedModelId.value || !candidateForm.provider_id || !candidateForm.upstream_model) {
    message.warning('请选择统一模型、Provider 并填写上游模型')
    return
  }
  savingCandidate.value = true
  try {
    await createUnifiedModelCandidate(selectedModelId.value, { ...candidateForm })
    message.success('候选模型已添加')
    await loadAll()
  } finally {
    savingCandidate.value = false
  }
}

onMounted(loadAll)
</script>
