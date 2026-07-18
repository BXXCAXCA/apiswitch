<template>
  <n-space vertical size="large">
    <n-h1>API Token</n-h1>
    <n-alert type="info">这是客户端访问网关的 Token，与供应商 API Key 完全分离。必须明确选择可用统一模型；未选择时模型不可见且不可调用。明文只在创建成功后显示一次。</n-alert>
    <n-alert v-if="createdToken" type="success" closable @close="createdToken=''" title="请立即复制，关闭后无法找回">
      <n-space vertical>
        <n-code :code="createdToken" word-wrap/>
        <n-space><n-button data-testid="copy-created-token" type="primary" size="small" @click="copyCreatedToken">复制 Token</n-button><span style="font-size:12px">若系统阻止自动复制，也可选中文字后按 Ctrl+C。</span></n-space>
      </n-space>
    </n-alert>
    <n-card :title="editingId?'编辑客户端 Token':'创建客户端 Token'">
      <n-form label-placement="top">
        <n-grid responsive="screen" :cols="'1 m:2 l:3'" :x-gap="16">
          <n-form-item-gi label="名称"><n-input data-testid="token-name" v-model:value="form.name"/></n-form-item-gi>
          <n-form-item-gi label="Scopes"><n-select v-model:value="form.scopes" multiple :options="scopeOptions"/></n-form-item-gi>
          <n-form-item-gi label="可用统一模型"><n-select data-testid="token-models" v-model:value="form.unified_model_ids" multiple filterable clearable :options="unifiedModelOptions" placeholder="不选择则不可见、不可调用"/></n-form-item-gi>
          <n-form-item-gi label="有效期"><n-date-picker v-model:value="form.expires_at" type="datetime" clearable style="width:100%"/></n-form-item-gi>
          <n-form-item-gi label="预算归属"><n-select v-model:value="form.budget_id" clearable :options="budgetOptions"/></n-form-item-gi>
          <n-form-item-gi label="启用"><n-switch v-model:value="form.enabled"/></n-form-item-gi>
        </n-grid>
        <n-space><n-button data-testid="create-token" type="primary" :loading="saving" @click="save">{{editingId?'保存修改':'创建 Token'}}</n-button><n-button v-if="editingId" @click="reset">取消</n-button></n-space>
      </n-form>
    </n-card>
    <n-card title="现有 Token"><n-empty v-if="!loading&&!items.length" description="尚未创建客户端 Token"/><n-data-table v-else :columns="columns" :data="items" :loading="loading" :scroll-x="1500"/></n-card>
  </n-space>
