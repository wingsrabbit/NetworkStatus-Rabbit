<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, shallowRef, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  NCard, NSpace, NSelect, NStatistic, NGrid, NGi, NSpin, NPageHeader, NButton, NTooltip,
  NTable, NTag
} from 'naive-ui'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { getTaskData, getTaskStats, getTaskAlerts } from '@/api/data'
import { getTask } from '@/api/tasks'
import { useSocket } from '@/composables/useSocket'
import type { ProbeResult, AlertHistory, ProbeTask, MtrHop } from '@/types'

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

/** Whether this is an MTR protocol */
const isMtr = computed(() => ['mtr_icmp', 'mtr_tcp', 'mtr_udp'].includes(protocol.value))

const mtrLastUpdate = ref<string | null>(null)
/** Timestamp when cumulative MTR stats began (first data or after reset) */
const mtrStartTime = ref<string | null>(null)

/** Latest MTR hops snapshot from the persistent mtr process (agent accumulates stats) */
const mtrSrc = ref('')
const mtrDst = ref('')
const mtrLatestHops = ref<MtrHop[]>([])

const mtrDisplayHops = computed(() => {
  return mtrLatestHops.value.map(hop => ({
    hop: hop.hop,
    host: hop.host,
    altHosts: [] as string[],
    loss: hop.loss,
    sent: hop.sent,
    last: hop.last,
    avg: hop.avg,
    best: hop.best,
    worst: hop.worst,
    stdev: hop.stdev,
  }))
})

function resetMtrStats() {
  mtrLatestHops.value = []
  mtrSrc.value = ''
  mtrDst.value = ''
  mtrLastUpdate.value = null
  // Tell server to restart the MTR task on the agent (server will persist and push reset_time)
  socket.value?.emit('dashboard:reset_mtr', { task_id: taskId })
}

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
    // MTR: just use the latest data point's snapshot (agent accumulates stats)
    if (isMtr.value && points.value.length > 0) {
      if (!mtrStartTime.value) {
        mtrStartTime.value = taskInfo.value?.mtr_reset_time || taskInfo.value?.created_at || points.value[0].timestamp
      }
      const lastPoint = points.value[points.value.length - 1]
      if (lastPoint?.hops) {
        mtrLatestHops.value = lastPoint.hops
        mtrLastUpdate.value = lastPoint.timestamp
        if (lastPoint.extra?.mtr_src) mtrSrc.value = lastPoint.extra.mtr_src
        if (lastPoint.extra?.mtr_dst) mtrDst.value = lastPoint.extra.mtr_dst
      }
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
  if (!chart.value || isMtr.value) return

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

  // MTR: replace display with the latest accumulated snapshot from agent
  if (isMtr.value && result.hops) {
    mtrLatestHops.value = result.hops
    mtrLastUpdate.value = result.timestamp
    if (result.extra?.mtr_src) mtrSrc.value = result.extra.mtr_src
    if (result.extra?.mtr_dst) mtrDst.value = result.extra.mtr_dst
  }

  if (!isRawRange.value) return
  points.value.push(result)
  if (points.value.length > 500) points.value.shift()
  updateChart()
  ;(window as any).__nsr_markDataReceived?.()
}

function handleMtrReset(data: any) {
  if (data.task_id !== taskId) return
  mtrLatestHops.value = []
  mtrSrc.value = ''
  mtrDst.value = ''
  mtrLastUpdate.value = null
  const resetTime = data.reset_time || new Date().toISOString()
  mtrStartTime.value = resetTime
  // Also update taskInfo so subsequent fetchData uses the new reset time
  if (taskInfo.value) {
    taskInfo.value.mtr_reset_time = resetTime
  }
}

onMounted(async () => {
  // Fetch task info first so isMtr can be evaluated before chart init
  try {
    const res = await getTask(taskId)
    taskInfo.value = res.data.task
    // Set MTR start time immediately from persisted reset time or task creation time
    if (isMtr.value) {
      mtrStartTime.value = taskInfo.value?.mtr_reset_time || taskInfo.value?.created_at || null
    }
  } catch (_) { /* will be retried in fetchData */ }

  if (!isMtr.value && chartRef.value) {
    chart.value = echarts.init(chartRef.value)
    window.addEventListener('resize', () => chart.value?.resize())
  }
  await fetchData()
  startAutoRefresh()
  subscribeTask(taskId)
  socket.value?.on('dashboard:task_detail', handleRealtimeUpdate)
  socket.value?.on('dashboard:mtr_reset', handleMtrReset)
})

