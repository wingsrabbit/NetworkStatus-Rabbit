import api from './index'
import type { DashboardCard, ProbeResult } from '@/types'

export function getDashboard(params?: {
  protocol?: string
  label?: string
  status?: string
  alert_status?: string
  search?: string
}) {
  return api.get<{ cards: DashboardCard[] }>('/data/dashboard', { params })
}

export function getTaskData(taskId: number, params?: { range?: string; start?: string; end?: string }) {
  return api.get<{ task_id: number; points: ProbeResult[] }>(`/data/task/${taskId}`, { params })
}

export function getTaskStats(taskId: number, params?: { range?: string }) {
  return api.get<{ task_id: number; stats: Record<string, any> }>(`/data/task/${taskId}/stats`, { params })
}
