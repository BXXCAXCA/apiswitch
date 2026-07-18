const CHINA_TIME_ZONE = 'Asia/Shanghai'

function hasTimeZone(value: string): boolean {
  return /(?:z|[+-]\d{2}:?\d{2})$/i.test(value)
}

export function parseApiDate(value: string | number | Date): Date {
  if (value instanceof Date || typeof value === 'number') return new Date(value)
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(value) && !hasTimeZone(value) ? `${value}Z` : value
  return new Date(normalized)
}

export function formatChinaDateTime(value: string | number | Date | null | undefined, fallback = '-'): string {
  if (value === null || value === undefined || value === '') return fallback
  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) return fallback
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: CHINA_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).format(date)
}

function chinaParts(value: string | number | Date): Record<string, number> {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: CHINA_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(parseApiDate(value))
  return Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, Number(part.value)]))
}

// Naive UI's DatePicker uses an epoch value but renders it in the browser's
// local zone. Convert API instants to a local wall clock that always represents UTC+8.
export function toChinaDatePickerValue(value: string | number | Date | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) return null
  const part = chinaParts(date)
  return new Date(part.year, part.month - 1, part.day, part.hour, part.minute, part.second).getTime()
}

// Treat the wall-clock value selected in DatePicker as Asia/Shanghai time.
export function chinaDatePickerValueToIso(value: number): string {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  const wallClock = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}+08:00`
  return new Date(wallClock).toISOString()
}
