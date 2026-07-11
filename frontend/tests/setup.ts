import { vi } from 'vitest'

const dashboardSummary = {
  requests_total: 0,
  success_rate: 0,
  average_latency_ms: 0,
  open_circuit_breakers: 0
}

vi.stubGlobal(
  'fetch',
  vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/api/admin/dashboard/summary')) {
      return new Response(JSON.stringify(dashboardSummary), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })
  })
)
