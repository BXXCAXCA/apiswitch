import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

function source(relativePath: string) {
  return readFileSync(
    fileURLToPath(new URL(`../src/views/${relativePath}`, import.meta.url)),
    'utf8'
  )
}

describe('call log layout regressions', () => {
  it('places pagination, the horizontal scrollbar, and filters above the table', () => {
    const content = source('LogsView.vue')
    const controls = content.indexOf('data-testid="log-table-controls"')
    const apply = content.indexOf('应用筛选', controls)
    const reset = content.indexOf('重置', controls)
    const pagination = content.indexOf('data-testid="log-pagination"', controls)
    const scrollbar = content.indexOf('data-testid="log-top-scrollbar"')
    const table = content.indexOf('data-testid="log-table"', scrollbar)

    expect(controls).toBeGreaterThan(-1)
    expect(apply).toBeGreaterThan(controls)
    expect(reset).toBeGreaterThan(controls)
    expect(pagination).toBeGreaterThan(controls)
    expect(scrollbar).toBeGreaterThan(pagination)
    expect(table).toBeGreaterThan(scrollbar)
  })
})
