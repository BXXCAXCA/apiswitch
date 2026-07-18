<template>
  <n-space vertical size="large">
    <n-h1>统一模型</n-h1>
    <n-alert type="info">“入口协议”是客户端调用 APISwitch 时使用的 API 格式；同一个稳定模型名可同时接受 OpenAI Chat、OpenAI Responses、Anthropic Messages 和 Gemini v1beta，网关再转换为候选上游支持的格式。</n-alert>
    <n-card :title="editingModelId?'编辑统一模型':'创建统一模型'">
      <n-form label-placement="left" label-width="120">
        <n-grid responsive="screen" :cols="'1 m:2 l:3'" :x-gap="16">
          <n-form-item-gi label="稳定模型名"><n-input v-model:value="form.name"/></n-form-item-gi><n-form-item-gi label="路由模式"><n-select data-testid="routing-mode" v-model:value="form.routing_mode" :options="routingModes"/></n-form-item-gi><n-form-item-gi label="组合策略"><n-select data-testid="combo-strategy" v-model:value="form.combo_strategy" :options="strategies" :disabled="form.routing_mode!=='combo'" :placeholder="form.routing_mode==='combo'?'请选择策略':'仅组合路由可用'"/></n-form-item-gi>
          <n-form-item-gi label="偏好档位"><n-select v-model:value="form.preferred_tier" :options="tiers"/></n-form-item-gi><n-form-item-gi label="最小上下文"><n-input-number v-model:value="form.min_context_window" clearable :min="1"/></n-form-item-gi><n-form-item-gi label="最大延迟 ms"><n-input-number v-model:value="form.max_latency_ms" clearable :min="1"/></n-form-item-gi>
          <n-form-item-gi label="单次成本上限"><n-input-number v-model:value="form.max_cost_per_request" clearable :min="0"/></n-form-item-gi><n-form-item-gi label="会话粘性"><n-switch v-model:value="form.session_affinity_enabled"/></n-form-item-gi><n-form-item-gi label="启用"><n-switch v-model:value="form.enabled"/></n-form-item-gi>
        </n-grid>
        <n-form-item label="描述"><n-input v-model:value="form.description"/></n-form-item>
        <n-form-item label="入口协议"><n-select v-model:value="form.enabled_protocols" multiple filterable :options="protocolOptions"/></n-form-item>
        <n-grid responsive="screen" :cols="'1 m:2'" :x-gap="16"><n-form-item-gi label="必需输入能力"><capability-checkbox-group v-model="form.required_input" :options="inputCapabilityOptions"/></n-form-item-gi><n-form-item-gi label="必需输出能力"><capability-checkbox-group v-model="form.required_output" :options="outputCapabilityOptions"/></n-form-item-gi></n-grid>
        <n-space><n-button type="primary" @click="saveModel">{{editingModelId?'保存修改':'创建统一模型'}}</n-button><n-button v-if="editingModelId" @click="resetModel">取消</n-button></n-space>
      </n-form>
    </n-card>
    <n-card title="统一模型列表"><n-empty v-if="!unified.length" description="暂无统一模型"/><n-data-table v-else :columns="modelColumns" :data="unified" :pagination="{pageSize:12}"/></n-card>
    <n-card title="候选上游模型">
      <n-alert type="info" style="margin-bottom:12px">能力覆盖只影响此候选在当前统一模型中的能力判断，不会修改上游模型。留空表示继承上游模型；仅在自动识别不准确或该供应商实例实际能力不同的时候设置。</n-alert>
      <n-form inline>
        <n-form-item label="统一模型"><n-select v-model:value="selectedUnifiedId" :options="unifiedOptions" style="min-width:220px"/></n-form-item>
        <n-form-item label="上游模型">
          <n-space vertical :size="4" class="upstream-selector">
            <n-select data-testid="candidate-upstream-select" v-model:value="candidateForm.upstream_model_id" filterable :disabled="!!editingCandidateId" :options="upstreamOptions" :render-label="renderUpstreamLabel" :consistent-menu-width="false" placeholder="请选择上游模型" style="width:100%"/>
            <span v-if="selectedUpstreamLabel" class="model-preview" :title="selectedUpstreamLabel">当前选择：{{ selectedUpstreamLabel }}</span>
          </n-space>
        </n-form-item>
        <n-form-item label="优先级"><n-input-number v-model:value="candidateForm.priority" :min="1"/></n-form-item><n-form-item label="权重"><n-input-number v-model:value="candidateForm.weight" :min="0"/></n-form-item><n-form-item label="启用"><n-switch v-model:value="candidateForm.enabled"/></n-form-item>
      </n-form>
      <n-grid responsive="screen" :cols="'1 m:2'" :x-gap="16"><n-form-item-gi label="覆盖输入能力（可选）"><capability-checkbox-group v-model="candidateForm.override_input" :options="inputCapabilityOptions"/></n-form-item-gi><n-form-item-gi label="覆盖输出能力（可选）"><capability-checkbox-group v-model="candidateForm.override_output" :options="outputCapabilityOptions"/></n-form-item-gi></n-grid>
      <n-space><n-button type="primary" @click="saveCandidate">{{editingCandidateId?'保存候选':'添加候选'}}</n-button><n-button v-if="editingCandidateId" @click="resetCandidate">取消编辑</n-button></n-space>
      <n-data-table style="margin-top:12px" :columns="candidateColumns" :data="selectedModel?.candidates||[]"/>
    </n-card>
  </n-space>
