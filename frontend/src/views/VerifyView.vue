<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError } from '../api/client'
import { useAuth } from '../stores/auth'

const route = useRoute()
const auth = useAuth()
const state = ref<'working' | 'done' | 'failed'>('working')
const message = ref('در حال تایید…')

onMounted(async () => {
  const token = String(route.query.token ?? '')
  if (!token) {
    state.value = 'failed'
    message.value = 'لینک تایید ناقص است.'
    return
  }
  try {
    const result = await auth.verify(token)
    state.value = 'done'
    message.value = result.message
  } catch (exception) {
    state.value = 'failed'
    message.value =
      exception instanceof ApiError ? exception.message : 'این لینک نامعتبر یا منقضی است.'
  }
})
</script>

<template>
  <div class="auth">
    <div class="box">
      <div class="card" style="align-items: center; text-align: center">
        <span
          class="pill"
          :class="state === 'done' ? 'on' : state === 'failed' ? 'off' : 'fire'"
        >
          {{ state === 'done' ? 'تایید شد' : state === 'failed' ? 'ناموفق' : 'در حال بررسی' }}
        </span>
        <h3>{{ message }}</h3>
        <RouterLink v-if="state === 'done'" class="btn" :to="{ name: 'login' }">ورود</RouterLink>
        <RouterLink v-else-if="state === 'failed'" class="btn ghost" :to="{ name: 'verify-pending' }">
          درخواست لینک تازه
        </RouterLink>
      </div>
    </div>
  </div>
</template>
