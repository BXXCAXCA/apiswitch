import { getJson } from './client'

export interface RouterHealthItem {
  unified_model: string
  candidate_id: number
  provider: string
  provider_type: string
  upstream_model: string
  enabled: boolean
  score: number
  success_count: number
  failure_count: number
  consecutive_failures: number
  avg_latency_ms: number | null
  last_failure_reason: string | null
  circuit_state: string
}

export interface RouterHealthResponse {
  items: RouterHealthItem[]
  total: number
}

export function fetchRouterHealth() {
  return getJson<RouterHealthResponse>('/api/admin/router-health')
}
