<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, shallowRef, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  NCard, NSpace, NSelect, NStatistic, NGrid, NGi, NSpin, NPageHeader, NButton, NTooltip,
  NTable
} from 'naive-ui'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { getTaskData, getTaskStats, getTaskAlerts } from '@/api/data'
import { getTask } from '@/api/tasks'
import { useSocket } from '@/composables/useSocket'
import type { ProbeResult, AlertHistory, ProbeTask } from '@/types'

const route = useRoute()
const taskId = route.params.taskId as string
const { subscribeTask, unsubscribeTask, socket } = useSocket()

const chartRef = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts>()
const points = ref<ProbeResult[]>([])
const stats = ref<Record<string, any>>({})
const alertHistory = ref<AlertHistory[]>([])
const taskInfo = ref<ProbeTask | null>(null)
const loading = ref(false)
const range = ref('30m')

const protocol = computed(() => taskInfo.value?.protocol || 'icmp')

const rangeOptions = [
  { label: '30 分钟', value: '30m' },
  { label: '1 小时', value: '1h' },
  { label: '24 小时', value: '24h' },
  { label: '3 天', value: '3d' },
  { label: '7 天', value: '7d' },
  { label: '30 天', value: '30d' },
]

/** 是否使用 raw 粒度（允许实时追加） */
const isRawRange = computed(() => ['30m', '1h'].includes(range.value))

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

