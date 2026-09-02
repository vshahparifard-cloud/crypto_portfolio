import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { Chart, ChartRange, CoinSearchRow, MarketRow } from '../api/types'

interface State {
  rows: MarketRow[]
  loading: boolean
  error: string | null
  lastSampledAt: string | null
  stream: EventSource | null
  query: string
  searchResults: CoinSearchRow[]
}

export const useMarket = defineStore('market', {
  state: (): State => ({
    rows: [],
    loading: false,
    error: null,
    lastSampledAt: null,
    stream: null,
    query: '',
    searchResults: [],
  }),
  getters: {
    visibleRows: (state) => {
      const q = state.query.trim().toLowerCase()
      if (!q) return state.rows
      return state.rows.filter(
        (row) => row.name.toLowerCase().includes(q) || row.symbol.toLowerCase().includes(q),
      )
    },
    byId: (state) => (coinId: string) => state.rows.find((row) => row.coin_id === coinId) ?? null,
  },
  actions: {
    async load(limit = 50) {
      this.loading = true
      this.error = null
      try {
        this.rows = await api.get<MarketRow[]>(`/market/coins?limit=${limit}`)
        this.lastSampledAt = this.rows[0]?.sampled_at ?? null
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'دریافت فهرست بازار ناموفق بود'
      } finally {
        this.loading = false
      }
    },
    async search(term: string) {
      if (term.trim().length < 1) {
        this.searchResults = []
        return
      }
      this.searchResults = await api.get<CoinSearchRow[]>(
        `/market/search?q=${encodeURIComponent(term.trim())}`,
      )
    },
    async chart(coinId: string, range: ChartRange) {
      return api.get<Chart>(`/market/coins/${coinId}/chart?range=${range}`)
    },
    async coin(coinId: string) {
      return api.get<MarketRow>(`/market/coins/${coinId}`)
    },
    /** Live prices arrive on every poll (every 5 minutes, per D1). */
    connect() {
      if (this.stream) return
      const source = new EventSource(api.streamUrl())
      source.addEventListener('prices', (event) => {
        const updates = JSON.parse((event as MessageEvent).data) as {
          coin_id: string
          price: string
          ts: string
        }[]
        const index = new Map(updates.map((item) => [item.coin_id, item]))
        for (const row of this.rows) {
          const update = index.get(row.coin_id)
          if (update) {
            row.price_usd = update.price
            row.sampled_at = update.ts
          }
        }
        this.lastSampledAt = updates[0]?.ts ?? this.lastSampledAt
      })
      source.onerror = () => {
        /* EventSource reconnects on its own; nothing to do here. */
      }
      this.stream = source
    },
    disconnect() {
      this.stream?.close()
      this.stream = null
    },
  },
})
