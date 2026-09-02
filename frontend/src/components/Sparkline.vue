<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ points: number[] | null; width?: number; height?: number }>()
const w = props.width ?? 68
const h = props.height ?? 20

const path = computed(() => {
  const values = props.points ?? []
  if (values.length < 2) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * w
      const y = h - ((value - min) / span) * (h - 2) - 1
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const rising = computed(() => {
  const values = props.points ?? []
  return values.length > 1 && values[values.length - 1] >= values[0]
})
</script>

<template>
  <svg v-if="path" :width="w" :height="h" :viewBox="`0 0 ${w} ${h}`" aria-hidden="true">
    <polyline
      :points="path"
      fill="none"
      :stroke="rising ? 'var(--up)' : 'var(--down)'"
      stroke-width="1.5"
    />
  </svg>
  <span v-else style="color: var(--ink-3)">—</span>
</template>
