<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NGrid, NGi, NCard, NStatistic, NTag, NSpace, NInput, NSelect, NSpin, NEmpty, NBadge
} from 'naive-ui'
import { useDashboardStore } from '@/stores/dashboard'
import type { DashboardTask } from '@/types'

const router = useRouter()
const store = useDashboardStore()
const search = ref('')
const protocolFilter = ref<string | null>(null)
const statusFilter = ref<string | null>(null)

const protocolOptions = [
  { label: '全部', value: '' },
  { label: 'ICMP', value: 'icmp' },
  { label: 'TCP', value: 'tcp' },
  { label: 'UDP', value: 'udp' },
  { label: 'HTTP', value: 'http' },
  { label: 'DNS', value: 'dns' },
]

const statusOptions = [
  { label: '全部', value: '' },
  { label: '在线', value: 'online' },
  { label: '离线', value: 'offline' },
]

onMounted(() => {
  store.fetchDashboard()
})

const filteredTasks = computed(() => {
  let result = store.tasks
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
  return result
})

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

    <NSpace style="margin-bottom: 16px;" align="center">
      <NInput v-model:value="search" placeholder="搜索任务/目标/节点" clearable style="width: 250px" />
      <NSelect v-model:value="protocolFilter" :options="protocolOptions" placeholder="协议" style="width: 120px" clearable />
    </NSpace>

    <NSpin :show="store.loading">
      <NEmpty v-if="filteredTasks.length === 0 && !store.loading" description="暂无数据" />
      <NGrid v-else :x-gap="16" :y-gap="16" cols="1 s:2 m:3 l:4" responsive="screen">
        <NGi v-for="task in filteredTasks" :key="task.task_id">
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
    </NSpin>
  </div>
</template>
