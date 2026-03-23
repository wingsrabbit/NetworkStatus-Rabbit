import api from './index'
import type { Settings } from '@/types'

export function getSettings() {
  return api.get<{ settings: Settings }>('/settings')
}

export function updateSettings(data: Settings) {
  return api.put<{ settings: Settings }>('/settings', data)
}
