import api from './index'
import type { User, PaginatedResponse } from '@/types'

export function getUsers(params?: { page?: number; per_page?: number }) {
  return api.get<PaginatedResponse<User>>('/users', { params })
}

export function createUser(data: { username: string; password: string; role?: string }) {
  return api.post<{ user: User }>('/users', data)
}

export function updateUserRole(id: string, role: string) {
  return api.put<{ user: User }>(`/users/${id}/role`, { role })
}

export function deleteUser(id: string) {
  return api.delete(`/users/${id}`)
}
