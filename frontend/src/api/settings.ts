import { getJson, patchJson } from './client'

export interface SystemSettings {
  listen_host: string
  port: number
  auth_enabled: boolean
  stream_failure_mode: string
  default_timeout_seconds: number
  request_log_retention_days: number
  record_full_request: boolean
  record_full_response: boolean
  default_provider_type: string
  default_unified_model: string
}

export type SystemSettingsUpdate = Partial<SystemSettings>

export interface SettingsResponse {
  settings: SystemSettings
  raw: Record<string, unknown>
}

export function fetchSettings() {
  return getJson<SettingsResponse>('/api/admin/settings')
}

export function updateSettings(payload: SystemSettingsUpdate) {
  return patchJson<SettingsResponse>('/api/admin/settings', payload)
}
