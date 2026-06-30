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

    <n-modal v-model:show="editingModel" preset="card" title="编辑统一模型" style="max-width: 720px">
      <n-form :model="editModelForm" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="名称"><n-input v-model:value="editModelForm.name" /></n-form-item-gi>
          <n-form-item-gi label="描述"><n-input v-model:value="editModelForm.description" /></n-form-item-gi>
          <n-form-item-gi label="能力"><n-select v-model:value="editModelForm.capabilities" multiple :options="capabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="editModelForm.enabled" /></n-form-item-gi>
        </n-grid>
        <n-space>
          <n-button type="primary" :loading="savingModel" @click="handleUpdateModel">保存</n-button>
          <n-button @click="editingModel = false">取消</n-button>
        </n-space>
      </n-form>
    </n-modal>

    <n-modal v-model:show="editingCandidate" preset="card" title="编辑候选模型" style="max-width: 720px">
      <n-form :model="editCandidateForm" label-placement="left" label-width="100">
        <n-grid :cols="2" :x-gap="16" :y-gap="12">
          <n-form-item-gi label="Provider"><n-select v-model:value="editCandidateForm.provider_id" :options="providerOptions" /></n-form-item-gi>
          <n-form-item-gi label="上游模型"><n-input v-model:value="editCandidateForm.upstream_model" /></n-form-item-gi>
          <n-form-item-gi label="优先级"><n-input-number v-model:value="editCandidateForm.manual_priority" :min="0" /></n-form-item-gi>
          <n-form-item-gi label="能力"><n-select v-model:value="editCandidateForm.capabilities" multiple :options="capabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="editCandidateForm.enabled" /></n-form-item-gi>
        </n-grid>
        <n-space>
          <n-button type="primary" :loading="savingCandidate" @click="handleUpdateCandidate">保存</n-button>
          <n-button @click="editingCandidate = false">取消</n-button>
        </n-space>
      </n-form>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NModal, NPopconfirm, NSelect, NSpace, NSwitch, NTag, useMessage } from 'naive-ui'
import { fetchProviders, type Provider } from '../api/providers'
import {
  createUnifiedModel,
  createUnifiedModelCandidate,
  deleteUnifiedModel,
  deleteUnifiedModelCandidate,
  fetchUnifiedModels,
  updateUnifiedModel,
  updateUnifiedModelCandidate,
  type UnifiedModel,
  type UnifiedModelCandidate,
  type UnifiedModelCandidateCreate,
  type UnifiedModelCreate
} from '../api/unifiedModels'

const message = useMessage()
const models = ref<UnifiedModel[]>([])
const providers = ref<Provider[]>([])
const selectedModelId = ref<number | null>(null)
const savingModel = ref(false)
const savingCandidate = ref(false)
const editingModel = ref(false)
const editingModelId = ref<number | null>(null)
const editingCandidate = ref(false)
const editingCandidateModelId = ref<number | null>(null)
const editingCandidateId = ref<number | null>(null)
const modelForm = reactive<UnifiedModelCreate>({
  name: '',
  description: '',
  enabled: true,
  capabilities: ['text']
})
const editModelForm = reactive<UnifiedModelCreate>({
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
const editCandidateForm = reactive<UnifiedModelCandidateCreate>({
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
  {
    title: '启用',
    key: 'enabled',
    render(row: UnifiedModel) {
      return h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '启用' : '禁用' })
    }
  },
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
      if (row.candidates.length === 0) return '无'
      return h(NSpace, { vertical: true, size: 4 }, {
        default: () => row.candidates.map((candidate) => h(NSpace, { size: 'small', align: 'center' }, {
          default: () => [
            h(NTag, { size: 'small', type: candidate.enabled ? 'success' : 'default' }, { default: () => `${candidate.provider_name}:${candidate.upstream_model}` }),
            h(NTag, { size: 'small' }, { default: () => `优先级 ${candidate.manual_priority}` }),
            h(NButton, { size: 'tiny', onClick: () => openCandidateEdit(row, candidate) }, { default: () => '编辑' }),
            h(NButton, { size: 'tiny', onClick: () => toggleCandidate(row, candidate) }, { default: () => candidate.enabled ? '禁用' : '启用' }),
            h(NPopconfirm, { onPositiveClick: () => handleDeleteCandidate(row, candidate) }, {
              default: () => '删除该候选模型？',
              trigger: () => h(NButton, { size: 'tiny', type: 'error' }, { default: () => '删除' })
            })
          ]
        }))
      })
    }
  },
  {
    title: '操作',
    key: 'actions',
    render(row: UnifiedModel) {
      return h(NSpace, { size: 'small' }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => openModelEdit(row) }, { default: () => '编辑' }),
          h(NButton, { size: 'small', onClick: () => toggleModel(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
          h(NPopconfirm, { onPositiveClick: () => handleDeleteModel(row) }, {
            default: () => '删除统一模型会同时删除其候选配置，是否继续？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' })
          })
        ]
      })
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

