<template>
  <n-space vertical size="large">
    <n-h1>上游模型</n-h1>
    <n-alert type="info">上游模型直接属于供应商实例。同步不会删除被引用模型；远端消失时会标记“远端不可用”。</n-alert>
    <n-card :title="editingId ? '编辑上游模型' : '添加上游模型'">
      <n-form label-placement="left" label-width="110">
        <n-grid responsive="screen" :cols="'1 m:2 l:3'" :x-gap="16">
          <n-form-item-gi label="供应商实例"><n-select data-testid="provider-select" v-model:value="providerId" filterable :disabled="!!editingId" :options="providerOptions" @update:value="changeProvider"/></n-form-item-gi>
          <n-form-item-gi v-if="!editingId" label="远端模型">
            <n-space vertical style="width:100%">
              <n-space vertical style="width:100%"><n-button data-testid="pull-models" :disabled="!providerId" :loading="pulling" @click="pullRemoteModels">拉取模型列表</n-button><n-select data-testid="remote-model-select" v-model:value="selectedRemoteModelId" filterable clearable :options="remoteModelOptions" :render-label="renderRemoteModelLabel" :consistent-menu-width="false" :placeholder="remoteCatalog.length?'请选择远端模型':'拉取后可选择'" style="width:100%;min-width:300px" @update:value="useRemoteModel"/></n-space>
              <span v-if="selectedRemoteModelId" class="model-preview">当前选择：{{ selectedRemoteModelId }}</span><span class="model-preview">选择远端模型会自动填充；列表中没有时可直接输入模型 ID。</span>
            </n-space>
          </n-form-item-gi>
          <n-form-item-gi label="模型 ID"><n-space vertical style="width:100%"><n-input-group><n-input data-testid="model-id-input" v-model:value="form.model_id" :disabled="!!editingId" @update:value="selectedRemoteModelId=null"/><n-button data-testid="infer-capabilities" :disabled="!form.model_id.trim()" @click="inferCapabilities">识别能力</n-button></n-input-group><n-space v-if="capabilitySource" align="center" size="small"><n-tag size="small" :type="capabilityConfidence==='high'?'success':capabilityConfidence==='medium'?'warning':'error'">{{ capabilityConfidence==='high'?'高置信度':capabilityConfidence==='medium'?'中置信度':'需人工确认' }}</n-tag><span class="model-preview">{{ capabilitySource }}</span></n-space></n-space></n-form-item-gi><n-form-item-gi label="显示名"><n-input v-model:value="form.display_name"/></n-form-item-gi>
          <n-form-item-gi label="输入能力"><capability-checkbox-group v-model="form.input_caps" :options="inputCapabilityOptions"/></n-form-item-gi><n-form-item-gi label="输出能力"><capability-checkbox-group v-model="form.output_caps" :options="outputCapabilityOptions"/></n-form-item-gi>
          <n-form-item-gi label="上下文长度"><n-input-number v-model:value="form.context_window" :min="1" clearable/></n-form-item-gi><n-form-item-gi label="最大输出"><n-input-number v-model:value="form.max_output_tokens" :min="1" clearable/></n-form-item-gi>
          <n-form-item-gi label="输入价格/百万"><n-input-number v-model:value="form.input_price" :min="0" clearable/></n-form-item-gi><n-form-item-gi label="输出价格/百万"><n-input-number v-model:value="form.output_price" :min="0" clearable/></n-form-item-gi><n-form-item-gi label="缓存输入价格"><n-input-number v-model:value="form.cached_input_price" :min="0" clearable/></n-form-item-gi>
          <n-form-item-gi label="标签"><n-input v-model:value="form.tags" placeholder="free, fast"/></n-form-item-gi>
        </n-grid>
        <n-space><n-button data-testid="add-upstream-model" type="primary" :disabled="!providerId" @click="save">{{editingId?'保存修改':'添加模型'}}</n-button><n-button v-if="editingId" @click="resetForm">取消</n-button></n-space>
      </n-form>
    </n-card>
    <n-card title="远端模型批量同步">
      <n-space wrap align="center"><n-button :disabled="!providerId" :loading="testing" @click="testProvider">测试连接</n-button><n-button type="primary" :disabled="!providerId" :loading="syncing" @click="sync">同步全部远端模型</n-button><n-tag v-if="syncResult" type="success">新增 {{syncResult.added}} / 更新 {{syncResult.updated}} / 不变 {{syncResult.unchanged}} / 远端消失 {{syncResult.marked_missing}}</n-tag></n-space>
    </n-card>
    <n-card title="模型列表">
      <n-space style="margin-bottom:12px"><n-button :disabled="!checkedRowKeys.length" @click="bulk('enable')">批量启用</n-button><n-button :disabled="!checkedRowKeys.length" @click="bulk('disable')">批量停用</n-button><n-button type="error" :disabled="!checkedRowKeys.length" @click="bulk('delete')">批量删除</n-button></n-space>
      <n-empty v-if="!loading&&!models.length" description="该供应商暂无模型，可同步或手工添加"/>
      <n-data-table v-else :columns="columns" :data="models" :loading="loading" :row-key="(row:any)=>row.id" v-model:checked-row-keys="checkedRowKeys" :pagination="{pageSize:20}"/>
    </n-card>
  </n-space>
