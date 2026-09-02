<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertModal from '../components/AlertModal.vue'
import CoinIcon from '../components/CoinIcon.vue'
import HoldingModal from '../components/HoldingModal.vue'
import PriceChart from '../components/PriceChart.vue'
import type { Candle, ChartRange, MarketRow } from '../api/types'
import { ago, compactMoney, money, percent, signClass } from '../format'
import { useAlerts } from '../stores/alerts'
import { useAuth } from '../stores/auth'
import { useMarket } from '../stores/market'
import { usePortfolio } from '../stores/portfolio'

const route = useRoute()
const router = useRouter()
const market = useMarket()
const alerts = useAlerts()
const portfolio = usePortfolio()
const auth = useAuth()

const coinId = computed(() => String(route.params.id))
const coin = ref<MarketRow | null>(null)
const points = ref<Candle[]>([])
const range = ref<ChartRange>('7d')
const loadingChart = ref(true)
const showAlert = ref(false)
const showHolding = ref(false)
const error = ref<string | null>(null)

const ranges: ChartRange[] = ['24h', '7d', '30d', '90d', '1y']

const thresholds = computed(() =>
  alerts
    .forCoin(coinId.value)
    .filter((alert) => alert.kind === 'price_above' || alert.kind === 'price_below')
    .map((alert) => ({
      value: Number(alert.threshold),
      label: `${alert.kind === 'price_above' ? 'حد سود' : 'حد ضرر'} ${Number(
        alert.threshold,
      ).toLocaleString('en-US')}`,
    })),
)

const holding = computed(() =>
  portfolio.holdings.find((item) => item.coin_id === coinId.value) ?? null,
)

async function loadChart() {
  loadingChart.value = true
  try {
    const chart = await market.chart(coinId.value, range.value)
    points.value = chart.points
  } finally {
    loadingChart.value = false
  }
}

async function loadAll() {
  error.value = null
  try {
    coin.value = await market.coin(coinId.value)
  } catch {
    error.value = 'این ارز پیدا نشد یا هنوز پایش نمی‌شود.'
    return
  }
  await loadChart()
  if (auth.isAuthenticated) {
    await Promise.all([alerts.load(), portfolio.load()])
  }
}

function requireAuth(action: 'alert' | 'holding') {
  if (!auth.isAuthenticated) {
    void router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  if (action === 'alert') showAlert.value = true
  else showHolding.value = true
}

onMounted(loadAll)
watch(range, loadChart)
watch(coinId, loadAll)
</script>

<template>
  <p v-if="error" class="notice error">{{ error }}</p>

  <template v-if="coin">
    <div class="bar">
      <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap">
        <span class="coin-cell">
          <CoinIcon :src="coin.image_url" :symbol="coin.symbol" :size="30" />
          <b style="font-size: 17px">{{ coin.name }}</b>
          <span class="sym">{{ coin.symbol }} · رتبه {{ coin.market_cap_rank ?? '—' }}</span>
        </span>
        <span class="num" style="font-size: 18px; font-weight: 600">{{ money(coin.price_usd) }}</span>
        <span class="pill" :class="Number(coin.pct_change_24h) >= 0 ? 'on' : 'off'">
          {{ percent(coin.pct_change_24h) }} · ۲۴ ساعت
        </span>
        <span style="font-size: 12px; color: var(--ink-3)">نمونه {{ ago(coin.sampled_at) }}</span>
      </div>
      <div style="display: flex; gap: 8px">
        <button class="btn ghost" @click="requireAuth('holding')">
          {{ holding ? 'ویرایش دارایی' : 'افزودن به سبد' }}
        </button>
        <button class="btn" @click="requireAuth('alert')">ساخت هشدار</button>
      </div>
    </div>

    <div class="bar">
      <div class="ranges">
        <button
          v-for="option in ranges"
          :key="option"
          :class="{ on: range === option }"
          @click="range = option"
        >
          {{ option }}
        </button>
      </div>
      <span v-if="thresholds.length" style="font-size: 11.5px; color: var(--signal)">
        خط‌چین کهربایی = آستانه‌های هشدار شما
      </span>
    </div>

    <PriceChart :points="points" :thresholds="thresholds" :loading="loadingChart" />

    <div class="tiles">
      <div class="tile">
        <span class="label">ارزش بازار</span>
        <span class="value num">{{ compactMoney(coin.market_cap) }}</span>
      </div>
      <div class="tile">
        <span class="label">حجم ۲۴ ساعت</span>
        <span class="value num">{{ compactMoney(coin.volume_24h) }}</span>
      </div>
      <div class="tile">
        <span class="label">هشدارهای این ارز</span>
        <span class="value num">{{ alerts.forCoin(coinId).length }}</span>
        <span class="sub" style="color: var(--ink-3)">
          {{ thresholds.length ? 'روی نمودار رسم شده' : 'هنوز هشداری ندارید' }}
        </span>
      </div>
      <div class="tile">
        <span class="label">دارایی شما</span>
        <span class="value num">{{ holding ? holding.quantity : '—' }}</span>
        <span v-if="holding" class="sub num" :class="signClass(holding.pnl_usd)">
          {{ money(holding.value_usd) }} · {{ percent(holding.pnl_pct) }}
        </span>
      </div>
    </div>

    <AlertModal
      v-if="showAlert"
      :coin="coin"
      @close="showAlert = false"
      @created="alerts.load()"
    />
    <HoldingModal
      v-if="showHolding"
      :coin="coin"
      :holding="holding"
      @close="showHolding = false"
      @saved="portfolio.load()"
    />
  </template>
</template>
