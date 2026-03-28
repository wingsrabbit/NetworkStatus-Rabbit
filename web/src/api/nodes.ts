import api from './index'
import type { Node, PaginatedResponse } from '@/types'

export function getNodes(params?: { page?: number; per_page?: number; status?: string; search?: string }) {
  return api.get<PaginatedResponse<Node>>('/nodes', { params })
}

export function createNode(data: { name: string; label_1?: string; label_2?: string; label_3?: string }) {
  return api.post<{ node: Node }>('/nodes', data)
}

export function updateNode(id: string, data: Partial<Node>) {
  return api.put<{ node: Node }>(`/nodes/${id}`, data)
}

export function deleteNode(id: string) {
  return api.delete(`/nodes/${id}`)
}

export function getDeployCommand(id: string) {
  return api.get<{ script_command: string; docker_command: string; docker_command_listen: string; node_id: string }>(`/nodes/${id}/deploy-command`)
}
