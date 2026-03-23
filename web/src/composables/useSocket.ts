import { ref, onUnmounted } from 'vue'
import { io, type Socket } from 'socket.io-client'
import { useDashboardStore } from '@/stores/dashboard'

const socket = ref<Socket | null>(null)

export function useSocket() {
  function connect() {
    if (socket.value?.connected) return

    socket.value = io('/dashboard', {
      path: '/socket.io',
      withCredentials: true,
      transports: ['websocket', 'polling'],
    })

    const s = socket.value

    s.on('connect', () => {
      console.log('[WS] Dashboard connected')
    })

    s.on('disconnect', (reason: string) => {
      console.log('[WS] Dashboard disconnected:', reason)
    })

    s.on('connect_error', (err: any) => {
      const code = err?.data?.code || 'UNKNOWN'
      console.error('[WS] Connection error:', code, err.message)
    })

    // BUG-03: Listen to probe_snapshot for real-time dashboard updates
    s.on('dashboard_probe_snapshot', (data: any) => {
      const store = useDashboardStore()
      if (data.tasks) {
        store.updateTaskSnapshot(data.tasks)
      }
    })

    s.on('dashboard_task_detail', (data: any) => {
      // Only used by TaskDetailView subscribers, not dashboard
    })

    s.on('dashboard_node_status', (data: any) => {
      const store = useDashboardStore()
      store.updateNodeStatus(data.node_id, data.status)
    })

    s.on('dashboard_alert', (data: any) => {
      const store = useDashboardStore()
      // BUG-06: Use 'alerting' not 'triggered'
      store.updateTask(data.task_id, {
        alert_status: data.event_type === 'alert' ? 'alerting' : 'normal',
      })
    })
  }

  function disconnect() {
    socket.value?.disconnect()
    socket.value = null
  }

  function subscribeTask(taskId: string) {
    socket.value?.emit('dashboard_subscribe_task', { task_id: taskId })
  }

  function unsubscribeTask(taskId: string) {
    socket.value?.emit('dashboard_unsubscribe_task', { task_id: taskId })
  }

  return { socket, connect, disconnect, subscribeTask, unsubscribeTask }
}