</template>
<script setup lang="ts">
import { computed,h,onMounted,reactive,ref } from 'vue'
import { NAlert,NButton,NCard,NCode,NDataTable,NDatePicker,NEmpty,NForm,NFormItemGi,NGrid,NH1,NInput,NSelect,NSpace,NSwitch,NTag,useMessage } from 'naive-ui'
import { deleteJson,getJson,patchJson,postJson } from '../api/client'
import { copyText } from '../clipboard'
import { chinaDatePickerValueToIso, formatChinaDateTime, toChinaDatePickerValue } from '../dateTime'
const message=useMessage();const items=ref<any[]>([]);const budgets=ref<any[]>([]);const unifiedModels=ref<any[]>([]);const loading=ref(false);const saving=ref(false);const createdToken=ref('');const editingId=ref<number|null>(null)
const form=reactive<any>({name:'',scopes:['gateway:invoke'],unified_model_ids:[],expires_at:null,budget_id:null,enabled:true})
const scopeOptions=[{label:'调用网关 gateway:invoke',value:'gateway:invoke'},{label:'管理访问 admin:access',value:'admin:access'}]
const budgetOptions=computed(()=>budgets.value.map(x=>({label:`${x.name} (${x.scope})`,value:x.id})))
const unifiedModelOptions=computed(()=>unifiedModels.value.map(x=>({label:x.name,value:x.id})))
async function load(){loading.value=true;try{[items.value,budgets.value,unifiedModels.value]=await Promise.all([getJson('/api/admin/tokens'),getJson('/api/admin/budgets'),getJson('/api/admin/unified-models')]) as any}finally{loading.value=false}}
function reset(){editingId.value=null;Object.assign(form,{name:'',scopes:['gateway:invoke'],unified_model_ids:[],expires_at:null,budget_id:null,enabled:true})}
function edit(row:any){editingId.value=row.id;Object.assign(form,{name:row.name,scopes:[...(row.scopes||[])],unified_model_ids:[...(row.unified_model_ids||[])],expires_at:toChinaDatePickerValue(row.expires_at),budget_id:row.budget_id||null,enabled:row.enabled})}
function payload(){return {name:form.name.trim(),scopes:form.scopes,unified_model_ids:[...form.unified_model_ids],expires_at:form.expires_at?chinaDatePickerValueToIso(form.expires_at):null,budget_id:form.budget_id,enabled:form.enabled}}
async function copyCreatedToken(){try{await copyText(createdToken.value);message.success('Token 已复制到剪贴板')}catch(error){message.error(String(error))}}
async function save(){if(!form.name.trim()||!form.scopes.length)return message.warning('请填写名称并至少选择一个 Scope');saving.value=true;try{if(editingId.value)await patchJson(`/api/admin/tokens/${editingId.value}`,payload());else{const result:any=await postJson('/api/admin/tokens',payload());createdToken.value=result.token}reset();await load()}catch(error){message.error(String(error))}finally{saving.value=false}}
async function toggle(row:any){await patchJson(`/api/admin/tokens/${row.id}`,{enabled:!row.enabled});await load()}
async function rotate(row:any){if(!window.confirm(`重置“${row.name}”的 Token？旧 Token 将立即失效。`))return;try{const result:any=await postJson(`/api/admin/tokens/${row.id}/rotate`,{});createdToken.value=result.token;await load();message.success('Token 已重置，请立即复制并更新所有客户端')}catch(error){message.error(String(error))}}
async function remove(row:any){try{await deleteJson(`/api/admin/tokens/${row.id}`);await load();message.success('Token 已撤销，历史日志已保留前缀快照')}catch(error){message.error(String(error))}}
const columns:any[]=[{title:'名称',key:'name',fixed:'left'},{title:'前缀',key:'prefix'},{title:'可用统一模型',key:'unified_models',width:260,render:(r:any)=>(r.unified_models||[]).length?h(NSpace,{size:4,wrap:true},{default:()=>r.unified_models.map((model:any)=>h(NTag,{size:'small',type:'info'},{default:()=>model.name}))}):h(NTag,{size:'small',type:'error'},{default:()=> '无（不可调用）'})},{title:'Scopes',key:'scopes',render:(r:any)=>(r.scopes||[]).join(', ')},{title:'有效期（UTC+8）',key:'expires_at',render:(r:any)=>r.expires_at?formatChinaDateTime(r.expires_at):'永不过期'},{title:'预算',key:'budget_id',render:(r:any)=>budgets.value.find(x=>x.id===r.budget_id)?.name||'-'},{title:'最后使用（UTC+8）',key:'last_used_at',render:(r:any)=>r.last_used_at?formatChinaDateTime(r.last_used_at):'从未使用'},{title:'状态',key:'enabled',render:(r:any)=>h(NTag,{type:r.enabled?'success':'default'},{default:()=>r.enabled?'启用':'停用'})},{title:'操作',key:'actions',width:280,fixed:'right',render:(r:any)=>h(NSpace,{wrap:false},{default:()=>[h(NButton,{size:'small',onClick:()=>edit(r)},{default:()=> '编辑'}),h(NButton,{'data-testid':`rotate-token-${r.id}`,size:'small',type:'warning',onClick:()=>rotate(r)},{default:()=> '重置密钥'}),h(NButton,{size:'small',onClick:()=>toggle(r)},{default:()=>r.enabled?'停用':'启用'}),h(NButton,{size:'small',type:'error',onClick:()=>remove(r)},{default:()=> '撤销'})]})}]
onMounted(load)
</script>