function refreshInterval(r: string): number {
  if (['30m', '1h'].includes(r)) return 5_000
  if (['24h', '3d'].includes(r)) return 60_000
  if (['7d', '30d'].includes(r)) return 300_000
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

let _chartInitialized = false

/** 将告警历史转为 markArea 数据 */
function buildMarkAreaData(): any[] {
  const areas: any[] = []
  const alerts = alertHistory.value
  // Pair alert→recovery events by metric, in chronological order
  const pendingAlerts: Record<string, AlertHistory> = {}
  for (const ev of alerts) {
    const key = ev.metric
    if (ev.event_type === 'alert') {
      pendingAlerts[key] = ev
    } else if (ev.event_type === 'recovery') {
      const startEv = pendingAlerts[key]
      const startTime = startEv?.created_at || ev.alert_started_at
      if (startTime) {
        const durationText = ev.duration_seconds != null ? `${ev.duration_seconds}s` : ''
        areas.push([
          {
            xAxis: new Date(startTime).getTime(),
            itemStyle: { color: 'rgba(208, 48, 80, 0.12)' },
            name: `${key} 告警${durationText ? ' (' + durationText + ')' : ''}`,
          },
          { xAxis: new Date(ev.created_at).getTime() }
        ])
        delete pendingAlerts[key]
      }
    }
  }
  // Still-active alerts: extend to now
  for (const [key, ev] of Object.entries(pendingAlerts)) {
    areas.push([
      {
        xAxis: new Date(ev.created_at).getTime(),
        itemStyle: { color: 'rgba(208, 48, 80, 0.18)' },
        name: `${key} 告警中`,
      },
      { xAxis: Date.now() }
    ])
  }
  return areas
}

/** DNS 解析 IP 变更记录 */
const dnsIpChanges = computed(() => {
  if (protocol.value !== 'dns') return []
  const changes: { timestamp: string; ip: string }[] = []
  let lastIp: string | null = null
  for (const p of points.value) {
    if (p.resolved_ip && p.resolved_ip !== lastIp) {
      changes.push({ timestamp: p.timestamp, ip: p.resolved_ip })
      lastIp = p.resolved_ip
    }
  }
  return changes
})

async function fetchData() {
  loading.value = true
  try {
    const promises: Promise<any>[] = [
      getTaskData(taskId, { range: range.value }),
      getTaskStats(taskId, { range: range.value }),
      getTaskAlerts(taskId, { range: range.value }),
    ]
    if (!taskInfo.value) {
      promises.push(getTask(taskId))
    }
    const results = await Promise.all(promises)
    points.value = results[0].data.data
    stats.value = results[1].data.stats
    alertHistory.value = results[2].data.alerts || []
    if (results[3]) {
      taskInfo.value = results[3].data.task
    }
    updateChart()
  } finally {
    loading.value = false
  }
}

function getXAxisConfig() {
  const now = Date.now()
  const windowMs = rangeToMs(range.value)
  const effectiveEnd = now - tailMarginMs.value
  const effectiveStart = effectiveEnd - windowMs

  const xAxisLabelFormat = (() => {
    switch (range.value) {
      case '30m': case '1h': return '{HH}:{mm}:{ss}'
      case '24h': case '3d': return '{HH}:{mm}'
      case '7d': case '30d': return '{MM}-{dd} {HH}:{mm}'
      default: return '{HH}:{mm}:{ss}'
    }
  })()

  return { effectiveStart, effectiveEnd, xAxisLabelFormat }
}

function getTooltipFormat(): string {
  switch (range.value) {
    case '30m': case '1h': return 'HH:mm:ss'
    case '24h': case '3d': return 'HH:mm'
    case '7d': case '30d': return 'MM-DD HH:mm'
    default: return 'HH:mm:ss'
  }
}

/** 构建通用 tooltip formatter */
function tooltipFormatter(params: any): string {
  if (!Array.isArray(params) || !params.length) return ''
  const tfmt = getTooltipFormat()
  const time = dayjs(params[0].value[0]).format(tfmt)
  let html = `${time}<br/>`
  for (const p of params) {
    if (p.componentType === 'markArea') continue
    const name = p.seriesName
    let unit = ' ms'
    if (name.includes('%') || name.includes('成功率')) unit = '%'
    else if (name.includes('状态码')) unit = ''
    else if (name.includes('IP')) unit = ''
    const val = p.value[1] != null ? (typeof p.value[1] === 'number' ? Number(p.value[1]).toFixed(2) : p.value[1]) : '-'
    html += `${p.marker} ${name}: ${val}${unit}<br/>`
  }
  return html
}

/** 根据协议构建 series 和 yAxis */
function buildProtocolChart() {
  const markAreaData = buildMarkAreaData()
  const markArea = markAreaData.length > 0 ? {
    silent: false,
    data: markAreaData,
    label: { show: true, position: 'insideTop', fontSize: 10, color: '#d03050' },
    emphasis: { label: { show: true } },
  } : undefined

  const p = protocol.value
  if (p === 'http') return buildHttpChart(markArea)
  if (p === 'dns') return buildDnsChart(markArea)
  if (p === 'tcp') return buildTcpChart(markArea)
  if (p === 'udp') return buildUdpChart(markArea)
  return buildIcmpChart(markArea) // icmp or default
}

function buildIcmpChart(markArea: any) {
  const latencies = points.value.map((p) => [p.timestamp, p.latency])

  const backendJitters = points.value.map((p) => p.jitter)
  const hasBackendJitter = backendJitters.some((v) => v != null)
  let jitters: [any, number | null][]
  if (hasBackendJitter) {
    jitters = points.value.map((p) => [p.timestamp, p.jitter])
  } else {
    const windowJitters = computeWindowJitter(points.value)
    jitters = points.value.map((p, i) => [p.timestamp, windowJitters[i]])
  }

  const series: any[] = [{
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
    markArea,
  }]

  // Red dots for packet loss
  const lossPoints = points.value
    .filter(p => p.packet_loss != null && p.packet_loss > 0)
    .map(p => [p.timestamp, p.latency ?? 0])
  if (lossPoints.length > 0) {
    series.push({
      name: '丢包',
      type: 'scatter',
      data: lossPoints,
      symbolSize: 6,
      itemStyle: { color: '#d03050' },
      z: 10,
    })
  }

  const hasJitter = jitters.some(([, v]) => v != null)
  const yAxis: any[] = [{ type: 'value', name: 'ms', min: 0 }]

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

  return { series, yAxis, rightMargin: 30 }
}

function buildTcpChart(markArea: any) {
  const latencies = points.value.map((p) => [p.timestamp, p.latency])

  const windowJitters = computeWindowJitter(points.value)
  const jitters: [any, number | null][] = points.value.map((p, i) => [p.timestamp, windowJitters[i]])

  const series: any[] = [{
    name: '连接延迟 (ms)',
    type: 'line',
    data: latencies,
    smooth: true,
    showSymbol: false,
    itemStyle: { color: '#18a058' },
    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(24,160,88,0.3)' },
      { offset: 1, color: 'rgba(24,160,88,0.02)' },
    ])},
    markArea,
  }]

  // Red dots for connection failures
  const failPoints = points.value
    .filter(p => p.success === false)
    .map(p => [p.timestamp, p.latency ?? 0])
  if (failPoints.length > 0) {
    series.push({
      name: '连接失败',
      type: 'scatter',
      data: failPoints,
      symbolSize: 6,
      itemStyle: { color: '#d03050' },
      z: 10,
    })
  }

  const hasJitter = jitters.some(([, v]) => v != null)
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

  const yAxis: any[] = [{ type: 'value', name: 'ms', min: 0 }]
  return { series, yAxis, rightMargin: 30 }
}

