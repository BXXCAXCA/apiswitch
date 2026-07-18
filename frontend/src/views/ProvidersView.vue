<template>
  <n-space vertical size="large">
    <n-h1>供应商</n-h1>
    <n-alert type="info">模板只提供默认值；每次保存都会创建独立供应商实例，同一模板可配置多个不同 API Key。读取接口永不返回凭据明文。</n-alert>
    <n-card title="模板目录">
      <div class="catalog-filters"><n-input v-model:value="filters.keyword" clearable placeholder="搜索供应商名称、协议或地址"/><n-select v-model:value="filters.protocol" clearable :options="protocolOptions" placeholder="协议筛选"/><n-select v-model:value="filters.region" clearable :options="regionOptions" placeholder="地区筛选"/><n-select v-model:value="filters.status" clearable :options="statusOptions" placeholder="验证状态"/></div>
      <n-data-table data-testid="provider-template-table" :columns="templateColumns" :data="filteredTemplates" :pagination="{pageSize:10}" :scroll-x="1700"/>
    </n-card>
    <n-card :title="editingId ? '编辑供应商实例' : '添加供应商实例'">
      <n-form label-placement="left" label-width="110">
        <n-grid responsive="screen" :cols="'1 m:2'" :x-gap="16">
          <n-form-item-gi label="模板"><n-select v-model:value="form.template_key" :disabled="!!editingId" :options="templateOptions" @update:value="useTemplate"/></n-form-item-gi>
          <n-form-item-gi label="实例名称"><n-input data-testid="provider-name" v-model:value="form.name"/></n-form-item-gi>
          <n-form-item-gi v-if="isManualTemplate" label="协议"><n-select v-model:value="form.protocol_type" :options="manualProtocols"/></n-form-item-gi>
          <n-form-item-gi label="Base URL"><n-input data-testid="provider-base-url" v-model:value="form.base_url" @blur="normalizeBaseUrl"/></n-form-item-gi>
          <n-form-item-gi label="API Key"><n-input v-model:value="form.api_key" type="password" show-password-on="click" :placeholder="editingId ? '留空表示不修改' : '仅写入，不会再次显示'"/></n-form-item-gi>
          <n-form-item-gi label="超时（秒）"><n-input-number v-model:value="form.timeout_seconds" :min="1" :max="3600"/></n-form-item-gi>
          <n-form-item-gi label="代理类型"><n-select v-model:value="form.proxy_type" clearable :options="proxyOptions"/></n-form-item-gi>
          <n-form-item-gi label="代理 URL"><n-input v-model:value="form.proxy_url" type="password" placeholder="可选，仅写入"/></n-form-item-gi>
        </n-grid>
        <n-alert v-if="selectedTemplate" :type="selectedTemplate.region==='global'?'warning':'info'" style="margin-bottom: 16px">{{ regionHint(selectedTemplate) }}<template v-if="selectedTemplate.configuration_hint"> {{selectedTemplate.configuration_hint}}</template></n-alert>
        <n-form-item label="自定义请求头"><n-input v-model:value="form.custom_headers" type="textarea" :autosize="{minRows:3}" placeholder='JSON，例如 {"X-Organization":"team"}'/></n-form-item>
        <n-space><n-button data-testid="save-provider" type="primary" :loading="saving" @click="save">{{ editingId ? '保存修改' : '添加实例' }}</n-button><n-button v-if="editingId" @click="resetForm">取消编辑</n-button></n-space>
      </n-form>
    </n-card>
    <n-card title="供应商实例">
      <n-empty v-if="!loading && !instances.length" description="尚未添加供应商实例"/>
      <n-data-table v-else :columns="instanceColumns" :data="instances" :loading="loading" :pagination="{pageSize:15}"/>
    </n-card>
  </n-space>
