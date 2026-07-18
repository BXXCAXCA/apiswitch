import { describe, expect, it } from 'vitest'
import { router } from '../src/router'
import { productNavigation } from '../src/navigation'

describe('router', () => {
  it('contains exactly the twelve new product routes', () => {
    expect(productNavigation.map((item) => item.label)).toEqual([
      '仪表盘', '供应商', '上游模型', '统一模型', '辅助模型', 'API Token',
      '路由状态', '调用日志', '价格与用量', '预算控制', 'Agent 配置', '系统设置'
    ])
    const paths = new Set(router.getRoutes().map((route) => route.path))
    for (const path of productNavigation.map((item) => item.path)) {
      expect(paths.has(path)).toBe(true)
    }
    expect(paths.has('/provider-connections')).toBe(false)
  })
})
