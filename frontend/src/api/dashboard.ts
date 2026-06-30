import { getJson } from './client'

export interface DashboardSummary {
  requests_total: number
  success_rate: number
  failure_rate: number
  average_latency_ms: number
  first_token_latency_ms: number
  open_circuit_breakers: number
  monthly_budget_used: number
  monthly_budget_limit: number
  recent_errors: string[]
}

export function fetchDashboardSummary() {
  return getJson<DashboardSummary>('/api/admin/dashboard/summary')
}
