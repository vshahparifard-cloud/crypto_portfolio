<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const route = useRoute()
const auth = useAuth()
const email = ref(String(route.query.email ?? ''))
const message = ref<string | null>(null)
const error = ref<string | null>(null)

async function resend() {
  message.value = null
  error.value = null
  try {
    const result = await auth.resendVerification(email.value)
    message.value = result.message
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'ارسال دوباره ناموفق بود'
  }
}
</script>

<template>
  <div class="auth">
    <div class="box">
      <div class="card">
        <span class="pill fire" style="align-self: flex-start">در انتظار تایید ایمیل</span>
        <h3>ایمیل خود را باز کنید</h3>
        <p style="font-size: 13px; color: var(--ink-2); margin: 0">
          لینک تایید به <b class="mono" style="direction: ltr">{{ email || 'ایمیل شما' }}</b>
          فرستاده شد. اگر نرسید، پوشه هرزنامه را ببینید یا دوباره درخواست کنید.
        </p>
        <div class="field">
          <label>ایمیل</label>
          <input v-model="email" class="input" type="email" />
        </div>
        <p v-if="message" class="notice">{{ message }}</p>
        <p v-if="error" class="notice error">{{ error }}</p>
        <div class="row">
          <button class="btn ghost" style="flex: 1" @click="resend">ارسال دوباره</button>
          <RouterLink class="btn" :to="{ name: 'login' }">صفحه ورود</RouterLink>
        </div>
        <span style="font-size: 11.5px; color: var(--ink-3)">سقف ارسال دوباره: ۳ بار در ساعت.</span>
      </div>
    </div>
  </div>
</template>