function buildUdpChart(markArea: any) {
  const latencies = points.value.map((p) => [p.timestamp, p.latency])

  const backendJitters = points.value.map((p) => p.jitter)
  const hasBackendJitter = backendJitters.some((v) => v != null)
  let jitters: [any, number | null][]
  if (hasBackendJitter) {
    jitters = points.value.map((p) => [p.timestamp, p.jitter])
  } else {
    const windowJitters = computeWindowJitter(points.value)
    jitters = points.value.map((p, i) => [p.timestamp, windowJitters[i]])
  }

  const series: any[] = [{
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
    markArea,
  }]

  // Red dots for packet loss
  const lossPoints = points.value
    .filter(p => p.packet_loss != null && p.packet_loss > 0)
    .map(p => [p.timestamp, p.latency ?? 0])
  if (lossPoints.length > 0) {
    series.push({
      name: '丢包',
      type: 'scatter',
      data: lossPoints,
      symbolSize: 6,
      itemStyle: { color: '#d03050' },
      z: 10,
    })
  }

  const hasJitter = jitters.some(([, v]) => v != null)
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

  const yAxis: any[] = [{ type: 'value', name: 'ms', min: 0 }]
  return { series, yAxis, rightMargin: 30 }
}

function buildHttpChart(markArea: any) {
  const totalTime = points.value.map((p) => [p.timestamp, p.total_time ?? p.latency])
  const dnsTime = points.value.map((p) => [p.timestamp, p.dns_time])
  const tcpTime = points.value.map((p) => [p.timestamp, p.tcp_time])
  const tlsTime = points.value.map((p) => [p.timestamp, p.tls_time])
  const ttfb = points.value.map((p) => [p.timestamp, p.ttfb])
  const statusCodes = points.value.map((p) => [p.timestamp, p.status_code])

  const series: any[] = [{
    name: '总响应时间 (ms)',
    type: 'line',
    data: totalTime,
    smooth: true,
    showSymbol: false,
    itemStyle: { color: '#18a058' },
    markArea,
  }]

  // Stacked area for phases
  const hasPhases = dnsTime.some(([, v]) => v != null) || tcpTime.some(([, v]) => v != null) ||
    tlsTime.some(([, v]) => v != null) || ttfb.some(([, v]) => v != null)
  if (hasPhases) {
    const phaseColors = ['#2080f0', '#f0a020', '#a855f7', '#36cfc9']
    const phases = [
      { name: 'DNS (ms)', data: dnsTime, color: phaseColors[0] },
      { name: 'TCP (ms)', data: tcpTime, color: phaseColors[1] },
      { name: 'TLS (ms)', data: tlsTime, color: phaseColors[2] },
      { name: 'TTFB (ms)', data: ttfb, color: phaseColors[3] },
    ]
    for (const phase of phases) {
      if (phase.data.some(([, v]) => v != null)) {
        series.push({
          name: phase.name,
          type: 'line',
          stack: 'phases',
          data: phase.data,
          smooth: true,
          showSymbol: false,
          areaStyle: { opacity: 0.4 },
          itemStyle: { color: phase.color },
          lineStyle: { width: 1 },
        })
      }
    }
  }

  // Status code scatter
  const hasStatusCodes = statusCodes.some(([, v]) => v != null)
  const yAxis: any[] = [{ type: 'value', name: 'ms', min: 0 }]
  if (hasStatusCodes) {
    series.push({
      name: 'HTTP 状态码',
      type: 'scatter',
      data: statusCodes.filter(([, v]) => v != null),
      yAxisIndex: 1,
      symbolSize: 6,
      itemStyle: {
        color: (params: any) => {
          const code = params.value[1]
          if (code >= 200 && code < 300) return '#18a058'
          if (code >= 300 && code < 400) return '#2080f0'
          if (code >= 400 && code < 500) return '#f0a020'
          return '#d03050'
        }
      },
    })
    yAxis.push({ type: 'value', name: '状态码', min: 100, max: 600, splitLine: { show: false } })
  }

  return { series, yAxis, rightMargin: hasStatusCodes ? 60 : 30 }
}

