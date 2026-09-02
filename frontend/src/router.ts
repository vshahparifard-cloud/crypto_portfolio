import { createRouter, createWebHistory } from 'vue-router'
import { onSessionLost } from './api/client'
import { useAuth } from './stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/market' },
    { path: '/market', name: 'market', component: () => import('./views/MarketView.vue') },
    { path: '/coin/:id', name: 'coin', component: () => import('./views/CoinView.vue') },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: () => import('./views/PortfolioView.vue'),
      meta: { auth: true },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('./views/AlertsView.vue'),
      meta: { auth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('./views/SettingsView.vue'),
      meta: { auth: true },
    },
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('./views/RegisterView.vue') },
    {
      path: '/verify-pending',
      name: 'verify-pending',
      component: () => import('./views/VerifyPendingView.vue'),
    },
    { path: '/verify', name: 'verify', component: () => import('./views/VerifyView.vue') },
    { path: '/forgot', name: 'forgot', component: () => import('./views/ForgotView.vue') },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('./views/ResetView.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/market' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.ready) await auth.restore()
  if (to.meta.auth && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && auth.isAuthenticated) {
    return { name: 'market' }
  }
  return true
})

onSessionLost(() => {
  void router.push({ name: 'login' })
})
