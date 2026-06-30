import { getJson } from './client'

export interface UnifiedModel {
  id: number
  name: string
  description?: string
  enabled: boolean
  capabilities: string[]
  candidates: Array<Record<string, unknown>>
}

export function fetchUnifiedModels() {
  return getJson<UnifiedModel[]>('/api/admin/unified-models')
}
