import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardTask, DashboardNode, DashboardSummary } from '@/types'
import { getDashboard } from '@/api/data'

export const useDashboardStore = defineStore('dashboard', () => {
  const tasks = ref<DashboardTask[]>([])
  const nodes = ref<DashboardNode[]>([])
  const summary = ref<DashboardSummary>({
    total_nodes: 0, online_nodes: 0, offline_nodes: 0,
    total_tasks: 0, alerting_tasks: 0,
  })
  const loading = ref(false)
  const filters = ref<{
    protocol?: string
    label?: string
    status?: string
    alert_status?: string
    search?: string
  }>({})

  async function fetchDashboard() {
    loading.value = true
    try {
      const res = await getDashboard(filters.value)
      tasks.value = res.data.tasks
      nodes.value = res.data.nodes
      summary.value = res.data.summary
    } finally {
      loading.value = false
    }
  }

  function updateTaskSnapshot(taskSnapshots: Record<string, any>) {
    for (const task of tasks.value) {
      const snap = taskSnapshots[task.task_id]
      if (snap) {
        task.latest = {
          latency: snap.last_latency,
          packet_loss: snap.last_packet_loss,
          jitter: null,
          success: snap.last_success,
          status_code: null,
          timestamp: null,
        }
        task.alert_status = snap.status === 'alerting' ? 'alerting' : 'normal'
      }
    }
  }

  function updateTask(taskId: string, data: Partial<DashboardTask>) {
    const idx = tasks.value.findIndex((t) => t.task_id === taskId)
    if (idx !== -1) {
      tasks.value[idx] = { ...tasks.value[idx], ...data }
    }
  }

  function updateNodeStatus(nodeId: string, status: string) {
    const node = nodes.value.find((n) => n.id === nodeId)
    if (node) {
      node.status = status
    }
  }

  return { tasks, nodes, summary, loading, filters, fetchDashboard, updateTaskSnapshot, updateTask, updateNodeStatus }
})
