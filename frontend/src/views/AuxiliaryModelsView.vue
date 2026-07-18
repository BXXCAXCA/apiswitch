<template>
  <n-space vertical size="large">
    <n-h1>辅助模型</n-h1>
    <n-alert type="info">辅助模型直接从“上游模型”中选择。系统按工作流顺序执行，任一步失败都会立即停止，避免产生不完整结果。</n-alert>
    <n-card title="辅助模式"><n-form inline><n-form-item label="模式"><n-select v-model:value="mode" :options="modeOptions" /></n-form-item><n-button @click="saveMode">保存模式</n-button></n-form></n-card>
    <n-card title="辅助模型池">
      <n-form label-placement="top">
        <n-grid responsive="screen" :cols="'1 m:2'" :x-gap="16">
          <n-form-item-gi label="上游模型">
            <n-space vertical style="width:100%">
              <n-select data-testid="aux-upstream-select" v-model:value="modelForm.upstream_model_id" filterable clearable :options="upstreamOptions" :render-label="renderUpstreamLabel" :consistent-menu-width="false" placeholder="请选择上游模型" style="width:100%;min-width:300px" @update:value="useUpstreamModel" />
              <span v-if="selectedUpstreamLabel" class="model-preview">当前选择：{{ selectedUpstreamLabel }}</span>
              <span class="model-preview">完整名称可悬停预览；能力会根据已识别的上游模型自动填充。</span>
            </n-space>
          </n-form-item-gi>
          <n-form-item-gi v-if="mode === 'per_unified_model'" label="统一模型"><n-select v-model:value="modelForm.unified_model_id" :options="unifiedOptions" /></n-form-item-gi>
          <n-form-item-gi label="模型能力"><n-space vertical><capability-checkbox-group v-model="modelForm.capabilities" :options="allCapabilityOptions" /><span v-if="capabilitySource" class="model-preview">{{ capabilitySource }}</span></n-space></n-form-item-gi>
          <n-form-item-gi label="优先级"><n-input-number v-model:value="modelForm.priority" :min="1" /></n-form-item-gi>
        </n-grid>
        <n-space><n-button type="primary" @click="addModel">添加辅助模型</n-button><n-button :loading="loadingUpstream" @click="loadUpstreamModels">刷新上游模型</n-button></n-space>
      </n-form>
      <n-data-table :columns="modelColumns" :data="models" />
    </n-card>
    <n-card title="可排序工作流">
      <n-form label-placement="left" label-width="120">
        <n-grid responsive="screen" :cols="'1 m:2'" :x-gap="16">
          <n-form-item-gi label="预设工作流"><n-select v-model:value="workflowForm.workflow_type" :options="workflowOptions" /></n-form-item-gi>
          <n-form-item-gi v-if="mode === 'per_unified_model'" label="统一模型"><n-select v-model:value="workflowForm.unified_model_id" :options="unifiedOptions" /></n-form-item-gi>
          <n-form-item-gi label="输入能力"><n-select v-model:value="workflowForm.input_capability" filterable :options="allCapabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="输出能力"><n-select v-model:value="workflowForm.output_capability" filterable :options="allCapabilityOptions" /></n-form-item-gi>
          <n-form-item-gi label="工作流顺序"><n-input-number v-model:value="workflowForm.priority" :min="1" /></n-form-item-gi>
        </n-grid>
        <n-form-item label="有序步骤 JSON"><n-input v-model:value="workflowForm.steps" type="textarea" :autosize="{ minRows: 3 }" /></n-form-item>
        <n-button type="primary" @click="addWorkflow">添加工作流</n-button>
      </n-form>
      <n-data-table :columns="workflowColumns" :data="workflows" />
    </n-card>
    <n-card title="模拟匹配结果"><n-form><n-form-item label="统一模型"><n-select v-model:value="planForm.unified_model_id" :options="unifiedOptions"/></n-form-item><n-form-item label="输入能力"><capability-checkbox-group v-model="planForm.required_input" :options="inputCapabilityOptions"/></n-form-item><n-form-item label="输出能力"><capability-checkbox-group v-model="planForm.required_output" :options="outputCapabilityOptions"/></n-form-item><n-button @click="runPlan">模拟规划</n-button></n-form><n-code v-if="planResult" :code="JSON.stringify(planResult,null,2)" language="json" word-wrap/></n-card>
  </n-space>
