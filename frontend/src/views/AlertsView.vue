<script setup lang="ts">
import { onMounted } from 'vue'
import CoinIcon from '../components/CoinIcon.vue'
import type { Alert } from '../api/types'
import {
  DELIVERY_LABELS,
  KIND_LABELS,
  STATUS_LABELS,
  dateTime,
  money,
  percent,
  signClass,
} from '../format'
import { useAlerts } from '../stores/alerts'
import { useAuth } from '../stores/auth'

const alerts = useAlerts()
const auth = useAuth()

onMounted(() => alerts.load())

function pillClass(status: Alert['status']): string {
  if (status === 'active') return 'pill on'
  if (status === 'cooling') return 'pill fire'
  return 'pill off'
}

function thresholdLabel(alert: Alert): string {
  return alert.kind === 'pct_up' || alert.kind === 'pct_down'
    ? `${alert.kind === 'pct_down' ? '−' : '+'}${Number(alert.threshold)}% / ${alert.window_minutes}د`
    : money(alert.threshold)
}

function distance(alert: Alert): string {
  if (!alert.current_price || alert.kind === 'pct_up' || alert.kind === 'pct_down') return '—'
  const current = Number(alert.current_price)
  const target = Number(alert.threshold)
  if (!current) return '—'
  return percent(((target - current) / current) * 100, 1)
}

async function remove(alert: Alert) {
  if (!confirm('این هشدار حذف شود؟')) return
  await alerts.remove(alert.id)
}
</script>

<template>
  <div class="bar">
    <span class="page-title">
      هشدارهای من
      <span style="font-size: 12.5px; font-weight: 400; color: var(--ink-3)">
        {{ alerts.activeCount }} فعال
      </span>
    </span>
    <RouterLink class="btn" :to="{ name: 'market' }">هشدار جدید از صفحه بازار</RouterLink>
  </div>

  <p v-if="auth.user && !auth.user.telegram_connected" class="notice warn">
    تلگرام شما وصل نیست، پس هشدارها جایی برای ارسال ندارند.
    <RouterLink :to="{ name: 'settings' }">اتصال تلگرام</RouterLink>
  </p>

  <div v-if="alerts.alerts.length" class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ارز</th>
          <th>شرط</th>
          <th class="n">آستانه</th>
          <th class="n">قیمت فعلی</th>
          <th class="n">فاصله تا هدف</th>
          <th>وضعیت</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="alert in alerts.alerts" :key="alert.id">
          <td>
            <RouterLink
              class="coin-cell"
              :to="{ name: 'coin', params: { id: alert.coin_id } }"
              style="color: inherit"
            >
              <CoinIcon :src="alert.image_url" :symbol="alert.symbol" />
              <b>{{ alert.symbol }}</b>
            </RouterLink>
          </td>
          <td>{{ KIND_LABELS[alert.kind] }}</td>
          <td class="n">{{ thresholdLabel(alert) }}</td>
          <td class="n">{{ money(alert.current_price) }}</td>
          <td class="n" :class="signClass(distance(alert).replace('−', '-').replace('+', ''))">
            {{ distance(alert) }}
          </td>
          <td>
            <span :class="pillClass(alert.status)">{{ STATUS_LABELS[alert.status] }}</span>
            <span v-if="alert.is_one_shot" class="pill off" style="margin-inline-start: 4px"
              >یک‌بارمصرف</span
            >
          </td>
          <td>
            <div style="display: flex; gap: 6px; justify-content: flex-end">
              <button
                v-if="alert.status === 'paused'"
                class="btn ghost small"
                @click="alerts.setStatus(alert.id, 'active')"
              >
                فعال‌سازی
              </button>
              <button
                v-else
                class="btn ghost small"
                @click="alerts.setStatus(alert.id, 'paused')"
              >
                توقف
              </button>
              <button class="btn danger small" @click="remove(alert)">حذف</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-else-if="!alerts.loading" class="card">
    <div class="empty">
      <span>هنوز هشداری نساخته‌اید.</span>
      <span style="font-size: 12.5px"
        >در صفحه بازار روی آیکن زنگ هر ارز بزنید تا هشدار حد سود یا حد ضرر بسازید.</span
      >
      <RouterLink class="btn" :to="{ name: 'market' }">رفتن به بازار</RouterLink>
    </div>
  </div>

  <h3 style="margin-top: 10px; font-size: 15px">تاریخچه فعال‌شدن‌ها</h3>
  <div v-if="alerts.events.length" class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ارز</th>
          <th>شرط</th>
          <th class="n">قیمت در لحظه هشدار</th>
          <th>زمان</th>
          <th>تحویل</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in alerts.events" :key="event.id">
          <td><b>{{ event.symbol }}</b></td>
          <td>{{ KIND_LABELS[event.kind] }} {{ event.threshold }}</td>
          <td class="n">{{ money(event.price_at_trigger) }}</td>
          <td>{{ dateTime(event.triggered_at) }}</td>
          <td>
            <span
              class="pill"
              :class="
                event.delivery_state === 'sent'
                  ? 'on'
                  : event.delivery_state === 'dead'
                    ? 'off'
                    : 'fire'
              "
            >
              {{ DELIVERY_LABELS[event.delivery_state] }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <p v-else class="notice">هنوز هیچ هشداری فعال نشده است.</p>
</template>
