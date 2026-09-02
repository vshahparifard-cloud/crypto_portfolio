import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { Alert, AlertEvent, AlertKind } from '../api/types'

interface State {
  alerts: Alert[]
  events: AlertEvent[]
  loading: boolean
}

export const useAlerts = defineStore('alerts', {
  state: (): State => ({ alerts: [], events: [], loading: false }),
  getters: {
    activeCount: (state) => state.alerts.filter((alert) => alert.status === 'active').length,
    forCoin: (state) => (coinId: string) =>
      state.alerts.filter((alert) => alert.coin_id === coinId && alert.status !== 'expired'),
  },
  actions: {
    async load() {
      this.loading = true
      try {
        const [alerts, events] = await Promise.all([
          api.get<Alert[]>('/alerts'),
          api.get<AlertEvent[]>('/alerts/events?limit=20'),
        ])
        this.alerts = alerts
        this.events = events
      } finally {
        this.loading = false
      }
    },
    async create(payload: {
      coin_id: string
      kind: AlertKind
      threshold: string
      window_minutes?: number | null
      cooldown_minutes: number
      is_one_shot: boolean
    }) {
      const created = await api.post<Alert>('/alerts', payload)
      this.alerts = [created, ...this.alerts]
      return created
    },
    async setStatus(id: string, status: Alert['status']) {
      const updated = await api.patch<Alert>(`/alerts/${id}`, { status })
      this.alerts = this.alerts.map((alert) => (alert.id === id ? updated : alert))
    },
    async remove(id: string) {
      await api.delete(`/alerts/${id}`)
      this.alerts = this.alerts.filter((alert) => alert.id !== id)
    },
  },
})
