<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const password = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const done = ref(false)

async function submit() {
  error.value = null
  const token = String(route.query.token ?? '')
  if (!token) {
    error.value = 'لینک بازیابی ناقص است.'
    return
  }
  if (password.value.length < 10) {
    error.value = 'رمز عبور باید حداقل ۱۰ نویسه باشد'
    return
  }
  busy.value = true
  try {
    await auth.resetPassword(token, password.value)
    done.value = true
    setTimeout(() => void router.push({ name: 'login' }), 1500)
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'تغییر رمز ناموفق بود'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="box">
      <form class="card" @submit.prevent="submit">
        <h3>تعیین رمز جدید</h3>
        <div class="field">
          <label>رمز عبور تازه — حداقل ۱۰ نویسه</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password" />
        </div>
        <p v-if="done" class="notice">رمز تغییر کرد؛ به صفحه ورود می‌رویم…</p>
        <p v-if="error" class="notice error">{{ error }}</p>
        <button class="btn" type="submit" :disabled="busy || done">ذخیره رمز</button>
        <span style="font-size: 11.5px; color: var(--ink-3)">
          با تغییر رمز، همه نشست‌های قبلی بسته می‌شوند.
        </span>
      </form>
    </div>
  </div>
</template>
