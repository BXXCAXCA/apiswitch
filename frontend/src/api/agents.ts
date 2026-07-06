import { deleteJson, getJson, patchJson, postJson } from './client'

export interface AgentConfig {
  id: number
  agent_type: string
  config_path: string | null
  last_backup_path: string | null
  enabled: boolean
  notes: string | null
  settings: Record<string, unknown>
  config_exists: boolean
  backup_configured: boolean
  created_at: string
  updated_at: string
}

export interface AgentConfigCreate {
  agent_type: string
  config_path?: string | null
  last_backup_path?: string | null
  enabled: boolean
  notes?: string | null
  settings?: Record<string, unknown>
}

export interface AgentConfigUpdate {
  agent_type?: string
  config_path?: string | null
  last_backup_path?: string | null
  enabled?: boolean
  notes?: string | null
  settings?: Record<string, unknown>
}

export interface AgentConfigCheckResult {
  ok: boolean
  message: string
  config_exists: boolean
}

export function fetchAgents() {
  return getJson<AgentConfig[]>('/api/admin/agents')
}

export function createAgent(payload: AgentConfigCreate) {
  return postJson<AgentConfig>('/api/admin/agents', payload)
}

export function updateAgent(agentId: number, payload: AgentConfigUpdate) {
  return patchJson<AgentConfig>(`/api/admin/agents/${agentId}`, payload)
}

export function deleteAgent(agentId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/agents/${agentId}`)
}

export function checkAgent(agentId: number) {
  return postJson<AgentConfigCheckResult>(`/api/admin/agents/${agentId}/check`, {})
}
