import api from './index'
import type { DashboardTask, DashboardNode, DashboardSummary, ProbeResult, AlertHistory } from '@/types'

export function getDashboard(params?: {
  protocol?: string
  label?: string
  status?: string
  alert_status?: string
  search?: string
}) {
  return api.get<{ nodes: DashboardNode[]; tasks: DashboardTask[]; summary: DashboardSummary }>('/data/dashboard', { params })
}

export function getTaskData(taskId: string, params?: { range?: string; start?: string; end?: string }) {
  return api.get<{ data: ProbeResult[] }>(`/data/task/${taskId}`, { params })
}

export function getTaskStats(taskId: string, params?: { range?: string }) {
  return api.get<{ stats: Record<string, any> }>(`/data/task/${taskId}/stats`, { params })
}

export function getTaskAlerts(taskId: string, params?: { range?: string }) {
  return api.get<{ alerts: AlertHistory[] }>(`/data/task/${taskId}/alerts`, { params })
}
