import { describe, expect, it } from 'vitest'
import { router } from '../src/router'

describe('router', () => {
  it('contains dashboard route', () => {
    expect(router.getRoutes().some((route) => route.path === '/dashboard')).toBe(true)
  })
})
