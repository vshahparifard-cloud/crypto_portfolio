<script setup lang="ts">
/**
 * ECharts price chart. Alert thresholds are drawn on the same canvas as amber
 * dashed lines, which is the whole reason this product needs a chart at all:
 * you should see how far the price is from your own targets.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Candle } from '../api/types'

echarts.use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps<{
  points: Candle[]
  thresholds?: { value: number; label: string }[]
  loading?: boolean
}>()

const host = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function render() {
  if (!chart) return
  const accent = cssVar('--accent') || '#2b50e0'
  const ink3 = cssVar('--ink-3') || '#7a8797'
  const line = cssVar('--line') || '#dce2e9'
  const signal = cssVar('--signal') || '#9c5a00'

  chart.setOption(
    {
      animation: false,
      grid: { top: 16, right: 16, bottom: 26, left: 62 },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => `$${value.toLocaleString('en-US')}`,
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: line } },
        axisLabel: { color: ink3, fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: line } },
        axisLabel: {
          color: ink3,
          fontSize: 10,
          fontFamily: 'IBM Plex Mono, monospace',
          formatter: (value: number) =>
            value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value),
        },
      },
      series: [
        {
          type: 'line',
          name: 'قیمت',
          showSymbol: false,
          smooth: false,
          lineStyle: { width: 1.8, color: accent },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${accent}38` },
              { offset: 1, color: `${accent}00` },
            ]),
          },
          data: props.points.map((candle) => [new Date(candle.ts).getTime(), Number(candle.close)]),
          markLine: {
            symbol: 'none',
            silent: true,
            lineStyle: { color: signal, type: 'dashed', width: 1.2 },
            label: { color: signal, fontSize: 10, formatter: '{b}' },
            data: (props.thresholds ?? []).map((item) => ({
              yAxis: item.value,
              name: item.label,
            })),
          },
        },
      ],
    },
    { notMerge: true },
  )
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  if (!host.value) return
  chart = echarts.init(host.value)
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.points, props.thresholds, props.loading],
  () => {
    // the canvas is kept in the DOM but hidden while empty, so it can measure
    // zero on first paint; resize before drawing
    chart?.resize()
    render()
  },
  { deep: true },
)
</script>

<template>
  <div class="chart-box">
    <div v-show="!loading && points.length" ref="host" class="chart"></div>
    <div v-if="loading" class="empty" style="height: 320px">در حال دریافت نمودار…</div>
    <div v-else-if="!points.length" class="empty" style="height: 320px">
      <span>هنوز داده نموداری برای این ارز ذخیره نشده است.</span>
      <span style="font-size: 12px"
        >تاریخچه پس از اولین اجرای <code>chart_backfill</code> پر می‌شود.</span
      >
    </div>
  </div>
</template>
