<template>
  <n-layout has-sider style="height:100vh">
    <n-layout-sider
      v-model:collapsed="collapsed"
      bordered
      collapsible
      show-trigger="bar"
      collapse-mode="width"
      :collapsed-width="0"
      :width="240"
      @update:collapsed="saveCollapsed"
    >
      <div class="brand-row">
        <span class="brand">APISwitch</span>
        <n-button quaternary circle size="small" title="隐藏侧边栏" aria-label="隐藏侧边栏" @click="collapsed=true">«</n-button>
      </div>
      <n-menu :value="route.path" :options="menuOptions" @update:value="navigate" />
    </n-layout-sider>
    <div class="main-shell">
      <n-layout-content class="content"><router-view /></n-layout-content>
    </div>
  </n-layout>
</template>

<script setup lang="ts">
import { h, ref } from 'vue'
import { NButton, NLayout, NLayoutContent, NLayoutSider, NMenu } from 'naive-ui'
import { RouterLink, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const collapsed = ref(localStorage.getItem('apiswitch.sidebar.collapsed') === '1')
const entries = [
  ['仪表盘', '/dashboard'], ['供应商', '/providers'], ['上游模型', '/upstream-models'], ['统一模型', '/unified-models'],
  ['辅助模型', '/auxiliary-models'], ['API Token', '/tokens'], ['路由状态', '/router-status'], ['调用日志', '/logs'],
  ['价格与用量', '/accounting'], ['预算控制', '/budgets'], ['Agent 配置', '/agents'], ['系统设置', '/settings']
]
const menuOptions = entries.map(([label, path]) => ({ label: () => h(RouterLink, { to: path }, { default: () => label }), key: path }))
function navigate(path: string) { router.push(path) }
function saveCollapsed(value: boolean) { localStorage.setItem('apiswitch.sidebar.collapsed', value ? '1' : '0') }
</script>

<style scoped>
.brand-row{height:96px;display:flex;align-items:center;justify-content:space-between;padding:0 18px 0 22px;box-sizing:border-box}
.brand{font-size:28px;font-weight:700;white-space:nowrap}
.main-shell{min-width:0;flex:1;height:100vh;overflow:hidden;background:#f5f7f9}
.content{height:100%;overflow-y:auto;padding:24px 30px 40px;box-sizing:border-box}
</style>
