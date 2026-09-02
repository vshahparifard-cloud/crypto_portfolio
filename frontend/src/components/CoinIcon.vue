<script setup lang="ts">
const props = defineProps<{ src?: string | null; symbol: string; size?: number }>()
const dimension = props.size ?? 22
</script>

<template>
  <img
    v-if="src"
    :src="src"
    :alt="symbol"
    :width="dimension"
    :height="dimension"
    style="border-radius: 50%; flex: none"
    loading="lazy"
  />
  <span
    v-else
    :style="{
      width: `${dimension}px`,
      height: `${dimension}px`,
      borderRadius: '50%',
      background: 'var(--surface-3)',
      color: 'var(--ink-2)',
      display: 'grid',
      placeItems: 'center',
      fontSize: `${Math.round(dimension * 0.42)}px`,
      fontWeight: 700,
      flex: 'none',
    }"
    >{{ symbol.slice(0, 2) }}</span
  >
</template>
