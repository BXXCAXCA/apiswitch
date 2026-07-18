import { createRouter, createWebHashHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import ProvidersView from '../views/ProvidersView.vue'
import ModelDiscoveryView from '../views/ModelDiscoveryView.vue'
import UnifiedModelsView from '../views/UnifiedModelsView.vue'
import AuxiliaryModelsView from '../views/AuxiliaryModelsView.vue'
import RouterStatusView from '../views/RouterStatusView.vue'
import TokensView from '../views/TokensView.vue'
import LogsView from '../views/LogsView.vue'
import AccountingV2View from '../views/AccountingV2View.vue'
import BudgetsView from '../views/BudgetsView.vue'
import AgentsV2View from '../views/AgentsV2View.vue'
import SystemSettingsV2View from '../views/SystemSettingsV2View.vue'

export const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [{ path: '/', component: AdminLayout, children: [
    { path: '', redirect: '/dashboard' }, { path: 'dashboard', component: DashboardView },
    { path: 'providers', component: ProvidersView }, { path: 'upstream-models', component: ModelDiscoveryView },
    { path: 'unified-models', component: UnifiedModelsView }, { path: 'auxiliary-models', component: AuxiliaryModelsView },
    { path: 'tokens', component: TokensView },
    { path: 'router-status', component: RouterStatusView },
    { path: 'logs', component: LogsView },
    { path: 'accounting', component: AccountingV2View },
    { path: 'budgets', component: BudgetsView },
    { path: 'agents', component: AgentsV2View },
    { path: 'settings', component: SystemSettingsV2View }
  ] }]
})
