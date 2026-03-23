import api from './index'
import type { AlertChannel, AlertHistory, PaginatedResponse } from '@/types'

export function getAlertChannels() {
  return api.get<{ channels: AlertChannel[] }>('/alerts/channels')
}

export function createAlertChannel(data: Partial<AlertChannel>) {
  return api.post<{ channel: AlertChannel }>('/alerts/channels', data)
}

export function updateAlertChannel(id: number, data: Partial<AlertChannel>) {
  return api.put<{ channel: AlertChannel }>(`/alerts/channels/${id}`, data)
}

export function deleteAlertChannel(id: number) {
  return api.delete(`/alerts/channels/${id}`)
}

export function testAlertChannel(id: number) {
  return api.post(`/alerts/channels/${id}/test`)
}

export function getAlertHistory(params?: { page?: number; per_page?: number; task_id?: number; event_type?: string }) {
  return api.get<PaginatedResponse<AlertHistory>>('/alerts/history', { params })
}
