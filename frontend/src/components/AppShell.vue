<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()

const telegramLabel = computed(() => {
  if (!auth.isAuthenticated) return 'وارد نشده‌اید'
  return auth.user?.telegram_connected ? 'تلگرام: متصل ✓' : 'تلگرام: وصل نشده'
})

async function logout() {
  await auth.logout()
  await router.push({ name: 'market' })
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="logo"><span class="mark">CP</span>کوین‌پالس</div>
      <RouterLink class="nav-item" :to="{ name: 'market' }">◉ بازار</RouterLink>
      <RouterLink class="nav-item" :to="{ name: 'portfolio' }">◈ سبد من</RouterLink>
      <RouterLink class="nav-item" :to="{ name: 'alerts' }">◔ هشدارها</RouterLink>
      <RouterLink class="nav-item" :to="{ name: 'settings' }">⚙ تنظیمات</RouterLink>
      <div class="foot">
        <span>{{ telegramLabel }}</span>
        <span v-if="auth.user" class="mono" style="font-size: 11px">{{ auth.user.email }}</span>
        <button v-if="auth.isAuthenticated" class="btn ghost small" @click="logout">خروج</button>
        <RouterLink v-else class="btn small" :to="{ name: 'login' }" style="text-align: center"
          >ورود</RouterLink
        >
      </div>
    </aside>
    <main class="main"><slot /></main>
  </div>
</template>
