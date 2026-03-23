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

    s.on('dashboard:task_detail', (data: any) => {
      const store = useDashboardStore()
      store.updateCard(data.task_id, {
        latest: data.result,
      })
    })

    s.on('dashboard:node_status', (data: any) => {
      const store = useDashboardStore()
      store.updateNodeStatus(data.node_id, data.status)
    })

    s.on('dashboard:alert', (data: any) => {
      const store = useDashboardStore()
      store.updateCard(data.task_id, {
        alert_status: data.event_type === 'triggered' ? 'triggered' : 'normal',
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