</template>
<script setup lang="ts">
import { computed,h,onMounted,reactive,ref } from 'vue'
import { NAlert,NButton,NCard,NDataTable,NEmpty,NForm,NFormItemGi,NGrid,NH1,NInput,NInputGroup,NInputNumber,NSelect,NSpace,NTag,NTooltip,useMessage } from 'naive-ui'
import { deleteJson,getJson,patchJson,postJson } from '../api/client'
import CapabilityCheckboxGroup from '../components/CapabilityCheckboxGroup.vue'
import { inputCapabilityOptions,outputCapabilityOptions } from '../modelCapabilities'
const message=useMessage();const providers=ref<any[]>([]);const models=ref<any[]>([]);const providerId=ref<number|null>(null);const loading=ref(false);const syncing=ref(false);const testing=ref(false);const pulling=ref(false);const probingId=ref<number|null>(null);const syncResult=ref<any>();const checkedRowKeys=ref<Array<number|string>>([]);const editingId=ref<number|null>(null);const remoteCatalog=ref<any[]>([]);const selectedRemoteModelId=ref<string|null>(null);const capabilitySource=ref('');const capabilityConfidence=ref<'high'|'medium'|'low'>('low')
const form=reactive<any>({model_id:'',display_name:'',input_caps:['text'],output_caps:['text'],context_window:null,max_output_tokens:null,input_price:null,output_price:null,cached_input_price:null,tags:''})
const providerOptions=computed(()=>providers.value.map(p=>({label:`${p.name} · ${p.protocol_type}`,value:p.id})))
const remoteModelOptions=computed(()=>remoteCatalog.value.map(model=>({label:model.display_name&&model.display_name!==model.model_id?`${model.display_name} · ${model.model_id}`:model.model_id,value:model.model_id})))
function renderRemoteModelLabel(option:any){return h(NTooltip,{placement:'right',style:{maxWidth:'640px'}},{trigger:()=>h('span',{style:{display:'block',maxWidth:'620px',whiteSpace:'normal',wordBreak:'break-all'}},String(option.label)),default:()=>String(option.label)})}
const csv=(value:string)=>value.split(',').map(x=>x.trim()).filter(Boolean)
function resetForm(){editingId.value=null;selectedRemoteModelId.value=null;capabilitySource.value='';capabilityConfidence.value='low';Object.assign(form,{model_id:'',display_name:'',input_caps:['text'],output_caps:['text'],context_window:null,max_output_tokens:null,input_price:null,output_price:null,cached_input_price:null,tags:''})}
function payload(){return {model_id:form.model_id.trim(),display_name:form.display_name.trim()||form.model_id.trim(),input_capabilities_json:[...form.input_caps],output_capabilities_json:[...form.output_caps],context_window:form.context_window,max_output_tokens:form.max_output_tokens,input_price:form.input_price,output_price:form.output_price,cached_input_price:form.cached_input_price,tags_json:csv(form.tags),pricing_source:'manual'}}
async function loadModels(){if(!providerId.value){models.value=[];return}loading.value=true;try{models.value=await getJson(`/api/admin/provider-instances/${providerId.value}/upstream-models`);checkedRowKeys.value=[]}finally{loading.value=false}}
async function changeProvider(){remoteCatalog.value=[];syncResult.value=undefined;resetForm();await loadModels()}
async function pullRemoteModels(){if(!providerId.value)return;pulling.value=true;try{const result:any=await postJson(`/api/admin/provider-instances/${providerId.value}/upstream-models/discover`,{});remoteCatalog.value=result.models||[];message.success(`已拉取 ${remoteCatalog.value.length} 个远端模型`)}catch(error){message.error(String(error))}finally{pulling.value=false}}
function applyInference(result:any){form.input_caps=[...(result.input_capabilities_json||['text'])];form.output_caps=[...(result.output_capabilities_json||['text'])];form.context_window=result.context_window??form.context_window;form.max_output_tokens=result.max_output_tokens??form.max_output_tokens;capabilityConfidence.value=result.inference_confidence||'low';capabilitySource.value=(result.inference_evidence||[]).join('；')+(result.requires_confirmation?'；请核对下方能力后再添加':'；可继续手动校正')}
async function useRemoteModel(modelId:string|null){if(!modelId)return;const model=remoteCatalog.value.find(item=>item.model_id===modelId);if(!model)return;Object.assign(form,{model_id:model.model_id,display_name:model.display_name||model.model_id,context_window:model.context_window??null,max_output_tokens:model.max_output_tokens??null});try{const result:any=await postJson('/api/admin/upstream-models/infer-capabilities',{model_id:model.model_id,metadata:model.remote_metadata||model});applyInference(result)}catch(error){message.error(String(error))}}
async function inferCapabilities(){const modelId=form.model_id.trim();if(!modelId)return;try{const remote=remoteCatalog.value.find(item=>item.model_id===modelId);const result:any=await postJson('/api/admin/upstream-models/infer-capabilities',{model_id:modelId,metadata:remote?.remote_metadata||remote});applyInference(result);if(!form.display_name.trim())form.display_name=modelId}catch(error){message.error(String(error))}}
async function testProvider(){if(!providerId.value)return;testing.value=true;try{const result:any=await postJson(`/api/admin/provider-instances/${providerId.value}/test`,{});message.success(`连接成功，远端返回 ${result.model_count} 个模型`)}catch(error){message.error(String(error))}finally{testing.value=false}}
async function sync(){if(!providerId.value)return;syncing.value=true;try{syncResult.value=await postJson(`/api/admin/provider-instances/${providerId.value}/upstream-models/sync`,{});await loadModels()}catch(error){message.error(String(error))}finally{syncing.value=false}}
async function save(){if(!providerId.value||!form.model_id.trim())return message.warning('请选择供应商并填写模型 ID');try{if(editingId.value)await patchJson(`/api/admin/upstream-models/${editingId.value}`,payload());else await postJson(`/api/admin/provider-instances/${providerId.value}/upstream-models`,payload());resetForm();await loadModels()}catch(error){message.error(String(error))}}
function edit(row:any){editingId.value=row.id;Object.assign(form,{model_id:row.model_id,display_name:row.display_name,input_caps:[...(row.input_capabilities_json||[])],output_caps:[...(row.output_capabilities_json||[])],context_window:row.context_window,max_output_tokens:row.max_output_tokens,input_price:row.input_price,output_price:row.output_price,cached_input_price:row.cached_input_price,tags:(row.tags_json||[]).join(', ')})}
async function toggle(row:any){await patchJson(`/api/admin/upstream-models/${row.id}`,{enabled:!row.enabled});await loadModels()}
async function remove(row:any){try{await deleteJson(`/api/admin/upstream-models/${row.id}`);await loadModels()}catch(error){message.error(String(error))}}
async function bulk(action:string){try{await postJson('/api/admin/upstream-models/bulk',{ids:checkedRowKeys.value,action});await loadModels()}catch(error){message.error(String(error))}}
async function probe(row:any){probingId.value=row.id;try{const result:any=await postJson(`/api/admin/upstream-models/${row.id}/probe`,{});message.success(`最小化检测成功（${result.request_type}）`);await loadModels()}catch(error){message.error(String(error))}finally{probingId.value=null}}
const columns:any[]=[{type:'selection'},{title:'模型 ID',key:'model_id',ellipsis:{tooltip:true}},{title:'显示名',key:'display_name'},{title:'输入 / 输出能力',key:'caps',render:(r:any)=>`${(r.input_capabilities_json||[]).join(', ')} → ${(r.output_capabilities_json||[]).join(', ')}`},{title:'上下文 / 最大输出',key:'limits',render:(r:any)=>`${r.context_window??'未知'} / ${r.max_output_tokens??'未知'}`},{title:'价格',key:'price',render:(r:any)=>`${r.input_price??'-'} / ${r.output_price??'-'}`},{title:'远端状态',key:'remote_status',render:(r:any)=>h(NTag,{type:r.remote_status==='missing'||r.remote_status==='probe_failed'?'error':r.remote_status==='available'?'success':'default'},{default:()=>({missing:'远端不可用',probe_failed:'检测失败',available:'可用'} as any)[r.remote_status]||r.remote_status})},{title:'引用',key:'reference_count'},{title:'状态',key:'enabled',render:(r:any)=>r.enabled?'启用':'停用'},{title:'操作',key:'actions',width:280,render:(r:any)=>h(NSpace,{wrap:false},{default:()=>[h(NButton,{size:'small',loading:probingId.value===r.id,onClick:()=>probe(r)},{default:()=> '最小检测'}),h(NButton,{size:'small',onClick:()=>edit(r)},{default:()=> '编辑'}),h(NButton,{size:'small',onClick:()=>toggle(r)},{default:()=>r.enabled?'停用':'启用'}),h(NButton,{size:'small',type:'error',disabled:r.reference_count>0,onClick:()=>remove(r)},{default:()=> '删除'})]})}]
onMounted(async()=>{providers.value=await getJson('/api/admin/provider-instances');if(providers.value[0]){providerId.value=providers.value[0].id;await loadModels()}})
</script>
<style scoped>
.model-preview{color:var(--n-text-color-3);font-size:12px;overflow-wrap:anywhere}
</style>
