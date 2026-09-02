<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CoinIcon from '../components/CoinIcon.vue'
import HoldingModal from '../components/HoldingModal.vue'
import type { Holding } from '../api/types'
import { money, percent, quantity, signClass } from '../format'
import { usePortfolio } from '../stores/portfolio'

const portfolio = usePortfolio()
const router = useRouter()
const editing = ref<Holding | null>(null)

onMounted(() => portfolio.load())

const donut = computed(() => {
  const palette = ['#f7931a', '#627eea', '#00a3ff', '#f0b90b', '#8247e5', '#7a8797']
  let offset = 25
  return (portfolio.summary?.allocation ?? []).slice(0, 6).map((slice, index) => {
    const share = Number(slice.share_pct)
    const segment = {
      symbol: slice.symbol,
      share,
      color: palette[index % palette.length],
      dash: `${share} ${100 - share}`,
      offset,
    }
    offset -= share
    return segment
  })
})

async function remove(holding: Holding) {
  if (!confirm(`${holding.symbol} از سبد حذف شود؟`)) return
  await portfolio.remove(holding.id)
}
</script>

<template>
  <div class="bar">
    <span class="page-title">سبد من</span>
    <button class="btn" @click="router.push({ name: 'market' })">افزودن دارایی از بازار</button>
  </div>

  <div v-if="portfolio.summary" class="tiles">
    <div class="tile">
      <span class="label">ارزش کل</span>
      <span class="value num">{{ money(portfolio.summary.total_value_usd) }}</span>
      <span class="sub num" :class="signClass(portfolio.summary.change_24h_usd)">
        {{ money(portfolio.summary.change_24h_usd) }} در ۲۴ ساعت
      </span>
    </div>
    <div class="tile">
      <span class="label">سود / زیان کل</span>
      <span class="value num" :class="signClass(portfolio.summary.pnl_usd)">
        {{ money(portfolio.summary.pnl_usd) }}
      </span>
      <span class="sub num" :class="signClass(portfolio.summary.pnl_pct)">
        {{ percent(portfolio.summary.pnl_pct) }}
      </span>
    </div>
    <div class="tile">
      <span class="label">بهای تمام‌شده</span>
      <span class="value num">{{ money(portfolio.summary.total_cost_usd) }}</span>
      <span class="sub" style="color: var(--ink-3)"
        >{{ portfolio.summary.holdings_count }} دارایی</span
      >
    </div>
    <div class="tile" style="flex-direction: row; align-items: center; gap: 14px">
      <svg v-if="donut.length" width="62" height="62" viewBox="0 0 42 42" role="img" aria-label="سهم هر ارز از سبد">
        <circle
          v-for="segment in donut"
          :key="segment.symbol"
          cx="21"
          cy="21"
          r="15.9"
          fill="none"
          :stroke="segment.color"
          stroke-width="7"
          :stroke-dasharray="segment.dash"
          :stroke-dashoffset="segment.offset"
        />
      </svg>
      <div style="display: flex; flex-direction: column; gap: 2px; font-size: 11.5px">
        <span v-for="segment in donut" :key="segment.symbol" style="color: var(--ink-2)">
          <span :style="{ color: segment.color }">●</span> {{ segment.symbol }}
          {{ segment.share.toFixed(1) }}٪
        </span>
      </div>
    </div>
  </div>

  <div v-if="portfolio.holdings.length" class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ارز</th>
          <th class="n">مقدار</th>
          <th class="n">میانگین خرید</th>
          <th class="n">قیمت روز</th>
          <th class="n">ارزش</th>
          <th class="n">سود / زیان</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="holding in portfolio.holdings" :key="holding.id">
          <td>
            <RouterLink
              class="coin-cell"
              :to="{ name: 'coin', params: { id: holding.coin_id } }"
              style="color: inherit"
            >
              <CoinIcon :src="holding.image_url" :symbol="holding.symbol" />
              <b>{{ holding.symbol }}</b>
              <span class="sym">{{ holding.name }}</span>
            </RouterLink>
          </td>
          <td class="n">{{ quantity(holding.quantity) }}</td>
          <td class="n">{{ money(holding.avg_buy_price) }}</td>
          <td class="n">{{ money(holding.price_usd) }}</td>
          <td class="n">{{ money(holding.value_usd) }}</td>
          <td class="n" :class="signClass(holding.pnl_usd)">
            {{ money(holding.pnl_usd) }} · {{ percent(holding.pnl_pct) }}
          </td>
          <td>
            <div style="display: flex; gap: 6px; justify-content: flex-end">
              <button class="btn ghost small" @click="editing = holding">ویرایش</button>
              <button class="btn danger small" @click="remove(holding)">حذف</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-else-if="!portfolio.loading" class="card">
    <div class="empty">
      <span>سبد شما خالی است.</span>
      <span style="font-size: 12.5px"
        >از صفحه بازار روی یک ارز بزنید و «افزودن به سبد» را انتخاب کنید.</span
      >
      <button class="btn" @click="router.push({ name: 'market' })">رفتن به بازار</button>
    </div>
  </div>

  <HoldingModal
    v-if="editing"
    :holding="editing"
    @close="editing = null"
    @saved="portfolio.load()"
  />
</template>