function openModelEdit(row: UnifiedModel) {
  editingModelId.value = row.id
  editModelForm.name = row.name
  editModelForm.description = row.description ?? ''
  editModelForm.enabled = row.enabled
  editModelForm.capabilities = [...row.capabilities]
  editingModel.value = true
}

async function handleUpdateModel() {
  if (!editingModelId.value) return
  if (!editModelForm.name) {
    message.warning('请填写统一模型名称')
    return
  }
  savingModel.value = true
  try {
    await updateUnifiedModel(editingModelId.value, { ...editModelForm })
    message.success('统一模型已更新')
    editingModel.value = false
    await loadAll()
  } finally {
    savingModel.value = false
  }
}

async function toggleModel(row: UnifiedModel) {
  await updateUnifiedModel(row.id, { enabled: !row.enabled })
  message.success(row.enabled ? '统一模型已禁用' : '统一模型已启用')
  await loadAll()
}

async function handleDeleteModel(row: UnifiedModel) {
  await deleteUnifiedModel(row.id)
  message.success('统一模型已删除')
  if (selectedModelId.value === row.id) selectedModelId.value = null
  await loadAll()
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

function openCandidateEdit(model: UnifiedModel, candidate: UnifiedModelCandidate) {
  editingCandidateModelId.value = model.id
  editingCandidateId.value = candidate.id
  editCandidateForm.provider_id = candidate.provider_id
  editCandidateForm.upstream_model = candidate.upstream_model
  editCandidateForm.manual_priority = candidate.manual_priority
  editCandidateForm.enabled = candidate.enabled
  editCandidateForm.capabilities = [...candidate.capabilities]
  editingCandidate.value = true
}

async function handleUpdateCandidate() {
  if (!editingCandidateModelId.value || !editingCandidateId.value) return
  if (!editCandidateForm.provider_id || !editCandidateForm.upstream_model) {
    message.warning('请选择 Provider 并填写上游模型')
    return
  }
  savingCandidate.value = true
  try {
    await updateUnifiedModelCandidate(editingCandidateModelId.value, editingCandidateId.value, { ...editCandidateForm })
    message.success('候选模型已更新')
    editingCandidate.value = false
    await loadAll()
  } finally {
    savingCandidate.value = false
  }
}

async function toggleCandidate(model: UnifiedModel, candidate: UnifiedModelCandidate) {
  await updateUnifiedModelCandidate(model.id, candidate.id, { enabled: !candidate.enabled })
  message.success(candidate.enabled ? '候选模型已禁用' : '候选模型已启用')
  await loadAll()
}

async function handleDeleteCandidate(model: UnifiedModel, candidate: UnifiedModelCandidate) {
  await deleteUnifiedModelCandidate(model.id, candidate.id)
  message.success('候选模型已删除')
  await loadAll()
}

onMounted(loadAll)
</script>
