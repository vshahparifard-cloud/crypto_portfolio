/** Display helpers. Latin digits everywhere, tabular alignment in tables. */
const usd = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
const usdSmall = new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 })

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `$${Math.abs(n) < 1 ? usdSmall.format(n) : usd.format(n)}`
}

export function compactMoney(value: string | null | undefined): string {
  if (!value) return '—'
  const n = Number(value)
  return Number.isFinite(n) ? `$${compact.format(n)}` : '—'
}

export function percent(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}%`
}

export function quantity(value: string | null | undefined): string {
  if (!value) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { maximumFractionDigits: 8 })
}

export function signClass(value: string | number | null | undefined): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}

/** "۲ دقیقه پیش" — the data age matters because samples are 5 minutes apart. */
export function ago(iso: string | null | undefined): string {
  if (!iso) return 'نامشخص'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 45) return 'همین حالا'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} دقیقه پیش`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ساعت پیش`
  return new Date(iso).toLocaleDateString('fa-IR')
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString('fa-IR')} ${d.toLocaleTimeString('fa-IR', {
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

export const KIND_LABELS: Record<string, string> = {
  price_above: 'بالاتر از',
  price_below: 'پایین‌تر از',
  pct_up: 'جهش درصدی',
  pct_down: 'ریزش درصدی',
}

export const STATUS_LABELS: Record<string, string> = {
  active: 'فعال',
  cooling: 'در سکوت',
  paused: 'متوقف',
  expired: 'منقضی',
}

export const DELIVERY_LABELS: Record<string, string> = {
  pending: 'در صف ارسال',
  sent: 'ارسال شد',
  failed: 'تلاش دوباره',
  dead: 'ناموفق',
}
