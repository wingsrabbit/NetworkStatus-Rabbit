<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, shallowRef, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  NCard, NSpace, NSelect, NStatistic, NGrid, NGi, NSpin, NPageHeader
} from 'naive-ui'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { getTaskData, getTaskStats } from '@/api/data'
import { useSocket } from '@/composables/useSocket'
import type { ProbeResult } from '@/types'

const route = useRoute()
const taskId = route.params.taskId as string
const { subscribeTask, unsubscribeTask, socket } = useSocket()

const chartRef = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts>()
const points = ref<ProbeResult[]>([])
const stats = ref<Record<string, any>>({})
const loading = ref(false)
const range = ref('30m')

const rangeOptions = [
  { label: '30 分钟', value: '30m' },
  { label: '1 小时', value: '1h' },
  { label: '6 小时', value: '6h' },
  { label: '24 小时', value: '24h' },
  { label: '7 天', value: '7d' },
  { label: '30 天', value: '30d' },
]

/** 是否使用 raw 粒度（允许实时追加） */
const isRawRange = computed(() => ['30m', '1h', '6h', '24h'].includes(range.value))

/** 统一格式化：两位小数 */
function fmt(val: number | null | undefined): string {
  if (val == null) return '-'
  return val.toFixed(2)
}


/** 从当前 points 重算统计值 */
function recalcStats() {
  const pts = points.value
  if (!pts.length) return

  const latencies = pts.map(p => p.latency).filter((v): v is number => v != null)
  const losses = pts.map(p => p.packet_loss).filter((v): v is number => v != null)
  const total = pts.length

  if (latencies.length) {
    const sorted = [...latencies].sort((a, b) => a - b)
    const p95Idx = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1)
    stats.value = {
      ...stats.value,
      avg_latency: sorted.reduce((a, b) => a + b, 0) / sorted.length,
      p95_latency: sorted[p95Idx],
      avg_packet_loss: losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : stats.value.avg_packet_loss,
      total_probes: total,
    }
  }
}

/** 将 range 字符串转为毫秒数 */
function rangeToMs(r: string): number {
  if (r.endsWith('m')) return parseInt(r) * 60 * 1000
  if (r.endsWith('h')) return parseInt(r) * 3600 * 1000
  if (r.endsWith('d')) return parseInt(r) * 86400 * 1000
  return 30 * 60 * 1000
}

/** 长周期视图定时刷新间隔（ms）：7d=60s, 30d=300s */
function refreshInterval(r: string): number | null {
  if (r === '7d') return 60_000
  if (r === '30d') return 300_000
  return null
}

let _refreshTimer: ReturnType<typeof setInterval> | null = null

function startAutoRefresh() {
  stopAutoRefresh()
  const interval = refreshInterval(range.value)
  if (interval) {
    _refreshTimer = setInterval(() => fetchData(), interval)
  }
}

function stopAutoRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null }
}

