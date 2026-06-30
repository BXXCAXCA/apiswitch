const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
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
