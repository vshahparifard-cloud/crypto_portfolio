<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const needsVerification = ref(false)
const info = ref<string | null>(null)

async function submit() {
  error.value = null
  needsVerification.value = false
  try {
    await auth.login(email.value, password.value)
    await router.push(String(route.query.next ?? '/market'))
  } catch (exception) {
    if (exception instanceof ApiError && exception.code === 'email_not_verified') {
      needsVerification.value = true
      error.value = exception.message
      return
    }
    error.value = exception instanceof ApiError ? exception.message : 'ورود ناموفق بود'
  }
}

async function resend() {
  const result = await auth.resendVerification(email.value)
  info.value = result.message
}
</script>

<template>
  <div class="auth">
    <div class="box">
      <div class="logo" style="justify-content: center; padding: 0">
        <span class="mark">CP</span>کوین‌پالس
      </div>
      <form class="card" @submit.prevent="submit">
        <h3>ورود به حساب</h3>
        <div class="field">
          <label>ایمیل</label>
          <input v-model="email" class="input" type="email" required autocomplete="email" />
        </div>
        <div class="field">
          <label>رمز عبور</label>
          <input
            v-model="password"
            class="input"
            type="password"
            required
            autocomplete="current-password"
          />
        </div>
        <p v-if="error" class="notice error">{{ error }}</p>
        <p v-if="info" class="notice">{{ info }}</p>
        <button v-if="needsVerification" type="button" class="btn ghost" @click="resend">
          ارسال دوباره ایمیل تایید
        </button>
        <button class="btn" type="submit" :disabled="auth.loading">
          {{ auth.loading ? 'در حال ورود…' : 'ورود' }}
        </button>
        <RouterLink :to="{ name: 'forgot' }" style="font-size: 12.5px">رمزم را فراموش کردم</RouterLink>
      </form>
      <div class="switcher">
        حساب ندارید؟ <RouterLink :to="{ name: 'register' }">ساخت حساب</RouterLink>
      </div>
    </div>
  </div>
</template>
