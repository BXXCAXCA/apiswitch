import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import UnifiedModelsView from '../views/UnifiedModelsView.vue'
import ModelDiscoveryView from '../views/ModelDiscoveryView.vue'
import RouterHealthView from '../views/RouterHealthView.vue'
import LogsView from '../views/LogsView.vue'
import TokensView from '../views/TokensView.vue'
import SettingsView from '../views/SettingsView.vue'
import BudgetsView from '../views/BudgetsView.vue'
import WebDAVView from '../views/WebDAVView.vue'
import AgentsView from '../views/AgentsView.vue'

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
        { path: 'tokens', component: TokensView },
        { path: 'settings', component: SettingsView },
        { path: 'budgets', component: BudgetsView },
        { path: 'webdav', component: WebDAVView },
        { path: 'agents', component: AgentsView }
      ]
    }
  ]
})
