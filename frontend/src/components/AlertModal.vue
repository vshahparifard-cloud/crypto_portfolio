<script setup lang="ts">
import { computed, ref } from 'vue'
import { ApiError } from '../api/client'
import type { AlertKind, MarketRow } from '../api/types'
import { money } from '../format'
import { useAlerts } from '../stores/alerts'

const props = defineProps<{ coin: MarketRow }>()
const emit = defineEmits<{ close: []; created: [] }>()

const alerts = useAlerts()
const kind = ref<AlertKind>('price_above')
const threshold = ref('')
const windowMinutes = ref(15)
const cooldown = ref(60)
const oneShot = ref(false)
const error = ref<string | null>(null)
const saving = ref(false)

const isPct = computed(() => kind.value === 'pct_up' || kind.value === 'pct_down')
const currentPrice = computed(() => Number(props.coin.price_usd ?? 0))

const suggestion = computed(() => {
  if (isPct.value) return kind.value === 'pct_up' ? '5' : '5'
  const factor = kind.value === 'price_above' ? 1.05 : 0.95
  return currentPrice.value ? (currentPrice.value * factor).toFixed(2) : ''
})

function pick(next: AlertKind) {
  kind.value = next
  threshold.value = ''
  error.value = null
}

async function submit() {
  error.value = null
  const value = threshold.value.trim() || suggestion.value
  if (!value) {
    error.value = 'مقدار آستانه را وارد کنید'
    return
  }
  saving.value = true
  try {
    await alerts.create({
      coin_id: props.coin.coin_id,
      kind: kind.value,
      threshold: value,
      window_minutes: isPct.value ? windowMinutes.value : null,
      cooldown_minutes: cooldown.value,
      is_one_shot: oneShot.value,
    })
    emit('created')
    emit('close')
  } catch (exception) {
    error.value =
      exception instanceof ApiError ? exception.message : 'ثبت هشدار ناموفق بود'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-label="هشدار جدید">
      <h3>هشدار جدید — {{ coin.name }}</h3>

      <div class="field">
        <label>نوع شرط</label>
        <div class="seg">
          <button :class="{ on: kind === 'price_above' }" @click="pick('price_above')">
            حد بالا
          </button>
          <button :class="{ on: kind === 'price_below' }" @click="pick('price_below')">
            حد پایین
          </button>
          <button :class="{ on: kind === 'pct_down' }" @click="pick('pct_down')">ریزش %</button>
          <button :class="{ on: kind === 'pct_up' }" @click="pick('pct_up')">جهش %</button>
        </div>
      </div>

      <div class="field">
        <label v-if="!isPct">آستانه قیمت — قیمت فعلی {{ money(coin.price_usd) }}</label>
        <label v-else>درصد تغییر</label>
        <input v-model="threshold" class="input" :placeholder="suggestion" inputmode="decimal" />
        <span v-if="!isPct" class="hint">
          {{
            kind === 'price_above'
              ? 'باید بیشتر از قیمت فعلی باشد، وگرنه هیچ عبوری رخ نمی‌دهد.'
              : 'باید کمتر از قیمت فعلی باشد، وگرنه هیچ عبوری رخ نمی‌دهد.'
          }}
        </span>
      </div>

      <div v-if="isPct" class="field">
        <label>پنجره زمانی</label>
        <div class="seg">
          <button
            v-for="option in [15, 30, 60]"
            :key="option"
            :class="{ on: windowMinutes === option }"
            @click="windowMinutes = option"
          >
            {{ option }} دقیقه
          </button>
        </div>
        <span class="hint">نمونه‌گیری هر ۵ دقیقه است، پس کوتاه‌ترین پنجره ۱۵ دقیقه است.</span>
      </div>

      <div class="field">
        <label>مهلت سکوت بعد از فعال شدن (دقیقه)</label>
        <input v-model.number="cooldown" class="input" type="number" min="5" max="1440" />
      </div>

      <label class="switch" @click="oneShot = !oneShot">
        <span class="track" :class="{ on: oneShot }"><span class="knob"></span></span>
        بعد از اولین فعال‌شدن خودکار متوقف شود
      </label>

      <p v-if="error" class="notice error">{{ error }}</p>

      <div class="row">
        <button class="btn" style="flex: 1" :disabled="saving" @click="submit">
          {{ saving ? 'در حال ثبت…' : 'ثبت هشدار' }}
        </button>
        <button class="btn ghost" @click="emit('close')">انصراف</button>
      </div>
      <span class="hint">تاخیر تشخیص تا ۵ دقیقه است؛ پیام روی تلگرام شما می‌آید.</span>
    </div>
  </div>
</template>
