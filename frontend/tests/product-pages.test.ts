import { flushPromises, mount } from '@vue/test-utils'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import ProvidersView from '../src/views/ProvidersView.vue'
import ModelDiscoveryView from '../src/views/ModelDiscoveryView.vue'
import UnifiedModelsView from '../src/views/UnifiedModelsView.vue'
import AuxiliaryModelsView from '../src/views/AuxiliaryModelsView.vue'
import TokensView from '../src/views/TokensView.vue'
import BudgetsView from '../src/views/BudgetsView.vue'
import LogsView from '../src/views/LogsView.vue'
import AgentsV2View from '../src/views/AgentsV2View.vue'
import SystemSettingsV2View from '../src/views/SystemSettingsV2View.vue'
import CapabilityCheckboxGroup from '../src/components/CapabilityCheckboxGroup.vue'
import { inputCapabilityOptions } from '../src/modelCapabilities'
import { getJson, patchJson, postJson } from '../src/api/client'

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

describe('generation two product pages', () => {
  it('persists the gateway switch from system settings', async () => {
    const getMock = vi.mocked(getJson)
    const patchMock = vi.mocked(patchJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/runtime') return { base_url: 'http://127.0.0.1:8080' } as any
      if (url === '/api/admin/settings') return { gateway_enabled: true, preferred_port: 8080, upload_limit_bytes: 20971520 } as any
      if (url === '/api/admin/settings/startup') return { enabled: false, command: null } as any
      return [] as any
    })
    patchMock.mockResolvedValueOnce({ gateway_enabled: false } as any)

    const wrapper = mountWithMessage(SystemSettingsV2View)
    await flushPromises()
    const gatewaySwitch: any = wrapper.findComponent('[data-testid="gateway-switch"]')
    expect(gatewaySwitch.props('value')).toBe(true)
    gatewaySwitch.vm.$emit('update:value', false)
    await flushPromises()

    expect(patchMock).toHaveBeenCalledWith('/api/admin/settings', { gateway_enabled: false })
    expect(gatewaySwitch.props('value')).toBe(false)
    expect(wrapper.text()).toContain('网关已停用')
    wrapper.unmount()
    patchMock.mockClear()
    getMock.mockImplementation(async () => [] as any)
  })

  it('renders the provider core form and its loading-safe empty state', async () => {
    const wrapper = mountWithMessage(ProvidersView)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('模板目录')
    expect(text).toContain('添加供应商实例')
    expect(text).toContain('API Key')
    expect(text).toContain('自定义请求头')
    expect(text).toContain('尚未添加供应商实例')
  })

  it('declares responsive form grids instead of fixed desktop-only columns', () => {
    const wrapper = mountWithMessage(ProvidersView)
    const responsiveGrid = wrapper.findAllComponents({ name: 'Grid' }).find((grid) => grid.props('responsive') === 'screen')
    expect(responsiveGrid).toBeTruthy()
    expect(responsiveGrid?.props('cols')).toBe('1 m:2')
  })

  it('hides redundant manual protocol templates and keeps the custom template', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/provider-templates') return [
        { key: 'manual', name: '手动供应商 · OpenAI 兼容', protocol_type: 'openai_compatible', verification_status: 'manual' },
        { key: 'manual_anthropic', name: '手动供应商 · Anthropic Messages', protocol_type: 'anthropic_messages', verification_status: 'manual' },
        { key: 'manual_gemini', name: '手动供应商 · Gemini', protocol_type: 'gemini', verification_status: 'manual' },
        { key: 'manual_custom', name: '手动供应商 · 自定义协议', protocol_type: 'custom', verification_status: 'manual' }
      ] as any
      return [] as any
    })

    const wrapper = mountWithMessage(ProvidersView)
    await flushPromises()

    expect(wrapper.find('[data-testid="provider-template-manual"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="provider-template-manual_anthropic"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="provider-template-manual_gemini"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="provider-template-manual_custom"]').exists()).toBe(true)
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('orders the provider catalog for horizontal use with actions first', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/provider-templates'
      ? [{ key: 'openai', name: 'OpenAI', protocol_type: 'openai', region: 'global', base_url: 'https://api.openai.com/v1', verification_status: 'unverified' }]
      : [] as any)
    const wrapper = mountWithMessage(ProvidersView)
    await flushPromises()
    const table: any = wrapper.findComponent('[data-testid="provider-template-table"]')
    expect(table.props('columns').map((column: any) => column.title)).toEqual(['操作', '名称', '协议', '地区', '默认地址'])
    expect(table.props('scrollX')).toBe(1700)
    expect(table.props('columns')[0].fixed).toBe('left')
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('starts a new instance when a catalog template is chosen during editing and restores its API path', async () => {
    const getMock = vi.mocked(getJson)
    const postMock = vi.mocked(postJson)
    const patchMock = vi.mocked(patchJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/provider-templates') return [
        { key: 'openai', name: 'OpenAI', protocol_type: 'openai', base_url: 'https://api.openai.com/v1', verification_status: 'unverified' },
        { key: 'lm_studio', name: 'LM Studio', protocol_type: 'openai_compatible', base_url: 'http://127.0.0.1:1234/v1', verification_status: 'compatible' }
      ] as any
      if (url === '/api/admin/provider-instances') return [{ id: 9, name: 'Existing', template_key: 'openai', protocol_type: 'openai', base_url: 'https://api.openai.com/v1', timeout_seconds: 120, enabled: true }] as any
      return [] as any
    })
    postMock.mockResolvedValue({ id: 10 } as any)
    const wrapper = mountWithMessage(ProvidersView)
    await flushPromises()

    await wrapper.find('[data-testid="provider-edit-9"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('编辑供应商实例')
    await wrapper.find('[data-testid="provider-template-lm_studio"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('添加供应商实例')

    const nameInput: any = wrapper.findComponent('[data-testid="provider-name"]')
    nameInput.vm.$emit('update:value', 'LAN LM Studio')
    const baseInput: any = wrapper.findComponent('[data-testid="provider-base-url"]')
    baseInput.vm.$emit('update:value', 'http://192.168.8.101:1234')
    await wrapper.find('[data-testid="save-provider"]').trigger('click')
    await flushPromises()

    expect(patchMock).not.toHaveBeenCalled()
    expect(postMock).toHaveBeenCalledWith('/api/admin/provider-instances', expect.objectContaining({
      template_key: 'lm_studio',
      name: 'LAN LM Studio',
      base_url: 'http://192.168.8.101:1234/v1'
    }))
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
    postMock.mockImplementation(async () => undefined as any)
  })

  it('uses a fixed checkbox vocabulary for upstream and unified model capabilities', async () => {
    for (const component of [ModelDiscoveryView, UnifiedModelsView, AuxiliaryModelsView]) {
      const wrapper = mountWithMessage(component)
      await flushPromises()
      expect(wrapper.findAllComponents(CapabilityCheckboxGroup).length).toBeGreaterThan(0)
      expect(wrapper.text()).not.toContain('能力（逗号分隔）')
      expect(wrapper.text()).not.toContain('能力覆盖 JSON')
    }
  })

  it('emits selected capabilities from checkboxes instead of accepting free text', async () => {
    const wrapper = mount(CapabilityCheckboxGroup, {
      props: { modelValue: ['text'], options: inputCapabilityOptions }
    })
    const group = wrapper.findComponent({ name: 'CheckboxGroup' })
    group.vm.$emit('update:value', ['text', 'vision'])
    await wrapper.vm.$nextTick()
    const updates = wrapper.emitted('update:modelValue')
    expect(updates?.at(-1)?.[0]).toEqual(['text', 'vision'])
  })

  it('pulls a provider catalog for selection while preserving direct model ID entry', async () => {
    const getMock = vi.mocked(getJson)
    const postMock = vi.mocked(postJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/provider-instances'
      ? [{ id: 7, name: '模拟供应商', protocol_type: 'openai_compatible' }]
      : [] as any)
    postMock.mockImplementation(async (url: string) => url.endsWith('/upstream-models/discover')
      ? { models: [{ model_id: 'remote-a', display_name: 'Remote A', input_capabilities_json: ['text'], output_capabilities_json: ['text'], remote_metadata: { input_modalities: ['text', 'image'] } }] }
      : url.endsWith('/infer-capabilities')
        ? { input_capabilities_json: ['text', 'vision'], output_capabilities_json: ['text'], inference_confidence: 'high', inference_evidence: ['远端目录显式声明模型能力'], requires_confirmation: false }
        : {} as any)

    const wrapper = mountWithMessage(ModelDiscoveryView)
    await flushPromises()
    expect(wrapper.text()).toContain('添加上游模型')
    expect(wrapper.text()).not.toContain('手工添加上游模型')

    await wrapper.find('[data-testid="pull-models"]').trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalledWith('/api/admin/provider-instances/7/upstream-models/discover', {})
    const remoteSelect: any = wrapper.findComponent('[data-testid="remote-model-select"]')
    expect(remoteSelect.props('options')).toEqual([{ label: 'Remote A · remote-a', value: 'remote-a' }])
    expect(remoteSelect.props('consistentMenuWidth')).toBe(false)
    expect(typeof remoteSelect.props('renderLabel')).toBe('function')

    remoteSelect.vm.$emit('update:value', 'remote-a')
    await flushPromises()
    const modelIdInput: any = wrapper.findComponent('[data-testid="model-id-input"]')
    expect(modelIdInput.props('value')).toBe('remote-a')
    expect(wrapper.text()).toContain('当前选择：remote-a')
    expect(wrapper.text()).toContain('高置信度')
    expect(wrapper.text()).toContain('远端目录显式声明模型能力')

    modelIdInput.vm.$emit('update:value', 'manual-model-id')
    await flushPromises()
    expect(modelIdInput.props('value')).toBe('manual-model-id')

    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
    postMock.mockImplementation(async () => undefined as any)
  })

  it('provides complete write flows for all five requested agents', async () => {
    const getMock = vi.mocked(getJson)
    const postMock = vi.mocked(postJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/unified-models'
      ? [{ id: 3, name: 'agent-all', enabled: true, enabled_protocols: ['openai_chat', 'openai_responses', 'gemini_v1beta'] }]
      : [] as any)
    postMock.mockResolvedValue({ config_path: 'C:/Users/test/.codex/config.toml', content: 'model = "agent-all"', language: 'toml', token_hint: '不保存 Token' } as any)
    const wrapper = mountWithMessage(AgentsV2View)
    await flushPromises()
    for (const label of ['Codex', 'OpenCode', '龙虾（OpenClaw）', 'Hermes', 'Gemini CLI']) expect(wrapper.text()).toContain(label)
    const modelSelect: any = wrapper.findComponent('[data-testid="agent-main-model"]')
    expect(modelSelect.props('options')).toEqual([{ label: 'agent-all', value: 3 }])
    modelSelect.vm.$emit('update:value', 3)
    await wrapper.find('[data-testid="agent-preview"]').trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalledWith('/api/admin/agents/codex/preview', expect.objectContaining({ main_model_id: 3 }))
    expect(wrapper.text()).toContain('C:/Users/test/.codex/config.toml')
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
    postMock.mockImplementation(async () => undefined as any)
  })

  it('disables Combo strategy outside Combo mode and explains capability overrides', async () => {
    const wrapper = mountWithMessage(UnifiedModelsView)
    await flushPromises()
    const routing: any = wrapper.findComponent('[data-testid="routing-mode"]')
    const strategy: any = wrapper.findComponent('[data-testid="combo-strategy"]')
    expect(strategy.props('disabled')).toBe(false)
    routing.vm.$emit('update:value', 'static')
    await flushPromises()
    expect(strategy.props('disabled')).toBe(true)
    expect(wrapper.text()).toContain('留空表示继承上游模型')
    wrapper.unmount()
  })

  it('shows complete upstream model names in the unified candidate selector', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/unified-models') return [{ id: 3, name: 'client-model', candidates: [] }] as any
      if (url === '/api/admin/provider-instances') return [{ id: 4, name: '长名称供应商' }] as any
      if (url === '/api/admin/provider-instances/4/upstream-models') return [{
        id: 8,
        model_id: 'namespace/extremely-long-upstream-model-name-that-must-remain-visible',
        display_name: '完整模型显示名称'
      }] as any
      return [] as any
    })
    const wrapper = mountWithMessage(UnifiedModelsView)
    await flushPromises()
    const select: any = wrapper.findComponent('[data-testid="candidate-upstream-select"]')
    expect(select.props('consistentMenuWidth')).toBe(false)
    expect(typeof select.props('renderLabel')).toBe('function')
    expect(select.props('options')).toEqual([{
      label: '长名称供应商 / 完整模型显示名称 · namespace/extremely-long-upstream-model-name-that-must-remain-visible (#8)',
      value: 8
    }])
    select.vm.$emit('update:value', 8)
    await flushPromises()
    expect(wrapper.text()).toContain('当前选择：长名称供应商 / 完整模型显示名称 · namespace/extremely-long-upstream-model-name-that-must-remain-visible (#8)')
    expect(wrapper.find('.model-preview').attributes('title')).toContain('namespace/extremely-long-upstream-model-name-that-must-remain-visible')
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('shows full auxiliary upstream names and inherits inferred capabilities', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/auxiliary/settings') return { mode: 'global_pool' } as any
      if (url === '/api/admin/provider-instances') return [{ id: 4, name: '长名称供应商' }] as any
      if (url === '/api/admin/provider-instances/4/upstream-models') return [{
        id: 8,
        provider_instance_id: 4,
        model_id: 'namespace/extremely-long-vision-embedding-model-name',
        display_name: '完整模型显示名称',
        input_capabilities_json: ['text', 'vision'],
        output_capabilities_json: ['text', 'embeddings']
      }] as any
      return [] as any
    })
    const wrapper = mountWithMessage(AuxiliaryModelsView)
    await flushPromises()
    const select: any = wrapper.findComponent('[data-testid="aux-upstream-select"]')
    expect(select.props('consistentMenuWidth')).toBe(false)
    expect(typeof select.props('renderLabel')).toBe('function')
    select.vm.$emit('update:value', 8)
    await flushPromises()
    expect(wrapper.text()).toContain('当前选择：长名称供应商 / 完整模型显示名称 · namespace/extremely-long-vision-embedding-model-name')
    expect(wrapper.text()).toContain('已根据上游模型的输入/输出能力自动识别')
    const capabilityGroup = wrapper.findAllComponents(CapabilityCheckboxGroup)[0]
    expect(capabilityGroup.props('modelValue')).toEqual(['text', 'vision', 'embeddings'])
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('offers explicit unified-model authorization when creating a token', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/unified-models'
      ? [{ id: 17, name: 'client-model' }]
      : [] as any)
    const wrapper = mountWithMessage(TokensView)
    await flushPromises()
    const select: any = wrapper.findComponent('[data-testid="token-models"]')
    expect(select.props('options')).toEqual([{ label: 'client-model', value: 17 }])
    expect(wrapper.text()).toContain('未选择时模型不可见且不可调用')
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('supports request-count periods scoped to a provider upstream model', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => {
      if (url === '/api/admin/provider-instances') return [{ id: 4, name: '国内供应商' }] as any
      if (url === '/api/admin/provider-instances/4/upstream-models') return [{ id: 8, model_id: 'model-a', display_name: '模型 A' }] as any
      return [] as any
    })
    const wrapper = mountWithMessage(BudgetsView)
    await flushPromises()

    const billing: any = wrapper.findComponent('[data-testid="budget-billing-mode"]')
    expect(billing.props('options')).toContainEqual({ label: '按调用条数', value: 'request_count' })
    billing.vm.$emit('update:value', 'request_count')
    const scope: any = wrapper.findComponent('[data-testid="budget-scope"]')
    scope.vm.$emit('update:value', 'upstream_model')
    await flushPromises()

    expect(wrapper.text()).toContain('调用条数上限')
    const periodSelect: any = wrapper.findComponent('[data-testid="budget-period"]')
    expect(periodSelect.props('options')).toEqual(expect.arrayContaining([
      { label: '滚动 5 小时', value: 'rolling_5_hours' },
      { label: '自然日（UTC+8）', value: 'calendar_day' },
      { label: '自然周（周一至周日，UTC+8）', value: 'calendar_week' }
    ]))
    const targetSelect: any = wrapper.findComponent('[data-testid="budget-target"]')
    expect(targetSelect.props('options')).toEqual([
      { label: '国内供应商 / 模型 A', value: '8' }
    ])
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('sizes the budget table to the full column width so fixed actions do not overlap', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/budgets'
      ? [{ id: 1, name: '每日预算', billing_mode: 'request_count', period_type: 'calendar_day', scope: 'global', usage_value: 0, limit_value: 50, enforcement_action: 'warn', enabled: true }]
      : [] as any)
    const wrapper = mountWithMessage(BudgetsView)
    await flushPromises()
    const table: any = wrapper.findComponent('[data-testid="budget-table"]')
    expect(table.props('scrollX')).toBe(1770)
    expect(table.props('columns').reduce((total: number, column: any) => total + Number(column.width || 0), 0)).toBe(1770)
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('shows the requested log columns and client name without failure-stage or cost columns', async () => {
    const getMock = vi.mocked(getJson)
    getMock.mockImplementation(async (url: string) => {
      if (url.startsWith('/api/admin/logs?')) return [{ request_id: 'req_unit', inbound_protocol: 'openai_chat', provider_name: '供应商 A', upstream_model_name: 'model-a', unified_model: 'stable-a', api_token_id: 7, api_token_name: '桌面客户端', success: true, latency_ms: 12.3, started_at: '2026-07-18T00:00:00Z' }] as any
      if (url === '/api/admin/tokens') return [{ id: 7, name: '桌面客户端', prefix: 'ask_unit' }] as any
      return [] as any
    })
    const wrapper = mountWithMessage(LogsView)
    await flushPromises()
    const table: any = wrapper.findComponent('[data-testid="log-table"]')
    expect(table.props('columns').map((column: any) => column.title)).toEqual(['请求 ID', '协议', '供应商', '上游模型', '统一模型', '客户端名称', '状态', '延迟', '时间（UTC+8）', '操作'])
    expect(wrapper.text()).toContain('桌面客户端')
    expect(wrapper.text()).not.toContain('失败阶段')
    expect(table.props('columns').some((column: any) => column.title === '成本')).toBe(false)
    const clientFilter: any = wrapper.findComponent('[data-testid="log-client-filter"]')
    expect(clientFilter.props('placeholder')).toBe('客户端名称（可选）')
    expect(clientFilter.props('options')).toEqual([{ label: '桌面客户端', value: 7 }])
    wrapper.unmount()
    getMock.mockImplementation(async () => [] as any)
  })

  it('copies the one-time plaintext token with an explicit button', async () => {
    const plaintext = 'ask_unit_placeholder_token'
    const writeText = vi.fn(async () => undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    const postMock = vi.mocked(postJson)
    postMock.mockResolvedValueOnce({ token: plaintext } as any)

    const wrapper = mountWithMessage(TokensView)
    await flushPromises()
    const nameInput: any = wrapper.findComponent('[data-testid="token-name"]')
    nameInput.vm.$emit('update:value', '客户端测试')
    await wrapper.find('[data-testid="create-token"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="copy-created-token"]').exists()).toBe(true)

    await wrapper.find('[data-testid="copy-created-token"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(plaintext)
    wrapper.unmount()
  })

  it('rotates a lost token and exposes the replacement plaintext once', async () => {
    const replacement = 'ask_rotated_unit_placeholder'
    const getMock = vi.mocked(getJson)
    const postMock = vi.mocked(postJson)
    getMock.mockImplementation(async (url: string) => url === '/api/admin/tokens'
      ? [{ id: 9, name: '客户端 Token', prefix: 'ask_old', scopes: ['gateway:invoke'], enabled: true }]
      : [] as any)
    postMock.mockResolvedValueOnce({ id: 9, token: replacement, prefix: 'ask_new' } as any)
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)

    const wrapper = mountWithMessage(TokensView)
    await flushPromises()
    await wrapper.find('[data-testid="rotate-token-9"]').trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/api/admin/tokens/9/rotate', {})
    expect(wrapper.find('[data-testid="copy-created-token"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(replacement)
    wrapper.unmount()
    vi.restoreAllMocks()
    getMock.mockImplementation(async () => [] as any)
  })
})
