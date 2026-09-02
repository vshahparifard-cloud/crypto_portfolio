<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError } from '../api/client'
import { dateTime } from '../format'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const link = ref<string | null>(null)
const message = ref<string | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)
const quietFrom = ref<number | null>(null)
const quietTo = ref<number | null>(null)

onMounted(async () => {
  await auth.refreshUser()
  quietFrom.value = auth.user?.quiet_from_hour ?? null
  quietTo.value = auth.user?.quiet_to_hour ?? null
})

async function run(action: () => Promise<void>) {
  busy.value = true
  message.value = null
  error.value = null
  try {
    await action()
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'انجام نشد'
  } finally {
    busy.value = false
  }
}

const createLink = () =>
  run(async () => {
    const result = await auth.telegramLink()
    link.value = result.deep_link
    message.value = 'لینک ساخته شد و ۱۰ دقیقه اعتبار دارد.'
  })

const sendTest = () =>
  run(async () => {
    const result = await auth.telegramTest()
    message.value = result.message
  })

const disconnect = () =>
  run(async () => {
    await auth.telegramUnlink()
    link.value = null
    message.value = 'اتصال تلگرام قطع شد.'
  })

const saveQuiet = () =>
  run(async () => {
    await auth.saveSettings({ quiet_from_hour: quietFrom.value, quiet_to_hour: quietTo.value })
    message.value = 'ساعت آرام ذخیره شد.'
  })
</script>

<template>
  <span class="page-title">تنظیمات</span>

  <p v-if="message" class="notice">{{ message }}</p>
  <p v-if="error" class="notice error">{{ error }}</p>

  <div class="card" style="display: flex; flex-direction: column; gap: 14px">
    <h3 style="font-size: 15px">اتصال به تلگرام</h3>
    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
      <span class="pill" :class="auth.user?.telegram_connected ? 'on' : 'off'">
        {{ auth.user?.telegram_connected ? 'متصل' : 'وصل نشده' }}
      </span>
      <span v-if="auth.user?.telegram_linked_at" style="font-size: 12px; color: var(--ink-3)">
        از {{ dateTime(auth.user.telegram_linked_at) }}
      </span>
    </div>

    <ol style="margin: 0; padding-inline-start: 18px; color: var(--ink-2); font-size: 13px">
      <li>لینک اختصاصی و یک‌بارمصرف بگیرید (اعتبار ۱۰ دقیقه).</li>
      <li>روی آن بزنید تا تلگرام با دستور <code>/start</code> باز شود.</li>
      <li>پیام آزمایشی بفرستید تا از سالم بودن مسیر مطمئن شوید.</li>
    </ol>

    <div style="display: flex; gap: 8px; flex-wrap: wrap">
      <button class="btn" :disabled="busy" @click="createLink">گرفتن لینک اتصال</button>
      <a v-if="link" class="btn ghost" :href="link" target="_blank" rel="noopener">
        باز کردن ربات تلگرام
      </a>
      <button
        v-if="auth.user?.telegram_connected"
        class="btn ghost"
        :disabled="busy"
        @click="sendTest"
      >
        ارسال پیام آزمایشی
      </button>
      <button
        v-if="auth.user?.telegram_connected"
        class="btn danger"
        :disabled="busy"
        @click="disconnect"
      >
        قطع اتصال
      </button>
    </div>
    <span v-if="link" class="mono" style="font-size: 11.5px; color: var(--ink-3); direction: ltr">
      {{ link }}
    </span>
  </div>

  <div class="card" style="display: flex; flex-direction: column; gap: 14px">
    <h3 style="font-size: 15px">ساعت آرام</h3>
    <span style="font-size: 13px; color: var(--ink-2)">
      در این بازه هشدارها ثبت می‌شوند ولی پیام تلگرام تا پایان بازه صبر می‌کند. برای غیرفعال کردن،
      هر دو مقدار را خالی بگذارید.
    </span>
    <div style="display: flex; gap: 12px; max-width: 300px">
      <div class="field">
        <label>از ساعت</label>
        <input v-model.number="quietFrom" class="input" type="number" min="0" max="23" />
      </div>
      <div class="field">
        <label>تا ساعت</label>
        <input v-model.number="quietTo" class="input" type="number" min="0" max="23" />
      </div>
    </div>
    <span style="font-size: 12px; color: var(--ink-3)">
      منطقه زمانی حساب شما: <code>{{ auth.user?.timezone }}</code>
    </span>
    <button class="btn" style="align-self: flex-start" :disabled="busy" @click="saveQuiet">
      ذخیره
    </button>
  </div>

  <div class="card">
    <h3 style="font-size: 15px; margin-bottom: 8px">حساب</h3>
    <span class="mono" style="font-size: 12.5px; direction: ltr">{{ auth.user?.email }}</span>
    <p style="font-size: 12.5px; color: var(--ink-3); margin-top: 6px">
      ایمیل تنها برای تایید حساب و بازیابی رمز استفاده می‌شود؛ هشدارها فقط از تلگرام می‌آیند.
    </p>
  </div>
</template>
