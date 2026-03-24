<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, shallowRef, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  NCard, NSpace, NSelect, NStatistic, NGrid, NGi, NSpin, NPageHeader, NButton, NTooltip
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
  { label: '3 天', value: '3d' },
  { label: '7 天', value: '7d' },
  { label: '14 天', value: '14d' },
  { label: '30 天', value: '30d' },
]

/** 是否使用 raw 粒度（允许实时追加） */
const isRawRange = computed(() => ['30m', '1h', '6h', '24h'].includes(range.value))

/** 是否处于局部缩放状态 */
const isZoomed = ref(false)

/** 缩放态下保存的当前可见区间百分比 */
const zoomStart = ref(0)
const zoomEnd = ref(100)

/** 安全尾巴（毫秒），基于任务 timeout，从 stats 返回 */
const tailMarginMs = computed(() => {
  const timeout = stats.value.timeout_seconds
  return (timeout != null ? timeout : 10) * 1000
})

/** 统一格式化：两位小数 */
function fmt(val: number | null | undefined): string {
  if (val == null) return '-'
  return val.toFixed(2)
}

/**
 * 基于最近 N 个 latency 点计算窗口抖动（标准差）。
 * 对每个点 i，取 [i-WINDOW+1, i] 范围内的有效 latency 计算 stdev。
 * 返回与 points 等长的数组，不足窗口大小的位置为 null。
 */
const JITTER_WINDOW = 10

function computeWindowJitter(pts: ProbeResult[]): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < pts.length; i++) {
    if (i < JITTER_WINDOW - 1) {
      result.push(null)
      continue
    }
    const window: number[] = []
    for (let j = i - JITTER_WINDOW + 1; j <= i; j++) {
      const lat = pts[j].latency
      if (lat != null) window.push(lat)
    }
    if (window.length < 2) {
      result.push(null)
      continue
    }
    const mean = window.reduce((a, b) => a + b, 0) / window.length
    const variance = window.reduce((a, b) => a + (b - mean) ** 2, 0) / window.length
    result.push(Math.sqrt(variance))
  }
  return result
}

/** 全部点的平均窗口抖动（用于统计卡） */
const avgWindowJitter = computed(() => {
  const jitterVals = computeWindowJitter(points.value).filter((v): v is number => v != null)
  if (jitterVals.length === 0) return null
  return jitterVals.reduce((a, b) => a + b, 0) / jitterVals.length
})

/** 数据点数展示文案 */
const dataPointLabel = computed(() => {
  const s = stats.value
  if (s.total_probes == null) return '-'
  if (s.expected_probes != null) {
    const label = s.bucket_type === 'raw' ? '原始样本' : (s.bucket_type === '1m' ? '分钟桶' : '小时桶')
    return `${s.total_probes} / ${s.expected_probes}`
  }
  return String(s.total_probes)
})

const dataPointTooltip = computed(() => {
  const s = stats.value
  if (s.expected_probes == null) return ''
  const label = s.bucket_type === 'raw' ? '原始样本' : (s.bucket_type === '1m' ? '分钟级聚合桶' : '小时级聚合桶')
  return `${label}：实际 ${s.total_probes} / 理论 ${s.expected_probes}`
})

/** 将 range 字符串转为毫秒数 */
function rangeToMs(r: string): number {
  if (r.endsWith('m')) return parseInt(r) * 60 * 1000
  if (r.endsWith('h')) return parseInt(r) * 3600 * 1000
  if (r.endsWith('d')) return parseInt(r) * 86400 * 1000
  return 30 * 60 * 1000
}

/**
 * 定时刷新间隔，按 Project 规格对齐：
 * 30m~24h: 秒级 (5s)
 * 3d~7d:   分钟级 (60s)
 * 14d~30d: 每 5 分钟 (300s)
 */
function refreshInterval(r: string): number {
  if (['30m', '1h', '6h', '24h'].includes(r)) return 5_000
  if (['3d', '7d'].includes(r)) return 60_000
  if (['14d', '30d'].includes(r)) return 300_000
  return 5_000
}

let _refreshTimer: ReturnType<typeof setInterval> | null = null

function startAutoRefresh() {
  stopAutoRefresh()
  const interval = refreshInterval(range.value)
  _refreshTimer = setInterval(() => fetchData(), interval)
}

function stopAutoRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null }
}

