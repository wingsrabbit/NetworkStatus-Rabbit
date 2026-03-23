import api from './index'
import type { User } from '@/types'

export function login(username: string, password: string) {
  return api.post<{ user: User }>('/auth/login', { username, password })
}

export function logout() {
  return api.post('/auth/logout')
}

export function getMe() {
  return api.get<{ user: User }>('/auth/me')
}
