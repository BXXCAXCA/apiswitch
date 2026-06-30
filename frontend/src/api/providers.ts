import { getJson, postJson } from './client'

export interface Provider {
  id: number
  name: string
  type: string
  base_url: string
  enabled: boolean
  timeout_seconds: number
  proxy_type?: string | null
  proxy_url?: string | null
  api_key_configured: boolean
}

export interface ProviderCreate {
  name: string
  type: string
  base_url: string
  api_key?: string | null
  enabled: boolean
  timeout_seconds: number
  proxy_type?: string | null
  proxy_url?: string | null
}

export interface ProviderConnectionResult {
  provider_id: number
  provider_name: string
  provider_type: string
  ok: boolean
  message: string
}

export interface DiscoveredModel {
  id: string
  owned_by?: string | null
  capabilities: string[]
}

export interface ModelDiscoveryResult {
  provider_id: number
  provider_name: string
  provider_type: string
  models: DiscoveredModel[]
}

export interface ProviderModel {
  id: number
  provider_id: number
  model_name: string
  enabled: boolean
  capabilities: string[]
  owned_by?: string | null
}

export function fetchProviders() {
  return getJson<Provider[]>('/api/admin/providers')
}

export function createProvider(payload: ProviderCreate) {
  return postJson<Provider>('/api/admin/providers', payload)
}

export function testProvider(providerId: number) {
  return postJson<ProviderConnectionResult>(`/api/admin/providers/${providerId}/test`, {})
}

export function discoverProviderModels(providerId: number) {
  return postJson<ModelDiscoveryResult>(`/api/admin/providers/${providerId}/discover-models`, {})
}

export function fetchProviderModels(providerId: number) {
  return getJson<ProviderModel[]>(`/api/admin/providers/${providerId}/models`)
}