</template>
<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NAlert,NButton,NCard,NDataTable,NEmpty,NForm,NFormItem,NFormItemGi,NGrid,NH1,NInput,NInputNumber,NSelect,NSpace,NTag,useMessage } from 'naive-ui'
import { deleteJson,getJson,patchJson,postJson } from '../api/client'
const message=useMessage();const templates=ref<any[]>([]);const instances=ref<any[]>([]);const loading=ref(false);const saving=ref(false);const editingId=ref<number|null>(null)
const filters=reactive({keyword:'',protocol:null as string|null,region:null as string|null,status:null as string|null})
const form=reactive<any>({template_key:'openai',name:'',protocol_type:'openai',base_url:'',api_key:'',timeout_seconds:120,proxy_type:null,proxy_url:'',custom_headers:''})
const protocolLabels:Record<string,string>={openai:'OpenAI 原生',openai_compatible:'OpenAI 兼容',anthropic_messages:'Anthropic Messages',gemini:'Gemini 原生',custom:'自定义协议'}
const manualProtocols=Object.entries(protocolLabels).filter(([value])=>value!=='openai').map(([value,label])=>({label,value}))
const proxyOptions=[{label:'HTTP/HTTPS',value:'http'},{label:'SOCKS5',value:'socks5'}]
const hiddenManualTemplateKeys=new Set(['manual','manual_anthropic','manual_gemini'])
const visibleTemplates=computed(()=>templates.value.filter(x=>!hiddenManualTemplateKeys.has(x.key)))
const templateOptions=computed(()=>visibleTemplates.value.map(x=>({label:`${x.name}（${statusText(x.verification_status)}）`,value:x.key})))
const selectedTemplate=computed(()=>templates.value.find(x=>x.key===form.template_key))
const isManualTemplate=computed(()=>String(form.template_key).startsWith('manual'))
const protocolOptions=computed(()=>Array.from(new Set<string>(visibleTemplates.value.map(x=>x.protocol_type))).map(value=>({label:protocolLabels[value]||value,value})))
const regionOptions=[{label:'国内直连',value:'native'},{label:'全球（通常需要代理）',value:'global'},{label:'本地部署',value:'local'}]
const statusOptions=[{label:'专用适配/已验证',value:'verified'},{label:'兼容模式',value:'compatible'},{label:'未验证',value:'unverified'},{label:'手动',value:'manual'}]
const filteredTemplates=computed(()=>visibleTemplates.value.filter(x=>(!filters.keyword||`${x.name} ${x.key} ${x.protocol_type} ${x.base_url}`.toLowerCase().includes(filters.keyword.toLowerCase()))&&(!filters.protocol||x.protocol_type===filters.protocol)&&(!filters.region||x.region===filters.region)&&(!filters.status||x.verification_status===filters.status)))
function statusText(value:string){return ({verified:'专用适配/已验证',connection_verified:'连接已验证',compatible:'兼容模式',unverified:'未验证',manual:'手动'} as any)[value]||value}
function regionText(value:string){return ({native:'国内直连',global:'全球/需代理',local:'本地部署'} as Record<string,string>)[value]||value}
function regionHint(item:any){return item.region==='global'?'该供应商属于全球服务，无法直连时请配置 HTTP/SOCKS5 代理。':item.region==='local'?'该模板用于本地部署，默认地址已校验为回环地址。':'该供应商属于国内服务，通常可直接连接。'}
async function load(){loading.value=true;try{[templates.value,instances.value]=await Promise.all([getJson('/api/admin/provider-templates'),getJson('/api/admin/provider-instances')]) as any;if(!form.base_url)useTemplate(form.template_key)}finally{loading.value=false}}
function useTemplate(key:string){const item=templates.value.find(x=>x.key===key);form.base_url=item?.base_url||'';form.protocol_type=item?.protocol_type||'openai_compatible';form.custom_headers=Object.keys(item?.default_headers||{}).length?JSON.stringify(item.default_headers,null,2):''}
function selectTemplate(key:string){if(editingId.value){editingId.value=null;Object.assign(form,{name:'',api_key:'',proxy_type:null,proxy_url:'',custom_headers:''})}form.template_key=key;useTemplate(key)}
function normalizeBaseUrl(){const value=form.base_url.trim();const item=selectedTemplate.value;if(!value||!item||item.key==='manual')return;try{const target=new URL(value);const fallback=new URL(item.base_url);if((target.pathname===''||target.pathname==='/')&&fallback.pathname&&fallback.pathname!=='/'){target.pathname=fallback.pathname;form.base_url=target.toString().replace(/\/$/,'')}}catch{/* 后端会返回结构化 URL 校验错误 */}}
function resetForm(){editingId.value=null;Object.assign(form,{template_key:'openai',name:'',protocol_type:'openai',base_url:'',api_key:'',timeout_seconds:120,proxy_type:null,proxy_url:'',custom_headers:''});useTemplate('openai')}
function edit(row:any){editingId.value=row.id;Object.assign(form,{template_key:row.template_key,name:row.name,protocol_type:row.protocol_type,base_url:row.base_url,api_key:'',timeout_seconds:row.timeout_seconds,proxy_type:row.proxy_type||null,proxy_url:'',custom_headers:''})}
function payload(){normalizeBaseUrl();const value:any={template_key:form.template_key,name:form.name.trim(),protocol_type:form.protocol_type,base_url:form.base_url.trim(),timeout_seconds:form.timeout_seconds,proxy_type:form.proxy_type};if(form.api_key)value.api_key=form.api_key;if(form.proxy_url)value.proxy_url=form.proxy_url;if(form.custom_headers.trim()){try{value.custom_headers=JSON.parse(form.custom_headers)}catch{throw new Error('自定义请求头必须是 JSON 对象')}}return value}
async function save(){if(!form.name.trim()||!form.base_url.trim())return message.warning('请填写实例名称和 Base URL');saving.value=true;try{const value=payload();if(editingId.value)await patchJson(`/api/admin/provider-instances/${editingId.value}`,value);else await postJson('/api/admin/provider-instances',value);message.success(editingId.value?'供应商实例已更新':'供应商实例已添加');resetForm();await load()}catch(error){message.error(String(error))}finally{saving.value=false}}
async function testConnection(row:any){try{const result:any=await postJson(`/api/admin/provider-instances/${row.id}/test`,{});message.success(`连接成功，发现 ${result.model_count} 个模型`);await load()}catch(error){message.error(String(error))}}
async function duplicate(row:any){try{await postJson(`/api/admin/provider-instances/${row.id}/duplicate`,{});await load();message.success('已复制为独立实例，可继续写入不同 API Key')}catch(error){message.error(String(error))}}
async function toggle(row:any){await patchJson(`/api/admin/provider-instances/${row.id}`,{enabled:!row.enabled});await load()}
async function remove(row:any){try{await deleteJson(`/api/admin/provider-instances/${row.id}`);await load()}catch(error){message.error(String(error))}}
const templateColumns:any[]=[{title:'操作',key:'actions',width:110,fixed:'left',render:(r:any)=>h(NButton,{size:'small','data-testid':`provider-template-${r.key}`,onClick:()=>selectTemplate(r.key)},{default:()=> '使用模板'})},{title:'名称',key:'name',width:300},{title:'协议',key:'protocol_type',width:220,render:(r:any)=>protocolLabels[r.protocol_type]||r.protocol_type},{title:'地区',key:'region',width:170,render:(r:any)=>regionText(r.region)},{title:'默认地址',key:'base_url',width:900,ellipsis:{tooltip:true},render:(r:any)=>r.base_url||'手动填写'}]
const instanceColumns:any[]=[{title:'名称',key:'name'},{title:'模板',key:'template_key'},{title:'协议',key:'protocol_type'},{title:'Base URL',key:'base_url',ellipsis:{tooltip:true}},{title:'凭据',key:'credential_configured',render:(r:any)=>h(NTag,{type:r.credential_configured?'success':'warning'},{default:()=>r.credential_configured?'已配置':'未配置'})},{title:'连接状态',key:'verification_status',render:(r:any)=>statusText(r.verification_status)},{title:'启用',key:'enabled',render:(r:any)=>r.enabled?'是':'否'},{title:'操作',key:'actions',width:330,render:(r:any)=>h(NSpace,{wrap:false},{default:()=>[h(NButton,{size:'small','data-testid':`provider-edit-${r.id}`,onClick:()=>edit(r)},{default:()=> '编辑'}),h(NButton,{size:'small',onClick:()=>testConnection(r)},{default:()=> '测试'}),h(NButton,{size:'small',onClick:()=>duplicate(r)},{default:()=> '复制'}),h(NButton,{size:'small',onClick:()=>toggle(r)},{default:()=>r.enabled?'停用':'启用'}),h(NButton,{size:'small',type:'error',onClick:()=>remove(r)},{default:()=> '删除'})]})}]
onMounted(load)
</script>
<style scoped>
.catalog-filters{display:grid;grid-template-columns:minmax(260px,2fr) repeat(3,minmax(150px,1fr));gap:12px;margin-bottom:16px;align-items:center}
@media (max-width:1000px){.catalog-filters{grid-template-columns:1fr 1fr}}
@media (max-width:640px){.catalog-filters{grid-template-columns:1fr}}
</style>
