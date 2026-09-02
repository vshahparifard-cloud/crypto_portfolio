export interface MarketRow {
  coin_id: string
  symbol: string
  name: string
  image_url: string | null
  market_cap_rank: number | null
  price_usd: string | null
  market_cap: string | null
  volume_24h: string | null
  pct_change_24h: string | null
  sparkline_7d: number[] | null
  sampled_at: string | null
}

export interface CoinSearchRow {
  coin_id: string
  symbol: string
  name: string
  image_url: string | null
  market_cap_rank: number | null
}

export interface Candle {
  ts: string
  open: string
  high: string
  low: string
  close: string
}

export interface Chart {
  coin_id: string
  range: ChartRange
  interval: string
  points: Candle[]
}

export type ChartRange = '24h' | '7d' | '30d' | '90d' | '1y'

export interface Holding {
  id: string
  coin_id: string
  symbol: string
  name: string
  image_url: string | null
  quantity: string
  avg_buy_price: string
  price_usd: string | null
  sampled_at: string | null
  value_usd: string | null
  cost_usd: string
  pnl_usd: string | null
  pnl_pct: string | null
  pct_change_24h: string | null
  note: string | null
}

export interface Allocation {
  coin_id: string
  symbol: string
  share_pct: string
}

export interface PortfolioSummary {
  total_value_usd: string
  total_cost_usd: string
  pnl_usd: string
  pnl_pct: string | null
  change_24h_usd: string
  holdings_count: number
  allocation: Allocation[]
}

export type AlertKind = 'price_above' | 'price_below' | 'pct_up' | 'pct_down'
export type AlertStatus = 'active' | 'cooling' | 'paused' | 'expired'

export interface Alert {
  id: string
  coin_id: string
  symbol: string
  name: string
  image_url: string | null
  kind: AlertKind
  threshold: string
  window_minutes: number | null
  status: AlertStatus
  cooldown_minutes: number
  is_one_shot: boolean
  last_triggered_at: string | null
  current_price: string | null
  created_at: string
}

export interface AlertEvent {
  id: string
  alert_id: string
  coin_id: string
  symbol: string
  kind: AlertKind
  threshold: string
  price_at_trigger: string
  triggered_at: string
  sampled_at: string
  delivery_state: 'pending' | 'sent' | 'failed' | 'dead'
  attempts: number
}

export interface User {
  id: string
  email: string
  is_verified: boolean
  telegram_connected: boolean
  telegram_linked_at: string | null
  timezone: string
  quiet_from_hour: number | null
  quiet_to_hour: number | null
  created_at: string
}

export interface TelegramLink {
  token: string
  deep_link: string
  expires_in_seconds: string
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: Record<string, unknown>
}
