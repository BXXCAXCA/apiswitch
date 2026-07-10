import { getJson } from './client'

export interface ScoreBreakdown {
  mode: string
  factors: Record<string, number>
  weighted_factors: Record<string, number>
  penalties: Record<string, number>
}

export interface RouterHealthItem {
  unified_model: string
  candidate_id: number
  provider: string
  provider_type: string
  upstream_model: string
  enabled: boolean
  available: boolean
  score: number
  score_breakdown: ScoreBreakdown | null
  success_count: number
  failure_count: number
  consecutive_failures: number
  avg_latency_ms: number | null
  last_failure_reason: string | null
  circuit_state: string
  opened_at: string | null
  half_open_at: string | null
  failure_threshold: number | null
  cooldown_seconds: number | null
}

export interface RouterHealthResponse {
  items: RouterHealthItem[]
  total: number
}

export function fetchRouterHealth() {
  return getJson<RouterHealthResponse>('/api/admin/router-health')
}
