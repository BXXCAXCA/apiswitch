import { describe, expect, it } from 'vitest'
import { chinaDatePickerValueToIso, formatChinaDateTime, toChinaDatePickerValue } from '../src/dateTime'

describe('UTC+8 date handling', () => {
  it('treats API datetimes without a suffix as UTC and displays UTC+8', () => {
    expect(formatChinaDateTime('2026-07-17T04:08:03.274022')).toBe('2026/07/17 12:08:03')
    expect(formatChinaDateTime('2026-07-17T04:08:03.274022Z')).toBe('2026/07/17 12:08:03')
  })

  it('round-trips API instants through a UTC+8 date picker wall clock', () => {
    const pickerValue = toChinaDatePickerValue('2026-07-17T04:08:03Z')
    expect(pickerValue).not.toBeNull()
    expect(chinaDatePickerValueToIso(pickerValue!)).toBe('2026-07-17T04:08:03.000Z')
  })
})