onUnmounted(() => {
  stopAutoRefresh()
  unsubscribeTask(taskId)
  socket.value?.off('dashboard:task_detail', handleRealtimeUpdate)
  socket.value?.off('dashboard:mtr_reset', handleMtrReset)
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
    <!-- MTR 模式：只显示 mtr 终端风格的路由追踪表 -->
    <template v-if="isMtr">
      <NCard style="margin-top: 16px; font-family: 'Courier New', Consolas, 'Liberation Mono', monospace; background: #1e1e2e; color: #cdd6f4;">
        <template #header>
          <NSpace align="center" justify="space-between" style="width: 100%;">
            <NSpace align="center" :size="12">
              <span style="color: #cdd6f4;">MTR 路由追踪</span>
              <NTag size="small" :type="mtrDisplayHops.length > 0 ? 'success' : 'default'"
                v-if="mtrLastUpdate">{{ dayjs(mtrLastUpdate).format('HH:mm:ss') }} 更新</NTag>
              <span v-if="mtrStartTime" style="color: #6c7086; font-size: 12px;">
                开始于 {{ dayjs(mtrStartTime).format('YYYY-MM-DD HH:mm:ss') }}
              </span>
            </NSpace>
            <NButton size="small" quaternary type="warning" @click="resetMtrStats"
              :disabled="mtrDisplayHops.length === 0">重置统计</NButton>
          </NSpace>
        </template>
        <NSpin :show="loading && mtrDisplayHops.length === 0">
          <!-- Header: source (IP) → target  |  timestamp + mode -->
          <div v-if="taskInfo" style="margin-bottom: 8px; color: #a6adc8; font-size: 13px; display: flex; justify-content: space-between;">
            <span>
              {{ mtrSrc || taskInfo.source_node_name || taskInfo.source_node_id }}
              <span v-if="taskInfo.source_node_ip" style="color: #6c7086;">({{ taskInfo.source_node_ip }})</span>
              →
              {{ taskInfo.target_address }}
              <span v-if="mtrDst && mtrDst !== taskInfo.target_address" style="color: #6c7086;">({{ mtrDst }})</span>
            </span>
            <span style="color: #6c7086;">
              <span v-if="mtrLastUpdate" style="margin-right: 16px;">{{ dayjs(mtrLastUpdate).format('YYYY-MM-DDTHH:mm:ssZ') }}</span>
              {{ protocol.replace('mtr_', '').toUpperCase() }} mode
            </span>
          </div>
          <div v-if="mtrDisplayHops.length === 0" style="text-align: center; padding: 40px 0; color: #6c7086;">
            等待首次探测结果…
          </div>
          <div v-else style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; line-height: 1.8;">
              <thead>
                <tr style="border-bottom: 1px solid #45475a; color: #a6adc8;">
                  <th style="padding: 4px 10px; text-align: left; width: 40px;"></th>
                  <th style="padding: 4px 10px; text-align: left; min-width: 200px;">Host</th>
                  <th style="padding: 4px 10px; text-align: right; width: 70px;">Loss%</th>
                  <th style="padding: 4px 10px; text-align: right; width: 55px;">Snt</th>
                  <th style="padding: 4px 10px; text-align: right; width: 75px;">Last</th>
                  <th style="padding: 4px 10px; text-align: right; width: 75px;">Avg</th>
                  <th style="padding: 4px 10px; text-align: right; width: 75px;">Best</th>
                  <th style="padding: 4px 10px; text-align: right; width: 75px;">Wrst</th>
                  <th style="padding: 4px 10px; text-align: right; width: 75px;">StDev</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="hop in mtrDisplayHops" :key="hop.hop">
                  <tr :style="{ borderBottom: hop.altHosts.length > 0 ? 'none' : '1px solid #313244' }">
                    <td style="padding: 4px 10px; color: #f9e2af;">{{ hop.hop }}.</td>
                    <td style="padding: 4px 10px;"
                        :style="{ color: hop.host === '???' ? '#6c7086' : '#cdd6f4' }">{{ hop.host }}</td>
                    <td style="padding: 4px 10px; text-align: right;"
                        :style="{ color: hop.loss > 0 ? '#f38ba8' : '#a6e3a1', fontWeight: hop.loss > 0 ? 'bold' : 'normal' }">
                      {{ hop.loss.toFixed(1) }}%
                    </td>
                    <td style="padding: 4px 10px; text-align: right; color: #a6adc8;">{{ hop.sent }}</td>
                    <td style="padding: 4px 10px; text-align: right; color: #cdd6f4;">{{ hop.last.toFixed(1) }}</td>
                    <td style="padding: 4px 10px; text-align: right; color: #cdd6f4; font-weight: 500;">{{ hop.avg.toFixed(1) }}</td>
                    <td style="padding: 4px 10px; text-align: right; color: #a6e3a1;">{{ hop.best.toFixed(1) }}</td>
                    <td style="padding: 4px 10px; text-align: right; color: #f38ba8;">{{ hop.worst.toFixed(1) }}</td>
                    <td style="padding: 4px 10px; text-align: right; color: #a6adc8;">{{ hop.stdev.toFixed(1) }}</td>
                  </tr>
                  <tr v-for="(altHost, j) in hop.altHosts" :key="`${hop.hop}-alt-${j}`"
                      :style="{ borderBottom: j === hop.altHosts.length - 1 ? '1px solid #313244' : 'none' }">
                    <td style="padding: 0 10px;"></td>
                    <td style="padding: 0 10px 0 30px; color: #7f849c; font-size: 12px;">{{ altHost }}</td>
                    <td colspan="7"></td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </NSpin>
      </NCard>
    </template>

    <!-- 非 MTR 模式：统计卡片 + 图表 -->
    <template v-else>
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
    </template>

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
