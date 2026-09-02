<script setup lang="ts">
import { ref } from 'vue'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const email = ref('')
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)

async function submit() {
  message.value = null
  error.value = null
  busy.value = true
  try {
    const result = await auth.forgotPassword(email.value)
    message.value = result.message
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'درخواست ناموفق بود'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="box">
      <form class="card" @submit.prevent="submit">
        <h3>بازیابی رمز</h3>
        <div class="field">
          <label>ایمیل</label>
          <input v-model="email" class="input" type="email" required />
        </div>
        <p v-if="message" class="notice">{{ message }}</p>
        <p v-if="error" class="notice error">{{ error }}</p>
        <button class="btn" type="submit" :disabled="busy">ارسال لینک بازیابی</button>
        <RouterLink :to="{ name: 'login' }" style="font-size: 12.5px">بازگشت به ورود</RouterLink>
      </form>
    </div>
  </div>
</template>
