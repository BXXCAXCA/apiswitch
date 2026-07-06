import { deleteJson, getJson, patchJson, postJson } from './client'

export interface WebDAVProfile {
  id: number
  name: string
  url: string
  username: string | null
  enabled: boolean
  password_configured: boolean
  created_at: string
  updated_at: string
}

export interface WebDAVProfileCreate {
  name: string
  url: string
  username?: string | null
  password?: string | null
  enabled: boolean
}

export interface WebDAVProfileUpdate {
  name?: string
  url?: string
  username?: string | null
  password?: string | null
  enabled?: boolean
}

export interface WebDAVConnectionResult {
  ok: boolean
  message: string
  status_code: number | null
}

export function fetchWebDAVProfiles() {
  return getJson<WebDAVProfile[]>('/api/admin/webdav')
}

export function createWebDAVProfile(payload: WebDAVProfileCreate) {
  return postJson<WebDAVProfile>('/api/admin/webdav', payload)
}

export function updateWebDAVProfile(profileId: number, payload: WebDAVProfileUpdate) {
  return patchJson<WebDAVProfile>(`/api/admin/webdav/${profileId}`, payload)
}

export function deleteWebDAVProfile(profileId: number) {
  return deleteJson<{ deleted: boolean }>(`/api/admin/webdav/${profileId}`)
}

export function testWebDAVProfile(profileId: number) {
  return postJson<WebDAVConnectionResult>(`/api/admin/webdav/${profileId}/test`, {})
}