function buildDnsChart(markArea: any) {
  const latencies = points.value.map((p) => [p.timestamp, p.latency])

  const series: any[] = [{
    name: '解析时间 (ms)',
    type: 'line',
    data: latencies,
    smooth: true,
    showSymbol: false,
    itemStyle: { color: '#18a058' },
    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(24,160,88,0.3)' },
      { offset: 1, color: 'rgba(24,160,88,0.02)' },
    ])},
    markArea,
  }]

  // Red dots for resolution failures
  const failPoints = points.value
    .filter(p => p.success === false)
    .map(p => [p.timestamp, p.latency ?? 0])
  if (failPoints.length > 0) {
    series.push({
      name: '解析失败',
      type: 'scatter',
      data: failPoints,
      symbolSize: 6,
      itemStyle: { color: '#d03050' },
      z: 10,
    })
  }

  const yAxis: any[] = [{ type: 'value', name: 'ms', min: 0 }]
  return { series, yAxis, rightMargin: 30 }
}

function updateChart() {
  if (!chart.value) return

  const { series, yAxis, rightMargin } = buildProtocolChart()
  const { effectiveStart, effectiveEnd, xAxisLabelFormat } = getXAxisConfig()

  if (isZoomed.value && _chartInitialized) {
    chart.value.setOption({ series })
  } else {
    const option: any = {
      tooltip: {
        trigger: 'axis',
        formatter: tooltipFormatter,
      },
      legend: { bottom: 30 },
      grid: { left: 60, right: rightMargin, top: 30, bottom: 96 },
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

function resetZoom() {
  if (!chart.value) return
  isZoomed.value = false
  zoomStart.value = 0
  zoomEnd.value = 100
  _chartInitialized = false
  updateChart()
}

function handleRealtimeUpdate(data: any) {
  if (data.task_id !== taskId) return
  const result = data.result as ProbeResult
  if (!result) return
  if (!isRawRange.value) return
  points.value.push(result)
  if (points.value.length > 500) points.value.shift()
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
  socket.value?.on('dashboard:task_detail', handleRealtimeUpdate)
})

onUnmounted(() => {
  stopAutoRefresh()
  unsubscribeTask(taskId)
  socket.value?.off('dashboard:task_detail', handleRealtimeUpdate)
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

    <!-- DNS 协议：解析 IP 变更记录 -->
    <NCard v-if="protocol === 'dns' && dnsIpChanges.length > 0" title="解析 IP 变更记录" style="margin-top: 16px">
      <NTable :bordered="false" :single-line="false" size="small">
        <thead>
          <tr><th>时间</th><th>解析 IP</th></tr>
        </thead>
        <tbody>
          <tr v-for="(change, i) in dnsIpChanges" :key="i">
            <td>{{ dayjs(change.timestamp).format('YYYY-MM-DD HH:mm:ss') }}</td>
            <td>{{ change.ip }}</td>
          </tr>
        </tbody>
      </NTable>
    </NCard>
  </div>
</template>
