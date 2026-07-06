import { deleteJson, getJson, patchJson, postJson } from './client'

export interface ApiToken {
  id: number
  name: string
  token_prefix: string
  enabled: boolean
  scopes: string[]
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export interface ApiTokenCreated extends ApiToken {
  token: string
}

export interface ApiTokenCreate {
  name: string
  scopes: string[]
  expires_at?: string | null
}

export interface ApiTokenUpdate {
  name?: string
  enabled?: boolean
  scopes?: string[]
  expires_at?: string | null
}

export function fetchApiTokens() {
  return getJson<ApiToken[]>('/api/admin/tokens')
}

export function createApiToken(payload: ApiTokenCreate) {
  return postJson<ApiTokenCreated>('/api/admin/tokens', payload)
}

export function updateApiToken(tokenId: number, payload: ApiTokenUpdate) {
  return patchJson<ApiToken>(`/api/admin/tokens/${tokenId}`, payload)
}

export function deleteApiToken(tokenId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/tokens/${tokenId}`)
}
