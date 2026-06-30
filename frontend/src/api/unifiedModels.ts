import { getJson, postJson } from './client'

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
  candidates: UnifiedModelCandidate[]
}

export interface UnifiedModelCreate {
  name: string
  description?: string
  enabled: boolean
  capabilities: string[]
}

export interface UnifiedModelCandidateCreate {
  provider_id: number
  upstream_model: string
  manual_priority: number
  enabled: boolean
  capabilities: string[]
}

export function fetchUnifiedModels() {
  return getJson<UnifiedModel[]>('/api/admin/unified-models')
}

export function createUnifiedModel(payload: UnifiedModelCreate) {
  return postJson<UnifiedModel>('/api/admin/unified-models', payload)
}

export function createUnifiedModelCandidate(modelId: number, payload: UnifiedModelCandidateCreate) {
  return postJson<UnifiedModelCandidate>(`/api/admin/unified-models/${modelId}/candidates`, payload)
}
