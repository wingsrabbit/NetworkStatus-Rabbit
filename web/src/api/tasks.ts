import api from './index'
import type { ProbeTask, PaginatedResponse } from '@/types'

export function getTasks(params?: { page?: number; per_page?: number; node_id?: string; protocol?: string }) {
  return api.get<PaginatedResponse<ProbeTask>>('/tasks', { params })
}

export function createTask(data: Partial<ProbeTask>) {
  return api.post<{ task: ProbeTask }>('/tasks', data)
}

export function updateTask(id: number, data: Partial<ProbeTask>) {
  return api.put<{ task: ProbeTask }>(`/tasks/${id}`, data)
}

export function deleteTask(id: number) {
  return api.delete(`/tasks/${id}`)
}

export function toggleTask(id: number) {
  return api.put<{ task: ProbeTask }>(`/tasks/${id}/toggle`)
}
