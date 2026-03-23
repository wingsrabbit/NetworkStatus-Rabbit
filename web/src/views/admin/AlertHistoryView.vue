<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NDataTable, NTag, NSpace, NSelect, useMessage, NPageHeader
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { getAlertHistory } from '@/api/alerts'
import type { AlertHistory } from '@/types'
import dayjs from 'dayjs'

const message = useMessage()
const items = ref<AlertHistory[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const eventFilter = ref<string | null>(null)

const eventOptions = [
  { label: '全部', value: '' },
  { label: '触发', value: 'triggered' },
  { label: '恢复', value: 'recovered' },
]

async function fetchHistory() {
  loading.value = true
  try {
    const params: any = { page: page.value, per_page: 20 }
    if (eventFilter.value) params.event_type = eventFilter.value
    const res = await getAlertHistory(params)
    items.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

const columns: DataTableColumns<AlertHistory> = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '任务ID', key: 'task_id', width: 80 },
  {
    title: '事件', key: 'event_type', width: 80,
    render: (row) => h(NTag, { type: row.event_type === 'triggered' ? 'error' : 'success', size: 'small' }, { default: () => row.event_type === 'triggered' ? '触发' : '恢复' }),
  },
  { title: '指标', key: 'metric', width: 100 },
  {
    title: '实际值', key: 'actual_value', width: 100,
    render: (row) => row.actual_value?.toFixed(2) ?? '-',
  },
  {
    title: '阈值', key: 'threshold', width: 100,
    render: (row) => `${row.operator} ${row.threshold}`,
  },
  {
    title: '通知', key: 'notified', width: 70,
    render: (row) => h(NTag, { type: row.notified ? 'success' : 'warning', size: 'small' }, { default: () => row.notified ? '是' : '否' }),
  },
  {
    title: '时间', key: 'created_at', width: 180,
    render: (row) => dayjs(row.created_at).format('YYYY-MM-DD HH:mm:ss'),
  },
]

onMounted(fetchHistory)
</script>

<template>
  <div>
    <NPageHeader title="告警历史" />
    <NSpace style="margin: 16px 0">
      <NSelect v-model:value="eventFilter" :options="eventOptions" placeholder="事件类型" style="width: 140px" clearable @update:value="fetchHistory" />
    </NSpace>

    <NDataTable
      :columns="columns"
      :data="items"
      :loading="loading"
      :pagination="{ page, pageSize: 20, itemCount: total, onChange: (p: number) => { page = p; fetchHistory() } }"
    />
  </div>
</template>
