const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
const adminToken = import.meta.env.VITE_ADMIN_TOKEN

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(adminToken ? { Authorization: `Bearer ${adminToken}` } : {}),
      ...(init?.headers ?? {})
    }
  })
  if (!response.ok) {
    let message = `请求失败：HTTP ${response.status}`
    try {
      const payload = await response.json()
      message = payload?.detail?.message ?? payload?.error?.message ?? payload?.detail ?? message
    } catch { /* keep the status-based message */ }
    throw new Error(String(message))
  }
  return response.json() as Promise<T>
}

export async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path)
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export async function patchJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

export async function deleteJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, { method: 'DELETE' })
}
