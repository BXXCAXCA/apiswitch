import { getJson } from './client'

export interface Provider {
  id: number
  name: string
  type: string
  base_url: string
  enabled: boolean
  timeout_seconds: number
}

export function fetchProviders() {
  return getJson<Provider[]>('/api/admin/providers')
}