</template>
<script setup lang="ts">
import { computed,h,onMounted,reactive,ref } from 'vue'
import { NAlert,NButton,NCard,NDataTable,NEmpty,NForm,NFormItem,NFormItemGi,NGrid,NH1,NInput,NInputNumber,NSelect,NSpace,NSwitch,NTag,NTooltip,useMessage } from 'naive-ui'
import { deleteJson,getJson,patchJson,postJson } from '../api/client'
import CapabilityCheckboxGroup from '../components/CapabilityCheckboxGroup.vue'
import { inputCapabilityOptions,outputCapabilityOptions } from '../modelCapabilities'
const message=useMessage();const unified=ref<any[]>([]);const upstream=ref<any[]>([]);const editingModelId=ref<number|null>(null);const selectedUnifiedId=ref<number|null>(null);const editingCandidateId=ref<number|null>(null)
const allProtocols=['openai_chat','openai_responses','anthropic_messages','gemini_v1beta','embeddings','files','images','audio','moderations','rerank','search','batches','websocket','video','music']
const protocolLabels:Record<string,string>={openai_chat:'OpenAI Chat Completions',openai_responses:'OpenAI Responses',anthropic_messages:'Anthropic Messages',gemini_v1beta:'Gemini v1beta',embeddings:'向量嵌入',files:'文件',images:'图像',audio:'音频',moderations:'内容审核',rerank:'重排序',search:'搜索',batches:'批处理',websocket:'WebSocket 对话',video:'视频',music:'音乐'}
const routingLabels:Record<string,string>={static:'静态路由',combo:'组合路由',auto:'自动路由'}
const strategyLabels:Record<string,string>={priority:'按优先级',weighted:'加权选择',round_robin:'轮询',least_used:'最少使用',cost_optimized:'成本优先',quota_headroom:'剩余额度优先',last_known_good:'最近成功优先'}
const tierLabels:Record<string,string>={quality:'质量优先',balanced:'均衡',speed:'速度优先',economy:'经济优先'}
const defaultProtocols=['openai_chat','openai_responses','anthropic_messages','gemini_v1beta']
const protocolOptions=allProtocols.map(value=>({label:protocolLabels[value]||value,value}));const strategies=Object.entries(strategyLabels).map(([value,label])=>({label,value}));const routingModes=Object.entries(routingLabels).map(([value,label])=>({label,value}));const tiers=Object.entries(tierLabels).map(([value,label])=>({label,value}))
const form=reactive<any>({name:'',description:'',required_input:[],required_output:[],enabled_protocols:[...defaultProtocols],routing_mode:'combo',combo_strategy:'priority',preferred_tier:'balanced',session_affinity_enabled:true,max_cost_per_request:null,max_latency_ms:null,min_context_window:null,enabled:true})
const candidateForm=reactive<any>({upstream_model_id:null,priority:100,weight:100,enabled:true,override_input:[],override_output:[]})
function upstreamLabel(x:any){const display=String(x.display_name||'').trim();const model=String(x.model_id);return `${x.provider_name} / ${display&&display!==model?`${display} · ${model}`:model} (#${x.id})`}
const unifiedOptions=computed(()=>unified.value.map(x=>({label:x.name,value:x.id})));const selectedModel=computed(()=>unified.value.find(x=>x.id===selectedUnifiedId.value));const upstreamOptions=computed(()=>upstream.value.map(x=>({label:upstreamLabel(x),value:x.id})));const selectedUpstreamLabel=computed(()=>upstreamOptions.value.find(x=>x.value===candidateForm.upstream_model_id)?.label||'')
function renderUpstreamLabel(option:any){return h(NTooltip,{placement:'right',style:{maxWidth:'900px'}},{trigger:()=>h('span',{class:'upstream-option',title:String(option.label)},String(option.label)),default:()=>String(option.label)})}
async function load(){unified.value=await getJson('/api/admin/unified-models');const providers:any[]=await getJson('/api/admin/provider-instances');upstream.value=(await Promise.all(providers.map(async p=>(await getJson<any[]>(`/api/admin/provider-instances/${p.id}/upstream-models`)).map(x=>({...x,provider_name:p.name}))))).flat();if(!selectedUnifiedId.value&&unified.value[0])selectedUnifiedId.value=unified.value[0].id}
function modelPayload(){return {name:form.name.trim(),description:form.description,required_capabilities:{input:[...form.required_input],output:[...form.required_output]},enabled_protocols:form.enabled_protocols,routing_mode:form.routing_mode,combo_strategy:form.combo_strategy,preferred_tier:form.preferred_tier,session_affinity_enabled:form.session_affinity_enabled,max_cost_per_request:form.max_cost_per_request,max_latency_ms:form.max_latency_ms,min_context_window:form.min_context_window,enabled:form.enabled}}
function resetModel(){editingModelId.value=null;Object.assign(form,{name:'',description:'',required_input:[],required_output:[],enabled_protocols:[...defaultProtocols],routing_mode:'combo',combo_strategy:'priority',preferred_tier:'balanced',session_affinity_enabled:true,max_cost_per_request:null,max_latency_ms:null,min_context_window:null,enabled:true})}
function editModel(row:any){editingModelId.value=row.id;Object.assign(form,{name:row.name,description:row.description||'',required_input:[...(row.required_capabilities?.input||[])],required_output:[...(row.required_capabilities?.output||[])],enabled_protocols:[...(row.enabled_protocols||[])],routing_mode:row.routing_mode,combo_strategy:row.combo_strategy,preferred_tier:row.preferred_tier,session_affinity_enabled:row.session_affinity_enabled,max_cost_per_request:row.max_cost_per_request,max_latency_ms:row.max_latency_ms,min_context_window:row.min_context_window,enabled:row.enabled})}
async function saveModel(){if(!form.name.trim()||!form.enabled_protocols.length)return message.warning('请填写稳定模型名并至少开启一个协议');try{if(editingModelId.value)await patchJson(`/api/admin/unified-models/${editingModelId.value}`,modelPayload());else await postJson('/api/admin/unified-models',modelPayload());resetModel();await load()}catch(error){message.error(String(error))}}
async function toggleModel(row:any){await patchJson(`/api/admin/unified-models/${row.id}`,{enabled:!row.enabled});await load()}
async function removeModel(row:any){try{await deleteJson(`/api/admin/unified-models/${row.id}`);if(selectedUnifiedId.value===row.id)selectedUnifiedId.value=null;await load()}catch(error){message.error(String(error))}}
function resetCandidate(){editingCandidateId.value=null;Object.assign(candidateForm,{upstream_model_id:null,priority:100,weight:100,enabled:true,override_input:[],override_output:[]})}
function editCandidate(row:any){editingCandidateId.value=row.id;Object.assign(candidateForm,{upstream_model_id:row.upstream_model_id,priority:row.priority,weight:row.weight,enabled:row.enabled,override_input:[...(row.capability_overrides?.input||[])],override_output:[...(row.capability_overrides?.output||[])]})}
async function saveCandidate(){if(!selectedUnifiedId.value||!candidateForm.upstream_model_id)return message.warning('请选择统一模型和上游模型');const overrides:any={};if(candidateForm.override_input.length)overrides.input=[...candidateForm.override_input];if(candidateForm.override_output.length)overrides.output=[...candidateForm.override_output];const payload={upstream_model_id:candidateForm.upstream_model_id,priority:candidateForm.priority,weight:candidateForm.weight,enabled:candidateForm.enabled,capability_overrides:overrides};try{if(editingCandidateId.value)await patchJson(`/api/admin/unified-models/${selectedUnifiedId.value}/candidates/${editingCandidateId.value}`,payload);else await postJson(`/api/admin/unified-models/${selectedUnifiedId.value}/candidates`,payload);resetCandidate();await load()}catch(error){message.error(String(error))}}
async function deleteCandidate(row:any){await deleteJson(`/api/admin/unified-models/${selectedUnifiedId.value}/candidates/${row.id}`);await load()}
const modelColumns:any[]=[{title:'名称',key:'name'},{title:'入口协议',key:'enabled_protocols',render:(r:any)=>(r.enabled_protocols||[]).map((value:string)=>protocolLabels[value]||value).join('、')},{title:'路由 / 策略 / 档位',key:'routing',render:(r:any)=>`${routingLabels[r.routing_mode]||r.routing_mode} / ${r.routing_mode==='combo'?(strategyLabels[r.combo_strategy]||r.combo_strategy):'—'} / ${tierLabels[r.preferred_tier]||r.preferred_tier}`},{title:'候选',key:'candidates',render:(r:any)=>r.candidates.length},{title:'状态',key:'enabled',render:(r:any)=>h(NTag,{type:r.enabled?'success':'default'},{default:()=>r.enabled?'启用':'停用'})},{title:'操作',key:'actions',width:210,render:(r:any)=>h(NSpace,{wrap:false},{default:()=>[h(NButton,{size:'small',onClick:()=>{selectedUnifiedId.value=r.id;editModel(r)}},{default:()=> '编辑'}),h(NButton,{size:'small',onClick:()=>toggleModel(r)},{default:()=>r.enabled?'停用':'启用'}),h(NButton,{size:'small',type:'error',onClick:()=>removeModel(r)},{default:()=> '删除'})]})}]
const candidateColumns:any[]=[{title:'供应商',key:'provider',render:(r:any)=>r.provider_instance?.name||'-'},{title:'上游模型',key:'upstream',render:(r:any)=>r.upstream_model?.model_id||r.upstream_model_id},{title:'优先级',key:'priority'},{title:'权重',key:'weight'},{title:'能力覆盖',key:'capability_overrides',render:(r:any)=>`${(r.capability_overrides?.input||[]).join(', ')||'继承'} → ${(r.capability_overrides?.output||[]).join(', ')||'继承'}`},{title:'状态',key:'enabled',render:(r:any)=>r.enabled?'启用':'停用'},{title:'操作',key:'actions',render:(r:any)=>h(NSpace,{}, {default:()=>[h(NButton,{size:'small',onClick:()=>editCandidate(r)},{default:()=> '编辑'}),h(NButton,{size:'small',type:'error',onClick:()=>deleteCandidate(r)},{default:()=> '删除'})]})}]
onMounted(load)
</script>
<style scoped>
.upstream-selector{width:min(560px,calc(100vw - 520px));min-width:360px}
.upstream-option{display:block;min-width:520px;max-width:min(900px,calc(100vw - 80px));white-space:normal;word-break:break-all;line-height:1.5}
.model-preview{display:block;max-width:560px;color:#666;font-size:13px;line-height:1.5;white-space:normal;word-break:break-all}
@media (max-width:900px){.upstream-selector{width:100%;min-width:280px}.upstream-option{min-width:280px}}
</style>
