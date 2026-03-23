import api from './index'
import type { DashboardCard, ProbeResult } from '@/types'

export function getDashboard(params?: {
  protocol?: string
  label?: string
  status?: string
  alert_status?: string
  search?: string
}) {
  return api.get<{ cards: DashboardCard[]; summary: Record<string, any> }>('/data/dashboard', { params })
}

export function getTaskData(taskId: string, params?: { range?: string; start?: string; end?: string }) {
  return api.get<{ data: ProbeResult[] }>(`/data/task/${taskId}`, { params })
}

export function getTaskStats(taskId: string, params?: { range?: string }) {
  return api.get<{ stats: Record<string, any> }>(`/data/task/${taskId}/stats`, { params })
}
