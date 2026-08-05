import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import LogsView from '../src/views/LogsView.vue'
import { getJson } from '../src/api/client'

vi.mock('../src/api/client', () => ({
  getJson: vi.fn(async () => []),
  postJson: vi.fn(),
  patchJson: vi.fn(),
  deleteJson: vi.fn()
}))

function mountWithMessage(component: object) {
  return mount(defineComponent({
    render: () => h(NMessageProvider, null, { default: () => h(component) })
  }))
}

function isBefore(first: Element, second: Element) {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
}

describe('call log layout regressions', () => {
  it('places filters, pagination, and the horizontal scrollbar above the table', async () => {
    vi.mocked(getJson).mockImplementation(async (url: string) => {
      if (url.startsWith('/api/admin/logs?')) {
        return [{
          request_id: 'req_layout',
          inbound_protocol: 'openai_responses',
          unified_model: 'client-model',
          success: true,
          latency_ms: 12,
          started_at: '2026-08-05T00:00:00Z'
        }] as any
      }
      return [] as any
    })

    const wrapper = mountWithMessage(LogsView)
    await flushPromises()

    const controls = wrapper.find('[data-testid="log-table-controls"]')
    const cardStack = wrapper.find('[data-testid="log-card-stack"]')
    const pagination = wrapper.find('[data-testid="log-pagination"]')
    const scrollbar = wrapper.find('[data-testid="log-top-scrollbar"]')
    const table = wrapper.find('[data-testid="log-table"]')

    expect(controls.exists()).toBe(true)
    expect(cardStack.exists()).toBe(true)
    expect(cardStack.findAllComponents({ name: 'Card' })).toHaveLength(2)
    expect(controls.text()).toContain('应用筛选')
    expect(controls.text()).toContain('重置')
    expect(pagination.exists()).toBe(true)
    expect(scrollbar.exists()).toBe(true)
    expect(table.exists()).toBe(true)
    expect(isBefore(controls.element, pagination.element)).toBe(true)
    expect(isBefore(pagination.element, scrollbar.element)).toBe(true)
    expect(isBefore(scrollbar.element, table.element)).toBe(true)

    wrapper.unmount()
    vi.mocked(getJson).mockImplementation(async () => [] as any)
  })
})
