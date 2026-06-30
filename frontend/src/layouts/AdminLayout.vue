<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider bordered collapse-mode="width" :collapsed-width="64" :width="240">
      <div class="brand">APISwitch</div>
      <n-menu :options="menuOptions" :value="$route.path" @update:value="handleMenuUpdate" />
    </n-layout-sider>
    <n-layout>
      <n-layout-header bordered class="header">AI API Gateway Control Panel</n-layout-header>
      <n-layout-content class="content"><router-view /></n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NMenu } from 'naive-ui'

const router = useRouter()
const label = (text: string, path: string) => () => h(RouterLink, { to: path }, { default: () => text })
const menuOptions = [
  { label: label('仪表盘', '/dashboard'), key: '/dashboard' },
  { label: label('上游平台', '/providers'), key: '/providers' },
  { label: label('统一模型', '/unified-models'), key: '/unified-models' },
  { label: label('模型发现', '/model-discovery'), key: '/model-discovery' },
  { label: label('路由状态', '/router-health'), key: '/router-health' },
  { label: label('调用日志', '/logs'), key: '/logs' },
  { label: label('预算控制', '/budgets'), key: '/budgets' },
  { label: label('Tokens', '/tokens'), key: '/tokens' },
  { label: label('WebDAV', '/webdav'), key: '/webdav' },
  { label: label('Agent 配置', '/agents'), key: '/agents' },
  { label: label('系统设置', '/settings'), key: '/settings' }
]

function handleMenuUpdate(key: string) {
  router.push(key)
}
</script>

<style scoped>
.brand { font-size: 20px; font-weight: 700; padding: 18px; }
.header { height: 56px; display: flex; align-items: center; padding: 0 24px; font-weight: 600; }
.content { padding: 24px; background: #f6f7f9; }
</style>
