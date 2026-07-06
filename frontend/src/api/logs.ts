import { getJson } from './client'

export interface RequestLogItem {
  request_id: string
  started_at: string
  finished_at: string | null
  inbound_protocol: string
  unified_model: string
  final_provider: string | null
  final_upstream_model: string | null
  success: boolean
  error_type: string | null
  error_message: string | null
  retry_chain: Record<string, unknown> | null
  input_tokens: number | null
  output_tokens: number | null
  estimated_cost: number | null
  latency_ms: number | null
  first_token_latency_ms: number | null
  cache_hit: boolean
}

export interface RequestLogsResponse {
  items: RequestLogItem[]
  total: number
}

export function fetchRequestLogs(limit = 50) {
  return getJson<RequestLogsResponse>(`/api/admin/logs?limit=${limit}`)
}
