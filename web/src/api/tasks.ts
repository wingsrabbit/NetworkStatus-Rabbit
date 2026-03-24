import api from './index'
import type { ProbeTask, PaginatedResponse } from '@/types'

export function getTask(id: string) {
  return api.get<{ task: ProbeTask }>(`/tasks/${id}`)
}

export function getTasks(params?: { page?: number; per_page?: number; node_id?: string; protocol?: string }) {
  return api.get<PaginatedResponse<ProbeTask>>('/tasks', { params })
}

export function createTask(data: Partial<ProbeTask>) {
  return api.post<{ task: ProbeTask }>('/tasks', data)
}

export function updateTask(id: string, data: Partial<ProbeTask>) {
  return api.put<{ task: ProbeTask }>(`/tasks/${id}`, data)
}

export function deleteTask(id: string) {
  return api.delete(`/tasks/${id}`)
}

export function toggleTask(id: string, enabled: boolean) {
  return api.put<{ task: ProbeTask }>(`/tasks/${id}/toggle`, { enabled })
}
