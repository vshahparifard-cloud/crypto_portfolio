import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { Holding, PortfolioSummary } from '../api/types'

interface State {
  holdings: Holding[]
  summary: PortfolioSummary | null
  loading: boolean
}

export const usePortfolio = defineStore('portfolio', {
  state: (): State => ({ holdings: [], summary: null, loading: false }),
  actions: {
    async load() {
      this.loading = true
      try {
        const [holdings, summary] = await Promise.all([
          api.get<Holding[]>('/portfolio/holdings'),
          api.get<PortfolioSummary>('/portfolio/summary'),
        ])
        this.holdings = holdings
        this.summary = summary
      } finally {
        this.loading = false
      }
    },
    async add(payload: {
      coin_id: string
      quantity: string
      avg_buy_price: string
      note?: string | null
    }) {
      await api.post<Holding>('/portfolio/holdings', payload)
      await this.load()
    },
    async update(
      id: string,
      payload: { quantity?: string; avg_buy_price?: string; note?: string | null },
    ) {
      await api.patch<Holding>(`/portfolio/holdings/${id}`, payload)
      await this.load()
    },
    async remove(id: string) {
      await api.delete(`/portfolio/holdings/${id}`)
      await this.load()
    },
  },
})
