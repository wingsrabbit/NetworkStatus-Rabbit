import api from './index'
import type { Settings } from '@/types'

export function getPublicSettings() {
  return api.get<{ site_title: string; site_subtitle: string }>('/settings/public')
}

export function getSettings() {
  return api.get<{ settings: Settings }>('/settings')
}

export function updateSettings(data: Settings) {
  return api.put<{ settings: Settings }>('/settings', data)
}
