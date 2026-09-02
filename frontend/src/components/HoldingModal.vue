<script setup lang="ts">
import { ref } from 'vue'
import { ApiError } from '../api/client'
import type { Holding, MarketRow } from '../api/types'
import { usePortfolio } from '../stores/portfolio'

const props = defineProps<{ coin?: MarketRow | null; holding?: Holding | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const portfolio = usePortfolio()
const quantity = ref(props.holding?.quantity ?? '')
const price = ref(props.holding?.avg_buy_price ?? props.coin?.price_usd ?? '')
const error = ref<string | null>(null)
const saving = ref(false)

async function submit() {
  error.value = null
  if (!quantity.value || Number(quantity.value) <= 0) {
    error.value = 'مقدار باید بزرگ‌تر از صفر باشد'
    return
  }
  saving.value = true
  try {
    if (props.holding) {
      await portfolio.update(props.holding.id, {
        quantity: quantity.value,
        avg_buy_price: price.value || '0',
      })
    } else if (props.coin) {
      await portfolio.add({
        coin_id: props.coin.coin_id,
        quantity: quantity.value,
        avg_buy_price: price.value || '0',
      })
    }
    emit('saved')
    emit('close')
  } catch (exception) {
    error.value = exception instanceof ApiError ? exception.message : 'ذخیره ناموفق بود'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-label="دارایی">
      <h3>
        {{ holding ? `ویرایش ${holding.symbol}` : `افزودن ${coin?.name ?? ''} به سبد` }}
      </h3>
      <div class="field">
        <label>مقدار</label>
        <input v-model="quantity" class="input" inputmode="decimal" placeholder="0.412" />
      </div>
      <div class="field">
        <label>میانگین قیمت خرید (دلار)</label>
        <input v-model="price" class="input" inputmode="decimal" placeholder="88900" />
        <span class="hint">برای محاسبه سود و زیان استفاده می‌شود.</span>
      </div>
      <p v-if="error" class="notice error">{{ error }}</p>
      <div class="row">
        <button class="btn" style="flex: 1" :disabled="saving" @click="submit">
          {{ saving ? 'در حال ذخیره…' : 'ذخیره' }}
        </button>
        <button class="btn ghost" @click="emit('close')">انصراف</button>
      </div>
    </div>
  </div>
</template>
