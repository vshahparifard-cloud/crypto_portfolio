<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()

const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const busy = ref(false)

const strength = computed(() => {
  const value = password.value
  let score = 0
  if (value.length >= 10) score++
  if (value.length >= 14) score++
  if (/[A-Za-z]/.test(value) && /\d/.test(value)) score++
  if (/[^A-Za-z0-9]/.test(value)) score++
  return score
})

async function submit() {
  error.value = null
  if (password.value.length < 10) {
    error.value = 'رمز عبور باید حداقل ۱۰ نویسه باشد'
    return
  }
  busy.value = true
  try {
    const result = await auth.register(email.value, password.value)
    if (result.verification_required) {
      await router.push({ name: 'verify-pending', query: { email: email.value } })
    } else {
      await router.push({ name: 'market' })
    }
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'ثبت‌نام ناموفق بود'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="box">
      <div class="logo" style="justify-content: center; padding: 0">
        <span class="mark">CP</span>ساخت حساب
      </div>
      <form class="card" @submit.prevent="submit">
        <div class="field">
          <label>ایمیل</label>
          <input v-model="email" class="input" type="email" required autocomplete="email" />
        </div>
        <div class="field">
          <label>رمز عبور — حداقل ۱۰ نویسه</label>
          <input
            v-model="password"
            class="input"
            type="password"
            required
            autocomplete="new-password"
          />
          <div class="strength">
            <i v-for="step in 4" :key="step" :class="{ on: strength >= step }"></i>
          </div>
        </div>
        <p v-if="error" class="notice error">{{ error }}</p>
        <button class="btn" type="submit" :disabled="busy">
          {{ busy ? 'در حال ثبت…' : 'ثبت‌نام' }}
        </button>
        <span style="font-size: 11.5px; color: var(--ink-3)">
          پس از ثبت‌نام مستقیم وارد حساب می‌شوید. (تایید ایمیل فعلاً غیرفعال است.)
        </span>
      </form>
      <div class="switcher">
        حساب دارید؟ <RouterLink :to="{ name: 'login' }">ورود</RouterLink>
      </div>
    </div>
  </div>
</template>
