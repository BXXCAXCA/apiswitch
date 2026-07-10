import { deleteJson, getJson, patchJson, postJson } from './client'

export interface ProviderConnection {
  id: number
  provider_id: number
  name: string
  auth_type: string
  account_label: string | null
  credential_configured: boolean
  refresh_token_configured: boolean
  expires_at: string | null
  priority: number
  enabled: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ProviderConnectionCreate {
  name: string
  auth_type: string
  account_label?: string | null
  credential?: string | null
  refresh_token?: string | null
  expires_at?: string | null
  priority: number
  enabled: boolean
  metadata?: Record<string, unknown>
}

export type ProviderConnectionUpdate = Partial<ProviderConnectionCreate>

export interface ProviderNode {
  id: number
  provider_id: number
  connection_id: number | null
  name: string
  base_url: string
  region: string | null
  enabled: boolean
  weight: number
  capabilities: string[]
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ProviderNodeCreate {
  name: string
  base_url: string
  connection_id?: number | null
  region?: string | null
  enabled: boolean
  weight: number
  capabilities?: string[]
  metadata?: Record<string, unknown>
}

export type ProviderNodeUpdate = Partial<ProviderNodeCreate>

export function fetchProviderConnections(providerId: number) {
  return getJson<ProviderConnection[]>(`/api/admin/providers/${providerId}/connections`)
}

export function createProviderConnection(providerId: number, payload: ProviderConnectionCreate) {
  return postJson<ProviderConnection>(`/api/admin/providers/${providerId}/connections`, payload)
}

export function updateProviderConnection(providerId: number, connectionId: number, payload: ProviderConnectionUpdate) {
  return patchJson<ProviderConnection>(
    `/api/admin/providers/${providerId}/connections/${connectionId}`,
    payload
  )
}

export function deleteProviderConnection(providerId: number, connectionId: number) {
  return deleteJson<{ deleted: boolean }>(
    `/api/admin/providers/${providerId}/connections/${connectionId}`
  )
}

export function fetchProviderNodes(providerId: number, connectionId?: number | null) {
  const query = connectionId ? `?connection_id=${connectionId}` : ''
  return getJson<ProviderNode[]>(`/api/admin/providers/${providerId}/nodes${query}`)
}

export function createProviderNode(providerId: number, payload: ProviderNodeCreate) {
  return postJson<ProviderNode>(`/api/admin/providers/${providerId}/nodes`, payload)
}

export function updateProviderNode(providerId: number, nodeId: number, payload: ProviderNodeUpdate) {
  return patchJson<ProviderNode>(`/api/admin/providers/${providerId}/nodes/${nodeId}`, payload)
}

export function deleteProviderNode(providerId: number, nodeId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/providers/${providerId}/nodes/${nodeId}`)
}
