import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import UnifiedModelsView from '../views/UnifiedModelsView.vue'
import ModelDiscoveryView from '../views/ModelDiscoveryView.vue'
import RouterHealthView from '../views/RouterHealthView.vue'
import LogsView from '../views/LogsView.vue'
import PlaceholderView from '../views/PlaceholderView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AdminLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardView },
        { path: 'providers', component: ProvidersView },
        { path: 'unified-models', component: UnifiedModelsView },
        { path: 'model-discovery', component: ModelDiscoveryView },
        { path: 'router-health', component: RouterHealthView },
        { path: 'logs', component: LogsView },
        { path: 'budgets', component: PlaceholderView, props: { title: '预算控制' } },
        { path: 'tokens', component: PlaceholderView, props: { title: 'API Token 管理' } },
        { path: 'webdav', component: PlaceholderView, props: { title: 'WebDAV 导入导出' } },
        { path: 'agents', component: PlaceholderView, props: { title: 'Agent 配置' } },
        { path: 'settings', component: PlaceholderView, props: { title: '系统设置' } }
      ]
    }
  ]
})
