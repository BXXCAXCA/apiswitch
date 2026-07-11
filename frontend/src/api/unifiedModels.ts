import { deleteJson, getJson, patchJson, postJson } from './client'

export interface UnifiedModelCandidate {
  id: number
  unified_model_id: number
  provider_id: number
  provider_name: string
  provider_type: string
  upstream_model: string
  manual_priority: number
  enabled: boolean
  capabilities: string[]
}

export interface UnifiedModel {
  id: number
  name: string
  description?: string
  enabled: boolean
  capabilities: string[]
  routing_mode: 'static' | 'combo' | 'auto'
  category?: string
  preferred_tier: string
  max_request_cost?: number
  min_context_window?: number
  session_affinity_enabled: boolean
  candidates: UnifiedModelCandidate[]
}

export interface UnifiedModelCreate {
  name: string
  description?: string
  enabled: boolean
  capabilities: string[]
  routing_mode: 'static' | 'combo' | 'auto'
  category?: string
  preferred_tier: string
  max_request_cost?: number
  min_context_window?: number
  session_affinity_enabled: boolean
}

export type UnifiedModelUpdate = Partial<UnifiedModelCreate>

export interface UnifiedModelCandidateCreate {
  provider_id: number
  upstream_model: string
  manual_priority: number
  enabled: boolean
  capabilities: string[]
}

export type UnifiedModelCandidateUpdate = Partial<UnifiedModelCandidateCreate>

export function fetchUnifiedModels() {
  return getJson<UnifiedModel[]>('/api/admin/unified-models')
}

export function createUnifiedModel(payload: UnifiedModelCreate) {
  return postJson<UnifiedModel>('/api/admin/unified-models', payload)
}

export function updateUnifiedModel(modelId: number, payload: UnifiedModelUpdate) {
  return patchJson<UnifiedModel>(`/api/admin/unified-models/${modelId}`, payload)
}

export function deleteUnifiedModel(modelId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/unified-models/${modelId}`)
}

export function createUnifiedModelCandidate(modelId: number, payload: UnifiedModelCandidateCreate) {
  return postJson<UnifiedModelCandidate>(`/api/admin/unified-models/${modelId}/candidates`, payload)
}

export function updateUnifiedModelCandidate(modelId: number, candidateId: number, payload: UnifiedModelCandidateUpdate) {
  return patchJson<UnifiedModelCandidate>(`/api/admin/unified-models/${modelId}/candidates/${candidateId}`, payload)
}

export function deleteUnifiedModelCandidate(modelId: number, candidateId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/unified-models/${modelId}/candidates/${candidateId}`)
}
