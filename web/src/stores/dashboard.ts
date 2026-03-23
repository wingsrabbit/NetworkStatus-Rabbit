import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardCard } from '@/types'
import { getDashboard } from '@/api/data'

export const useDashboardStore = defineStore('dashboard', () => {
  const cards = ref<DashboardCard[]>([])
  const loading = ref(false)
  const filters = ref<{
    protocol?: string
    label?: string
    status?: string
    alert_status?: string
    search?: string
  }>({})

  async function fetchCards() {
    loading.value = true
    try {
      const res = await getDashboard(filters.value)
      cards.value = res.data.cards
    } finally {
      loading.value = false
    }
  }

  function updateCard(taskId: string, data: Partial<DashboardCard>) {
    const idx = cards.value.findIndex((c) => c.task_id === taskId)
    if (idx !== -1) {
      cards.value[idx] = { ...cards.value[idx], ...data }
    }
  }

  function updateNodeStatus(nodeId: string, status: string) {
    for (const card of cards.value) {
      if (card.source_node_id === nodeId) {
        card.source_node_status = status
      }
    }
  }

  return { cards, loading, filters, fetchCards, updateCard, updateNodeStatus }
})
