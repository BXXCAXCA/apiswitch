import { deleteJson, getJson, patchJson, postJson } from './client'

export interface ModelPricing {
  id: number
  provider_id: number | null
  model_name: string
  input_cost_per_million: number | null
  output_cost_per_million: number | null
  cached_input_cost_per_million: number | null
  currency: string
  effective_at: string
  created_at: string
  updated_at: string
}

export interface ModelPricingCreate {
  provider_id?: number | null
  model_name: string
  input_cost_per_million?: number | null
  output_cost_per_million?: number | null
  cached_input_cost_per_million?: number | null
  currency: string
}

export type ModelPricingUpdate = Partial<ModelPricingCreate>

export interface UsageHistory {
  id: number
  request_id: string
  api_token_id: number | null
  provider_connection_id: number | null
  unified_model: string
  upstream_model: string | null
  input_tokens: number | null
  output_tokens: number | null
  estimated_cost: number | null
  created_at: string
}

export interface UsageSummary {
  request_count: number
  input_tokens: number
  output_tokens: number
  estimated_cost: number
  priced_request_count: number
}

export interface QuotaSnapshot {
  id: number
  provider_connection_id: number
  captured_at: string
  remaining_requests: number | null
  remaining_tokens: number | null
  remaining_credit: number | null
  reset_at: string | null
  raw: Record<string, unknown>
}

export function fetchModelPricing() {
  return getJson<ModelPricing[]>('/api/admin/accounting/pricing')
}

export function createModelPricing(payload: ModelPricingCreate) {
  return postJson<ModelPricing>('/api/admin/accounting/pricing', payload)
}

export function updateModelPricing(pricingId: number, payload: ModelPricingUpdate) {
  return patchJson<ModelPricing>(`/api/admin/accounting/pricing/${pricingId}`, payload)
}

export function deleteModelPricing(pricingId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/accounting/pricing/${pricingId}`)
}

export function fetchUsageHistory(limit = 100) {
  return getJson<UsageHistory[]>(`/api/admin/accounting/usage?limit=${limit}`)
}

export function fetchUsageSummary() {
  return getJson<UsageSummary>('/api/admin/accounting/usage/summary')
}

export function fetchQuotaSnapshots(limit = 100) {
  return getJson<QuotaSnapshot[]>(`/api/admin/accounting/quota-snapshots?limit=${limit}`)
}

export function createQuotaSnapshot(payload: {
  provider_connection_id: number
  remaining_requests?: number | null
  remaining_tokens?: number | null
  remaining_credit?: number | null
  reset_at?: string | null
  raw?: Record<string, unknown>
}) {
  return postJson<QuotaSnapshot>('/api/admin/accounting/quota-snapshots', payload)
}
