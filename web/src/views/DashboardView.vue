<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NGrid, NGi, NCard, NStatistic, NTag, NSpace, NInput, NSelect, NSpin, NEmpty, NBadge,
  NButton, NButtonGroup, NPagination
} from 'naive-ui'
import { useDashboardStore } from '@/stores/dashboard'
import type { DashboardTask } from '@/types'

const router = useRouter()
const store = useDashboardStore()
const search = ref('')
const protocolFilter = ref<string | null>(null)
const viewMode = ref<'grid' | 'list'>('grid')
const pageSize = ref(10)
const currentPage = ref(1)

const protocolOptions = [
  { label: '全部', value: '' },
  { label: 'ICMP', value: 'icmp' },
  { label: 'TCP', value: 'tcp' },
  { label: 'UDP', value: 'udp' },
  { label: 'HTTP', value: 'http' },
  { label: 'DNS', value: 'dns' },
]

const pageSizeOptions = [
  { label: '10 条', value: 10 },
  { label: '20 条', value: 20 },
  { label: '50 条', value: 50 },
]

onMounted(() => {
  store.fetchDashboard()
})

const filteredTasks = computed(() => {
  let result = [...store.tasks]
  if (search.value) {
    const s = search.value.toLowerCase()
    result = result.filter(
      (t) =>
        t.name.toLowerCase().includes(s) ||
        t.target.toLowerCase().includes(s) ||
        t.source_node.toLowerCase().includes(s)
    )
  }
  if (protocolFilter.value) {
    result = result.filter((t) => t.protocol === protocolFilter.value)
  }
  // Sort alphabetically by name
  result.sort((a, b) => a.name.localeCompare(b.name))
  return result
})

const totalPages = computed(() => Math.ceil(filteredTasks.value.length / pageSize.value))
const pagedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTasks.value.slice(start, start + pageSize.value)
})

// Reset page when filter changes
function onFilterChange() {
  currentPage.value = 1
}

function latencyColor(latency: number | null | undefined) {
  if (latency == null) return 'default'
  if (latency < 50) return 'success'
  if (latency < 200) return 'warning'
  return 'error'
}

function formatLatency(val: number | null | undefined) {
  if (val == null) return '-'
  return `${val.toFixed(2)} ms`
}

function goToDetail(task: DashboardTask) {
  router.push(`/dashboard/${task.task_id}`)
}
</script>

<template>
  <div>
    <!-- Summary bar -->
    <NGrid :x-gap="16" :y-gap="16" cols="2 m:4" responsive="screen" style="margin-bottom: 16px">
      <NGi><NCard><NStatistic label="节点数" :value="store.summary.total_nodes" /></NCard></NGi>
      <NGi><NCard><NStatistic label="任务数" :value="store.summary.total_tasks" /></NCard></NGi>
      <NGi><NCard><NStatistic label="在线" :value="store.summary.online_nodes" /></NCard></NGi>
      <NGi><NCard><NStatistic label="告警" :value="store.summary.alerting_tasks" /></NCard></NGi>
    </NGrid>

    <!-- Toolbar -->
    <NSpace style="margin-bottom: 16px;" align="center" justify="space-between">
      <NSpace align="center">
        <NInput v-model:value="search" placeholder="搜索任务/目标/节点" clearable style="width: 250px" @update:value="onFilterChange" />
        <NSelect v-model:value="protocolFilter" :options="protocolOptions" placeholder="协议" style="width: 120px" clearable @update:value="onFilterChange" />
      </NSpace>
      <NSpace align="center" :size="12">
        <NSelect v-model:value="pageSize" :options="pageSizeOptions" style="width: 100px" @update:value="onFilterChange" />
        <NButtonGroup size="small">
          <NButton :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'" title="卡片视图">
            <template #icon><span style="font-size: 14px">▦</span></template>
          </NButton>
          <NButton :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'" title="列表视图">
            <template #icon><span style="font-size: 14px">☰</span></template>
          </NButton>
        </NButtonGroup>
      </NSpace>
    </NSpace>

    <NSpin :show="store.loading">
      <NEmpty v-if="filteredTasks.length === 0 && !store.loading" description="暂无数据" />

      <!-- Grid view (cards) -->
      <NGrid v-else-if="viewMode === 'grid'" :x-gap="16" :y-gap="16" cols="1 s:2 m:3 l:4" responsive="screen">
        <NGi v-for="task in pagedTasks" :key="task.task_id">
          <NCard hoverable style="cursor: pointer" @click="goToDetail(task)">
            <template #header>
              <NSpace align="center" justify="space-between" style="width: 100%">
                <span>{{ task.name }}</span>
                <NSpace :size="4">
                  <NTag size="small" round>{{ task.protocol.toUpperCase() }}</NTag>
                  <NBadge v-if="task.alert_status === 'alerting'" dot type="error" />
                </NSpace>
              </NSpace>
            </template>
            <NSpace vertical :size="8">
              <div style="color: var(--n-text-color-3); font-size: 13px;">
                {{ task.source_node }} → {{ task.target }}
              </div>
              <NSpace :size="24">
                <NStatistic label="延迟" :value="formatLatency(task.latest?.latency)" />
                <NStatistic v-if="task.latest?.packet_loss != null" label="丢包" :value="`${task.latest.packet_loss.toFixed(2)}%`" />
                <NStatistic v-if="task.latest?.status_code != null" label="状态码" :value="task.latest.status_code" />
              </NSpace>
            </NSpace>
          </NCard>
        </NGi>
      </NGrid>

      <!-- List view (horizontal rows) -->
      <div v-else class="list-view">
        <NCard v-for="task in pagedTasks" :key="task.task_id" hoverable style="cursor: pointer; margin-bottom: 8px" @click="goToDetail(task)">
          <NSpace align="center" justify="space-between" style="width: 100%">
            <NSpace align="center" :size="16" style="flex: 1; min-width: 0">
              <NTag size="small" round style="flex-shrink: 0">{{ task.protocol.toUpperCase() }}</NTag>
              <span style="font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">{{ task.name }}</span>
              <span style="color: var(--n-text-color-3); font-size: 13px; white-space: nowrap">
                {{ task.source_node }} → {{ task.target }}
              </span>
            </NSpace>
            <NSpace align="center" :size="24" style="flex-shrink: 0">
              <NStatistic label="延迟" :value="formatLatency(task.latest?.latency)" />
              <NStatistic v-if="task.latest?.packet_loss != null" label="丢包" :value="`${task.latest.packet_loss.toFixed(2)}%`" />
              <NStatistic v-if="task.latest?.status_code != null" label="状态码" :value="task.latest.status_code" />
              <NBadge v-if="task.alert_status === 'alerting'" dot type="error" />
            </NSpace>
          </NSpace>
        </NCard>
      </div>

      <!-- Pagination -->
      <NSpace v-if="filteredTasks.length > pageSize" justify="center" style="margin-top: 16px">
        <NPagination
          v-model:page="currentPage"
          :page-count="totalPages"
          :page-size="pageSize"
        />
      </NSpace>
    </NSpin>
  </div>
</template>