/** 图表是否已完成首次初始化 */
let _chartInitialized = false

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
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chart.value) return

  const latencies = points.value.map((p) => [p.timestamp, p.latency])
  const losses = points.value.map((p) => [p.timestamp, p.packet_loss])

  // jitter：优先使用后端返回值，若全为 null 则回退到前端 10 点窗口计算
  const backendJitters = points.value.map((p) => p.jitter)
  const hasBackendJitter = backendJitters.some((v) => v != null)
  let jitters: [any, number | null][]
  if (hasBackendJitter) {
    jitters = points.value.map((p) => [p.timestamp, p.jitter])
  } else {
    const windowJitters = computeWindowJitter(points.value)
    jitters = points.value.map((p, i) => [p.timestamp, windowJitters[i]])
  }

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

  const hasJitter = jitters.some(([, v]) => v != null)
  if (hasJitter) {
    series.push({
      name: '窗口抖动 (ms)',
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

  // 安全尾巴：右边界 = now - tailMargin，避免尚未完成的探测被当作掉点
  const now = Date.now()
  const windowMs = rangeToMs(range.value)
  const effectiveEnd = now - tailMarginMs.value
  const effectiveStart = effectiveEnd - windowMs

  const xAxisLabelFormat = (() => {
    switch (range.value) {
      case '30m': case '1h': case '6h': return '{HH}:{mm}:{ss}'
      case '24h': return '{HH}:{mm}'
      case '3d': case '7d': case '14d': case '30d': return '{MM}-{dd} {HH}:{mm}'
      default: return '{HH}:{mm}:{ss}'
    }
  })()

  const tooltipFormat = (() => {
    switch (range.value) {
      case '30m': case '1h': case '6h': return 'HH:mm:ss'
      case '24h': return 'HH:mm'
      case '3d': case '7d': case '14d': case '30d': return 'MM-DD HH:mm'
      default: return 'HH:mm:ss'
    }
  })()

  if (isZoomed.value && _chartInitialized) {
    // 缩放态：只更新数据序列，不覆盖 xAxis 和 dataZoom
    chart.value.setOption({ series })
  } else {
    // 非缩放态或首次：完整设置
    const option: any = {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params.length) return ''
          const time = dayjs(params[0].value[0]).format(tooltipFormat)
          let html = `${time}<br/>`
          for (const p of params) {
            const unit = p.seriesName.includes('%') ? '%' : ' ms'
            const val = p.value[1] != null ? Number(p.value[1]).toFixed(2) : '-'
            html += `${p.marker} ${p.seriesName}: ${val}${unit}<br/>`
          }
          return html
        },
      },
      legend: { bottom: 30 },
      grid: { left: 60, right: hasLoss ? 60 : 30, top: 30, bottom: 96 },
      xAxis: {
        type: 'time',
        min: effectiveStart,
        max: effectiveEnd,
        axisLabel: { formatter: xAxisLabelFormat },
        boundaryGap: false,
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
        { type: 'slider', xAxisIndex: 0, bottom: 8, height: 20, filterMode: 'none' },
      ],
      yAxis,
      series,
    }
    chart.value.setOption(option, true)
    _chartInitialized = true

    // 监听 dataZoom 事件以追踪缩放状态
    chart.value.off('datazoom')
    chart.value.on('datazoom', () => {
      const opt = chart.value?.getOption() as any
      if (!opt?.dataZoom?.length) return
      const dz = opt.dataZoom[0]
      const zoomed = dz.start !== 0 || dz.end !== 100
      isZoomed.value = zoomed
      if (zoomed) {
        zoomStart.value = dz.start
        zoomEnd.value = dz.end
      }
    })
  }
}

/** 重置图表缩放到基础视图 */
function resetZoom() {
  if (!chart.value) return
  isZoomed.value = false
  zoomStart.value = 0
  zoomEnd.value = 100
  // 强制完整刷新图表（含 xAxis 更新）
  _chartInitialized = false
  updateChart()
}

function handleRealtimeUpdate(data: any) {
  if (data.task_id !== taskId) return
  const result = data.result as ProbeResult
  if (!result) return
  // 仅 raw 粒度范围允许实时追加
  if (!isRawRange.value) return
  points.value.push(result)
  if (points.value.length > 500) points.value.shift()
  // 统计卡由定时 fetchData() 统一更新，此处仅更新图表
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
  isZoomed.value = false
  _chartInitialized = false
  fetchData()
  startAutoRefresh()
})
</script>

<template>
  <div>
    <NPageHeader @back="$router.back()" title="任务详情" />
    <NSpace style="margin: 16px 0" align="center">
      <NSelect v-model:value="range" :options="rangeOptions" style="width: 140px" />
      <NButton v-if="isZoomed" size="small" @click="resetZoom">重置缩放</NButton>
    </NSpace>

    <NGrid :x-gap="16" :y-gap="16" cols="2 m:5" responsive="screen" style="margin-bottom: 16px">
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
          <NTooltip>
            <template #trigger>
              <NStatistic label="窗口抖动" :value="avgWindowJitter != null ? `${fmt(avgWindowJitter)} ms` : '-'" />
            </template>
            基于最近 {{ JITTER_WINDOW }} 个延迟样本的标准差
          </NTooltip>
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="平均丢包" :value="stats.avg_packet_loss != null ? `${fmt(stats.avg_packet_loss)}%` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NTooltip v-if="dataPointTooltip">
            <template #trigger>
              <NStatistic label="数据点数" :value="dataPointLabel" />
            </template>
            {{ dataPointTooltip }}
          </NTooltip>
          <NStatistic v-else label="数据点数" :value="dataPointLabel" />
        </NCard>
      </NGi>
    </NGrid>

    <NCard>
      <NSpin :show="loading">
        <div ref="chartRef" style="width: 100%; height: 430px"></div>
      </NSpin>
    </NCard>
  </div>
</template>
