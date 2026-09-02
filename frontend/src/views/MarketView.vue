<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AlertModal from '../components/AlertModal.vue'
import CoinIcon from '../components/CoinIcon.vue'
import Sparkline from '../components/Sparkline.vue'
import type { MarketRow } from '../api/types'
import { ago, compactMoney, money, percent, signClass } from '../format'
import { useAlerts } from '../stores/alerts'
import { useAuth } from '../stores/auth'
import { useMarket } from '../stores/market'

const market = useMarket()
const alerts = useAlerts()
const auth = useAuth()
const router = useRouter()
const alertTarget = ref<MarketRow | null>(null)

const freshness = computed(() => ago(market.lastSampledAt))
const armedCoins = computed(
  () => new Set(alerts.alerts.filter((alert) => alert.status !== 'expired').map((a) => a.coin_id)),
)

onMounted(async () => {
  await market.load(50)
  market.connect()
  if (auth.isAuthenticated) await alerts.load()
})

onUnmounted(() => market.disconnect())

function openCoin(coinId: string) {
  void router.push({ name: 'coin', params: { id: coinId } })
}

function requestAlert(row: MarketRow) {
  if (!auth.isAuthenticated) {
    void router.push({ name: 'login', query: { next: '/market' } })
    return
  }
  alertTarget.value = row
}
</script>

<template>
  <div class="bar">
    <span class="page-title">بازار ارزهای دیجیتال</span>
    <input v-model="market.query" class="input rtl" style="max-width: 240px" placeholder="جستجوی نام یا نماد…" />
    <span class="pill on"><span class="dot"></span>قیمت {{ freshness }} · تازه‌سازی هر ۵ دقیقه</span>
  </div>

  <p v-if="market.error" class="notice error">{{ market.error }}</p>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>ارز</th>
          <th class="n">قیمت</th>
          <th class="n">۲۴ ساعت</th>
          <th class="n">۷ روز</th>
          <th class="n">ارزش بازار</th>
          <th class="n">حجم ۲۴ ساعت</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="market.loading && !market.rows.length">
          <td colspan="8" style="text-align: center; color: var(--ink-3)">در حال دریافت…</td>
        </tr>
        <tr
          v-for="row in market.visibleRows"
          :key="row.coin_id"
          class="clickable"
          @click="openCoin(row.coin_id)"
        >
          <td class="n">{{ row.market_cap_rank ?? '—' }}</td>
          <td>
            <span class="coin-cell">
              <CoinIcon :src="row.image_url" :symbol="row.symbol" />
              <b>{{ row.name }}</b>
              <span class="sym">{{ row.symbol }}</span>
            </span>
          </td>
          <td class="n">{{ money(row.price_usd) }}</td>
          <td class="n" :class="signClass(row.pct_change_24h)">{{ percent(row.pct_change_24h) }}</td>
          <td><Sparkline :points="row.sparkline_7d" /></td>
          <td class="n">{{ compactMoney(row.market_cap) }}</td>
          <td class="n">{{ compactMoney(row.volume_24h) }}</td>
          <td @click.stop>
            <button
              class="icon-btn"
              :class="{ armed: armedCoins.has(row.coin_id) }"
              :title="armedCoins.has(row.coin_id) ? 'هشدار فعال دارید' : 'ساخت هشدار'"
              @click="requestAlert(row)"
            >
              ◔
            </button>
          </td>
        </tr>
        <tr v-if="!market.loading && !market.visibleRows.length">
          <td colspan="8">
            <div class="empty">
              <span>چیزی پیدا نشد.</span>
              <button class="btn ghost small" @click="market.query = ''">پاک کردن جستجو</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <span style="font-size: 12px; color: var(--ink-3)">
    قیمت‌ها هر ۵ دقیقه از CoinGecko نمونه‌گیری می‌شوند؛ عدد کنار هر ردیف سن همان نمونه است، نه لحظه‌ای.
  </span>

  <AlertModal
    v-if="alertTarget"
    :coin="alertTarget"
    @close="alertTarget = null"
    @created="alerts.load()"
  />
</template>
