export const CURRENCY_SYMBOLS = { INR: '₹', USD: '$', EUR: '€', GBP: '£' }

export function formatMoney(value, currency = 'INR', options = {}) {
  const number = Number(value || 0)
  const { compact = false, decimals = 0, signed = false } = options
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(Math.abs(number))
  if (signed && number > 0) return `+${formatted}`
  return number < 0 ? `−${formatted}` : formatted
}

export function formatNumber(value, options = {}) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1, ...options }).format(Number(value || 0))
}

export function formatPct(value, decimals = 0) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(decimals)}%`
}

export function formatDate(value, style = 'medium') {
  if (!value) return '—'
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  if (style === 'short') return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  if (style === 'month') return date.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
  if (style === 'long') return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatMonthKey(value) {
  if (!value) return ''
  return new Date(`${value}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
}

export function todayISO() {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60 * 1000).toISOString().slice(0, 10)
}

export function currentMonth() {
  return todayISO().slice(0, 7)
}

export function shiftMonth(month, delta) {
  const [year, monthNumber] = month.split('-').map(Number)
  const date = new Date(year, monthNumber - 1 + delta, 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function titleCase(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function initials(name = '') {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

export const CATEGORY_COLORS = {
  'Food & Dining': '#c9855f',
  Groceries: '#7aa17a',
  Transport: '#6e8fa8',
  Housing: '#2f5d4a',
  Utilities: '#a58a5f',
  Healthcare: '#b06a6a',
  Shopping: '#9a7fb1',
  Entertainment: '#d0a45c',
  Subscriptions: '#5d9c94',
  Education: '#718ba6',
  Travel: '#c27d6a',
  'Loan EMI': '#8c5f5f',
  Insurance: '#7d8f7d',
  Investments: '#3f7d68',
  Other: '#9aa39d',
  Salary: '#2f5d4a',
  Freelance: '#5d9c94',
  Business: '#718ba6',
  'Investment Returns': '#3f7d68',
  Gift: '#d0a45c',
  'Other Income': '#7aa17a',
}

export const CHART_COLORS = ['#315d4b', '#d0a45c', '#718ba6', '#c9855f', '#7aa17a', '#9a7fb1', '#5d9c94', '#b06a6a']

export function colorForCategory(category, index = 0) {
  return CATEGORY_COLORS[category] || CHART_COLORS[index % CHART_COLORS.length]
}
