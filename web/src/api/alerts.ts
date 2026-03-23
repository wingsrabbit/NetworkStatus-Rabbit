import api from './index'
import type { AlertChannel, AlertHistory, PaginatedResponse } from '@/types'

export function getAlertChannels() {
  return api.get<{ items: AlertChannel[] }>('/alerts/channels')
}

export function createAlertChannel(data: { name: string; url: string; type?: string; enabled?: boolean }) {
  return api.post<{ channel: AlertChannel }>('/alerts/channels', data)
}

export function updateAlertChannel(id: string, data: Partial<{ name: string; url: string; type: string; enabled: boolean }>) {
  return api.put<{ channel: AlertChannel }>(`/alerts/channels/${id}`, data)
}

export function deleteAlertChannel(id: string) {
  return api.delete(`/alerts/channels/${id}`)
}

export function testAlertChannel(id: string) {
  return api.post(`/alerts/channels/${id}/test`)
}

export function getAlertHistory(params?: { page?: number; per_page?: number; task_id?: string; event_type?: string }) {
  return api.get<PaginatedResponse<AlertHistory>>('/alerts/history', { params })
}
