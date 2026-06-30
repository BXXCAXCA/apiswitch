import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import App from '../src/App.vue'
import { createPinia } from 'pinia'
import { router } from '../src/router'

describe('App', () => {
  it('mounts', async () => {
    const wrapper = mount(App, { global: { plugins: [createPinia(), router] } })
    expect(wrapper.exists()).toBe(true)
  })
})
