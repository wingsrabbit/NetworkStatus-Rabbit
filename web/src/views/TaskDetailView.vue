<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, shallowRef } from 'vue'
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
const taskId = Number(route.params.id)
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

async function fetchData() {
  loading.value = true
  try {
    const [dataRes, statsRes] = await Promise.all([
      getTaskData(taskId, { range: range.value }),
      getTaskStats(taskId, { range: range.value }),
    ])
    points.value = dataRes.data.points
    stats.value = statsRes.data.stats
    updateChart()
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chart.value) return

  const times = points.value.map((p) => dayjs(p.time).format('HH:mm:ss'))
  const latencies = points.value.map((p) => p.latency)
  const losses = points.value.map((p) => p.packet_loss)
  const jitters = points.value.map((p) => p.jitter)

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

  const hasLoss = losses.some((v) => v != null && v > 0)
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

  const hasJitter = jitters.some((v) => v != null)
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

  chart.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 60, right: hasLoss ? 60 : 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: times, boundaryGap: false },
    yAxis,
    series,
  }, true)
}

function handleRealtimeUpdate(data: any) {
  if (data.task_id !== taskId) return
  const latest = data.latest as ProbeResult
  if (!latest) return
  points.value.push(latest)
  if (points.value.length > 500) points.value.shift()
  updateChart()
}

onMounted(() => {
  if (chartRef.value) {
    chart.value = echarts.init(chartRef.value)
    window.addEventListener('resize', () => chart.value?.resize())
  }
  fetchData()
  subscribeTask(taskId)
  socket.value?.on('dashboard:task_update', handleRealtimeUpdate)
})

onUnmounted(() => {
  unsubscribeTask(taskId)
  socket.value?.off('dashboard:task_update', handleRealtimeUpdate)
  chart.value?.dispose()
})

watch(range, () => fetchData())
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
          <NStatistic label="平均延迟" :value="stats.avg_latency != null ? `${stats.avg_latency.toFixed(1)} ms` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="P95 延迟" :value="stats.p95_latency != null ? `${stats.p95_latency.toFixed(1)} ms` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="平均丢包" :value="stats.avg_packet_loss != null ? `${stats.avg_packet_loss.toFixed(1)}%` : '-'" />
        </NCard>
      </NGi>
      <NGi>
        <NCard>
          <NStatistic label="数据点数" :value="stats.count ?? '-'" />
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
