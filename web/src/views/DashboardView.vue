<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NGrid, NGi, NCard, NStatistic, NTag, NSpace, NInput, NSelect, NSpin, NEmpty, NBadge
} from 'naive-ui'
import { useDashboardStore } from '@/stores/dashboard'
import type { DashboardCard } from '@/types'

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
  store.fetchCards()
})

const filteredCards = computed(() => {
  let result = store.cards
  if (search.value) {
    const s = search.value.toLowerCase()
    result = result.filter(
      (c) =>
        c.task_name.toLowerCase().includes(s) ||
        c.target_address.toLowerCase().includes(s) ||
        c.source_node_name.toLowerCase().includes(s)
    )
  }
  if (protocolFilter.value) {
    result = result.filter((c) => c.protocol === protocolFilter.value)
  }
  if (statusFilter.value) {
    result = result.filter((c) => c.source_node_status === statusFilter.value)
  }
  return result
})

function statusColor(status: string) {
  return status === 'online' ? 'success' : 'error'
}

function latencyColor(latency: number | null | undefined) {
  if (latency == null) return 'default'
  if (latency < 50) return 'success'
  if (latency < 200) return 'warning'
  return 'error'
}

function formatLatency(val: number | null | undefined) {
  if (val == null) return '-'
  return `${val.toFixed(1)} ms`
}

function goToDetail(card: DashboardCard) {
  router.push(`/task/${card.task_id}`)
}
</script>

<template>
  <div>
    <NSpace style="margin-bottom: 16px;" align="center">
      <NInput v-model:value="search" placeholder="搜索任务/目标/节点" clearable style="width: 250px" />
      <NSelect v-model:value="protocolFilter" :options="protocolOptions" placeholder="协议" style="width: 120px" clearable />
      <NSelect v-model:value="statusFilter" :options="statusOptions" placeholder="状态" style="width: 120px" clearable />
    </NSpace>

    <NSpin :show="store.loading">
      <NEmpty v-if="filteredCards.length === 0 && !store.loading" description="暂无数据" />
      <NGrid v-else :x-gap="16" :y-gap="16" cols="1 s:2 m:3 l:4" responsive="screen">
        <NGi v-for="card in filteredCards" :key="card.task_id">
          <NCard hoverable style="cursor: pointer" @click="goToDetail(card)">
            <template #header>
              <NSpace align="center" justify="space-between" style="width: 100%">
                <span>{{ card.task_name }}</span>
                <NSpace :size="4">
                  <NTag :type="statusColor(card.source_node_status)" size="small" round>
                    {{ card.source_node_status === 'online' ? '在线' : '离线' }}
                  </NTag>
                  <NTag size="small" round>{{ card.protocol.toUpperCase() }}</NTag>
                  <NBadge v-if="card.alert_status === 'triggered'" dot type="error" />
                </NSpace>
              </NSpace>
            </template>
            <NSpace vertical :size="8">
              <div style="color: var(--n-text-color-3); font-size: 13px;">
                {{ card.source_node_name }} → {{ card.target_address }}
              </div>
              <NSpace :size="24">
                <NStatistic label="延迟" :value="formatLatency(card.latest?.latency)" />
                <NStatistic v-if="card.latest?.packet_loss != null" label="丢包" :value="`${card.latest.packet_loss}%`" />
                <NStatistic v-if="card.latest?.status_code != null" label="状态码" :value="card.latest.status_code" />
              </NSpace>
            </NSpace>
          </NCard>
        </NGi>
      </NGrid>
    </NSpin>
  </div>
</template>
