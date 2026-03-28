import { ref, onUnmounted } from 'vue'
import { io, type Socket } from 'socket.io-client'
import { useDashboardStore } from '@/stores/dashboard'
import { useRouter } from 'vue-router'

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
      if (code === 'WS_AUTH_FAILED') {
        const router = useRouter()
        router.push('/login')
      }
    })

    s.on('error', (data: any) => {
      const code = data?.code || 'UNKNOWN'
      console.error('[WS] Error event:', code, data?.message)
      if (code === 'WS_AUTH_FAILED' || code === 'WS_TOKEN_EXPIRED') {
        const router = useRouter()
        router.push('/login')
      }
    })

    // BUG-03: Listen to probe_snapshot for real-time dashboard updates
    s.on('dashboard:probe_snapshot', (data: any) => {
      const store = useDashboardStore()
      if (data.tasks) {
        store.updateTaskSnapshot(data.tasks)
        ;(window as any).__nsr_markDataReceived?.()
      }
    })

    s.on('dashboard:task_detail', (data: any) => {
      // Only used by TaskDetailView subscribers, not dashboard
    })

    s.on('dashboard:node_status', (data: any) => {
      const store = useDashboardStore()
      store.updateNodeStatus(data.node_id, data.status)
    })

    s.on('dashboard:alert', (data: any) => {
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
    socket.value?.emit('dashboard:subscribe_task', { task_id: taskId })
  }

  function unsubscribeTask(taskId: string) {
    socket.value?.emit('dashboard:unsubscribe_task', { task_id: taskId })
  }

  return { socket, connect, disconnect, subscribeTask, unsubscribeTask }
}
