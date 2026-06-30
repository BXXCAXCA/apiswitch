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
}

export interface ProviderCreate {
  name: string
  type: string
  base_url: string
  enabled: boolean
  timeout_seconds: number
  proxy_type?: string | null
  proxy_url?: string | null
}

export function fetchProviders() {
  return getJson<Provider[]>('/api/admin/providers')
}

export function createProvider(payload: ProviderCreate) {
  return postJson<Provider>('/api/admin/providers', payload)
}
