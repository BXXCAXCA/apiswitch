import { deleteJson, getJson, patchJson, postJson } from './client'

export interface Budget {
  id: number
  name: string
  scope: string
  scope_id: string | null
  monthly_limit: number | null
  currency: string
  enabled: boolean
  spent_amount: number
  alert_threshold_percent: number
  usage_percent: number | null
  alert_triggered: boolean
  enforcement_action: 'warn_only' | 'reject' | 'fallback_to_free' | 'fallback_to_cheapest'
  created_at: string
  updated_at: string
}

export interface BudgetCreate {
  name: string
  scope: string
  scope_id?: string | null
  monthly_limit?: number | null
  currency: string
  enabled: boolean
  spent_amount?: number
  alert_threshold_percent: number
  enforcement_action: 'warn_only' | 'reject' | 'fallback_to_free' | 'fallback_to_cheapest'
}

export interface BudgetUpdate {
  name?: string
  scope?: string
  scope_id?: string | null
  monthly_limit?: number | null
  currency?: string
  enabled?: boolean
  spent_amount?: number
  alert_threshold_percent?: number
  enforcement_action?: 'warn_only' | 'reject' | 'fallback_to_free' | 'fallback_to_cheapest'
}

export function fetchBudgets() {
  return getJson<Budget[]>('/api/admin/budgets')
}

export function createBudget(payload: BudgetCreate) {
  return postJson<Budget>('/api/admin/budgets', payload)
}

export function updateBudget(budgetId: number, payload: BudgetUpdate) {
  return patchJson<Budget>(`/api/admin/budgets/${budgetId}`, payload)
}

export function deleteBudget(budgetId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/budgets/${budgetId}`)
}
