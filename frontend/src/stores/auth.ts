import { defineStore } from 'pinia'
import { api, setAccessToken } from '../api/client'
import type { TelegramLink, User } from '../api/types'

interface State {
  user: User | null
  ready: boolean
  loading: boolean
}

export const useAuth = defineStore('auth', {
  state: (): State => ({ user: null, ready: false, loading: false }),
  getters: {
    isAuthenticated: (state) => state.user !== null,
  },
  actions: {
    /** Called once on boot: the refresh cookie decides whether we have a session. */
    async restore() {
      try {
        const token = await api.post<{ access_token: string }>('/auth/refresh')
        setAccessToken(token.access_token)
        this.user = await api.get<User>('/auth/me')
      } catch {
        this.user = null
        setAccessToken(null)
      } finally {
        this.ready = true
      }
    },
    async login(email: string, password: string) {
      this.loading = true
      try {
        const token = await api.post<{ access_token: string }>('/auth/login', { email, password })
        setAccessToken(token.access_token)
        this.user = await api.get<User>('/auth/me')
      } finally {
        this.loading = false
      }
    },
    async register(email: string, password: string) {
      return api.post<{ message: string }>('/auth/register', { email, password })
    },
    async resendVerification(email: string) {
      return api.post<{ message: string }>('/auth/verify/resend', { email })
    },
    async verify(token: string) {
      return api.post<{ message: string }>(`/auth/verify/${encodeURIComponent(token)}`)
    },
    async forgotPassword(email: string) {
      return api.post<{ message: string }>('/auth/password/forgot', { email })
    },
    async resetPassword(token: string, password: string) {
      return api.post<{ message: string }>('/auth/password/reset', { token, password })
    },
    async logout() {
      try {
        await api.post('/auth/logout')
      } finally {
        setAccessToken(null)
        this.user = null
      }
    },
    async saveSettings(payload: Partial<Pick<User, 'timezone' | 'quiet_from_hour' | 'quiet_to_hour'>>) {
      this.user = await api.patch<User>('/auth/me', payload)
    },
    async telegramLink() {
      return api.post<TelegramLink>('/telegram/link')
    },
    async telegramTest() {
      return api.post<{ message: string }>('/telegram/test')
    },
    async telegramUnlink() {
      await api.delete('/telegram/link')
      if (this.user) this.user.telegram_connected = false
    },
    async refreshUser() {
      if (this.user) this.user = await api.get<User>('/auth/me')
    },
  },
})