</template>
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NCode, NDataTable, NForm, NFormItem, NFormItemGi, NGrid, NH1, NInput, NInputNumber, NSelect, NSpace, NTag, NTooltip, useMessage } from 'naive-ui'
import { deleteJson, getJson, patchJson, postJson } from '../api/client'
import CapabilityCheckboxGroup from '../components/CapabilityCheckboxGroup.vue'
import { allCapabilityOptions, inputCapabilityOptions, outputCapabilityOptions } from '../modelCapabilities'
const message=useMessage();const mode=ref('global_pool');const models=ref<any[]>([]);const workflows=ref<any[]>([]);const upstream=ref<any[]>([]);const unified=ref<any[]>([]);const loadingUpstream=ref(false);const capabilitySource=ref('')
const providers=ref<any[]>([]);const planResult=ref<any>();const planForm=reactive<any>({unified_model_id:null,required_input:['text'],required_output:['text']})
const modeLabels:Record<string,string>={disabled:'关闭辅助模型',per_unified_model:'按统一模型独立配置',global_pool:'使用全局辅助模型池'}
const workflowLabels:Record<string,string>={vision_to_text:'图像转文本',file_extract:'文件内容提取',context_compress:'上下文压缩',tool_plan:'工具规划',audio_transcribe:'音频转写',structured_repair:'结构化输出修复',terminal_capability:'终端能力补全'}
const modeOptions=Object.entries(modeLabels).map(([value,label])=>({label,value}));const workflowOptions=Object.entries(workflowLabels).map(([value,label])=>({label,value}))
const modelForm=reactive<any>({upstream_model_id:null,unified_model_id:null,capabilities:['vision'],priority:100});const workflowForm=reactive<any>({workflow_type:'vision_to_text',unified_model_id:null,input_capability:'vision',output_capability:'text',priority:100,steps:'[{"input":"vision","output":"text"}]'})
const unifiedOptions=computed(()=>unified.value.map(x=>({label:x.name,value:x.id})));const upstreamOptions=computed(()=>upstream.value.filter(x=>x.enabled!==false&&x.remote_status!=='missing').map(x=>({label:`${x.provider_name} / ${x.display_name||x.model_id}${x.display_name&&x.display_name!==x.model_id?` · ${x.model_id}`:''}`,value:x.id})));const selectedUpstreamLabel=computed(()=>upstreamOptions.value.find(x=>x.value===modelForm.upstream_model_id)?.label||'')
const validCapabilities=new Set(allCapabilityOptions.map(option=>option.value))
function renderUpstreamLabel(option:any){return h(NTooltip,{placement:'right',style:{maxWidth:'720px'}},{trigger:()=>h('span',{style:{display:'block',maxWidth:'680px',whiteSpace:'normal',wordBreak:'break-all'}},String(option.label)),default:()=>String(option.label)})}
async function loadUpstreamModels(){loadingUpstream.value=true;try{upstream.value=(await Promise.all(providers.value.map(async p=>(await getJson<any[]>(`/api/admin/provider-instances/${p.id}/upstream-models`)).map(x=>({...x,provider_name:p.name}))))).flat()}finally{loadingUpstream.value=false}}
async function load(){mode.value=(await getJson('/api/admin/auxiliary/settings') as any).mode;[models.value,workflows.value,unified.value,providers.value]=await Promise.all([getJson('/api/admin/auxiliary/models'),getJson('/api/admin/auxiliary/workflows'),getJson('/api/admin/unified-models'),getJson('/api/admin/provider-instances')]) as any;await loadUpstreamModels()}
function useUpstreamModel(id:number|null){if(!id){modelForm.capabilities=[];capabilitySource.value='';return}const model=upstream.value.find(item=>item.id===id);if(!model)return;modelForm.capabilities=Array.from(new Set([...(model.input_capabilities_json||[]),...(model.output_capabilities_json||[])])).filter(capability=>validCapabilities.has(capability));capabilitySource.value='已根据上游模型的输入/输出能力自动识别，可手动调整'}
async function saveMode(){await patchJson('/api/admin/auxiliary/settings',{mode:mode.value});message.success('辅助模式已保存')}
async function addModel(){if(!modelForm.upstream_model_id)return message.warning('请选择上游模型');await postJson('/api/admin/auxiliary/models',{upstream_model_id:modelForm.upstream_model_id,unified_model_id:mode.value==='per_unified_model'?modelForm.unified_model_id:null,capabilities:[...modelForm.capabilities],priority:modelForm.priority});await load()}
async function removeModel(row:any){await deleteJson(`/api/admin/auxiliary/models/${row.id}`);await load()}
async function toggleModel(row:any){await patchJson(`/api/admin/auxiliary/models/${row.id}`,{enabled:!row.enabled});await load()}
async function addWorkflow(){let steps;try{steps=JSON.parse(workflowForm.steps);if(!Array.isArray(steps))throw new Error()}catch{return message.error('有序步骤必须是 JSON 数组')};await postJson('/api/admin/auxiliary/workflows',{workflow_type:workflowForm.workflow_type,scope:mode.value==='per_unified_model'?'unified_model':'global',unified_model_id:mode.value==='per_unified_model'?workflowForm.unified_model_id:null,input_capability:workflowForm.input_capability,output_capability:workflowForm.output_capability,priority:workflowForm.priority,ordered_steps:steps});await load()}
async function runPlan(){if(!planForm.unified_model_id)return message.warning('请选择统一模型');planResult.value=await postJson('/api/admin/auxiliary/plan',{unified_model_id:planForm.unified_model_id,required_input:[...planForm.required_input],required_output:[...planForm.required_output]})}
async function removeWorkflow(row:any){await deleteJson(`/api/admin/auxiliary/workflows/${row.id}`);await load()}
async function toggleWorkflow(row:any){await patchJson(`/api/admin/auxiliary/workflows/${row.id}`,{enabled:!row.enabled});await load()}
const actions=(toggle:(row:any)=>Promise<void>,remove:(row:any)=>Promise<void>)=>(row:any)=>h(NSpace,{}, {default:()=>[h(NButton,{size:'small',onClick:()=>toggle(row)},{default:()=>row.enabled?'停用':'启用'}),h(NButton,{size:'small',type:'error',onClick:()=>remove(row)},{default:()=> '删除'})]})
const modelColumns:any[]=[{title:'供应商',key:'provider',render:(r:any)=>r.provider_instance?.name||'-'},{title:'上游模型',key:'upstream',render:(r:any)=>r.upstream_model?.display_name||r.upstream_model?.model_id||r.upstream_model_id},{title:'统一模型',key:'unified_model',render:(r:any)=>r.unified_model?.name||'全局池'},{title:'能力',key:'capabilities',render:(r:any)=>(r.capabilities||[]).join(', ')},{title:'优先级',key:'priority'},{title:'状态',key:'enabled',render:(r:any)=>h(NTag,{type:r.enabled?'success':'default'},{default:()=>r.enabled?'启用':'停用'})},{title:'操作',key:'actions',render:actions(toggleModel,removeModel)}]
const workflowColumns:any[]=[{title:'顺序',key:'priority'},{title:'工作流',key:'workflow_type',render:(r:any)=>workflowLabels[r.workflow_type]||r.workflow_type},{title:'输入 → 输出',key:'flow',render:(r:any)=>`${r.input_capability} → ${r.output_capability}`},{title:'步骤数',key:'ordered_steps',render:(r:any)=>(r.ordered_steps||[]).length},{title:'状态',key:'enabled',render:(r:any)=>h(NTag,{type:r.enabled?'success':'default'},{default:()=>r.enabled?'启用':'停用'})},{title:'操作',key:'actions',render:actions(toggleWorkflow,removeWorkflow)}]
onMounted(load)
</script>
<style scoped>
.model-preview{color:var(--n-text-color-3);font-size:12px;overflow-wrap:anywhere}
</style>