async function fetchData() {
  loading.value = true
  try {
    const [dataRes, statsRes] = await Promise.all([
      getTaskData(taskId, { range: range.value }),
      getTaskStats(taskId, { range: range.value }),
    ])
    points.value = dataRes.data.data
    stats.value = statsRes.data.stats
    updateChart()
    // 通知全局状态栏收到新数据
    ;(window as any).__nsr_markDataReceived?.()
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chart.value) return

  const latencies = points.value.map((p) => [p.timestamp, p.latency])
  const losses = points.value.map((p) => [p.timestamp, p.packet_loss])
  const jitters = points.value.map((p) => [p.timestamp, p.jitter])

  const series: any[] = [
    {
      name: '延迟 (ms)',
      type: 'line',
      data: latencies,
      smooth: true,
      showSymbol: false,
      itemStyle: { color: '#18a058' },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(24,160,88,0.3)' },
        { offset: 1, color: 'rgba(24,160,88,0.02)' },
      ])},
    },
  ]

  const rawLosses = points.value.map((p) => p.packet_loss)
  const hasLoss = rawLosses.some((v) => v != null && v > 0)
  if (hasLoss) {
    series.push({
      name: '丢包率 (%)',
      type: 'bar',
      data: losses,
      yAxisIndex: 1,
      itemStyle: { color: '#d03050' },
      barWidth: 4,
    })
  }

  const rawJitters = points.value.map((p) => p.jitter)
  const hasJitter = rawJitters.some((v) => v != null)
  if (hasJitter) {
    series.push({
      name: '抖动 (ms)',
      type: 'line',
      data: jitters,
      smooth: true,
      showSymbol: false,
      lineStyle: { type: 'dashed' },
      itemStyle: { color: '#f0a020' },
    })
  }

  const yAxis: any[] = [
    { type: 'value', name: 'ms', min: 0 },
  ]
  if (hasLoss) {
    yAxis.push({ type: 'value', name: '%', min: 0, max: 100, splitLine: { show: false } })
  }

  // 固定时间轴窗口：max = 当前时间, min = 当前时间 - 选定范围
  const now = Date.now()
  const windowMs = rangeToMs(range.value)

  const xAxisLabelFormat = (() => {
    switch (range.value) {
      case '30m': case '1h': case '6h': return '{HH}:{mm}:{ss}'
      case '24h': return '{HH}:{mm}'
      case '7d': case '30d': return '{MM}-{dd} {HH}:{mm}'
      default: return '{HH}:{mm}:{ss}'
    }
  })()

  chart.value.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!Array.isArray(params) || !params.length) return ''
        const time = dayjs(params[0].value[0]).format(
          range.value === '30d' || range.value === '7d' ? 'MM-DD HH:mm' :
          range.value === '24h' ? 'HH:mm' : 'HH:mm:ss'
        )
        let html = `${time}<br/>`
        for (const p of params) {
          const unit = p.seriesName.includes('%') ? '%' : ' ms'
          const val = p.value[1] != null ? Number(p.value[1]).toFixed(2) : '-'
          html += `${p.marker} ${p.seriesName}: ${val}${unit}<br/>`
        }
        return html
      },
    },
    legend: { bottom: 0 },
    grid: { left: 60, right: hasLoss ? 60 : 30, top: 30, bottom: 40 },
    xAxis: {
      type: 'time',
      min: now - windowMs,
      max: now,
      axisLabel: { formatter: xAxisLabelFormat },
      boundaryGap: false,
    },
    yAxis,
    series,
  }, true)
}

function handleRealtimeUpdate(data: any) {
  if (data.task_id !== taskId) return
  const result = data.result as ProbeResult
  if (!result) return
  // 仅 raw 粒度范围允许实时追加，7d/30d 聚合视图不追加秒级点
  if (!isRawRange.value) return
  points.value.push(result)
  if (points.value.length > 500) points.value.shift()
  recalcStats()
  updateChart()
  ;(window as any).__nsr_markDataReceived?.()
}

onMounted(() => {
  if (chartRef.value) {
    chart.value = echarts.init(chartRef.value)
    window.addEventListener('resize', () => chart.value?.resize())
  }
  fetchData()
  startAutoRefresh()
  subscribeTask(taskId)
  socket.value?.on('dashboard_task_detail', handleRealtimeUpdate)
})

onUnmounted(() => {
  stopAutoRefresh()
  unsubscribeTask(taskId)
  socket.value?.off('dashboard_task_detail', handleRealtimeUpdate)
  chart.value?.dispose()
})

watch(range, () => {
  fetchData()
  startAutoRefresh()
})
</script>

<template>
  <div>
    <NPageHeader @back="$router.back()" title="任务详情" />
    <NSpace style="margin: 16px 0" align="center">
      <NSelect v-model:value="range" :options="rangeOptions" style="width: 140px" />
    </NSpace>

    <NGrid :x-gap="16" :y-gap="16" cols="2 m:4" responsive="screen" style="margin-bottom: 16px">
      <NGi>
        <NCard>
          <NStatistic label="平均延迟" :value="stats.avg_latency != null ? `${fmt(stats.avg_latency)} ms` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="P95 延迟" :value="stats.p95_latency != null ? `${fmt(stats.p95_latency)} ms` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="平均丢包" :value="stats.avg_packet_loss != null ? `${fmt(stats.avg_packet_loss)}%` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="数据点数" :value="stats.total_probes ?? '-'" />
        </NCard>
      </NGi>
    </NGrid>

    <NCard>
      <NSpin :show="loading">
        <div ref="chartRef" style="width: 100%; height: 400px"></div>
      </NSpin>
    </NCard>
  </div>
</template>
