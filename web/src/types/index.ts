export interface User {
  id: string
  username: string
  role: 'admin' | 'readonly'
  created_at: string
  created_by: string | null
}

export interface Node {
  id: string
  name: string
  token?: string
  label_1: string
  label_2: string
  label_3: string
  status: 'online' | 'offline'
  last_seen: string | null
  created_at: string
  enabled: boolean
  config_version: number
  capabilities: NodeCapabilities | null
  agent_version: string | null
  public_ip: string | null
  private_ip: string | null
}

export interface NodeCapabilities {
  protocols: string[]
  unsupported: string[]
  unsupported_reasons: Record<string, string>
  os?: string
}

export interface ProbeTask {
  id: string
  name: string
  source_node_id: string
  source_node_name?: string
  protocol: 'icmp' | 'tcp' | 'udp' | 'http' | 'dns'
  target_type: 'internal' | 'external'
  target_node_id: string | null
  target_address: string
  target_port: number | null
  interval: number
  timeout: number
  enabled: boolean
  created_at: string
  alert_latency_threshold: number | null
  alert_loss_threshold: number | null
  alert_fail_count: number | null
  alert_eval_window: number
  alert_trigger_count: number
  alert_recovery_count: number
  alert_cooldown_seconds: number
}

export interface AlertChannel {
  id: string
  name: string
  type: 'webhook'
  url: string
  enabled: boolean
  created_at: string
}

export interface AlertHistory {
  id: string
  task_id: string
  task_name?: string
  event_type: 'alert' | 'recovery'
  metric: string
  actual_value: number
  threshold: number
  notified: boolean
  created_at: string
}

export interface ProbeResult {
  timestamp: string
  latency: number | null
  packet_loss: number | null
  jitter: number | null
  success: boolean | null
  dns_time: number | null
  tcp_time: number | null
  tls_time: number | null
  ttfb: number | null
  total_time: number | null
  status_code: number | null
  resolved_ip: string | null
}

export interface DashboardTask {
  task_id: string
  name: string
  source_node: string
  target: string
  protocol: string
  enabled: boolean
  latest: {
    latency: number | null
    packet_loss: number | null
    jitter: number | null
    success: boolean | null
    status_code: number | null
    timestamp: string | null
  } | null
  alert_status: 'normal' | 'alerting'
}

export interface DashboardNode {
  id: string
  name: string
  status: string
  labels: (string | null)[]
  capabilities: any
  last_seen: string | null
}

export interface DashboardSummary {
  total_nodes: number
  online_nodes: number
  offline_nodes: number
  total_tasks: number
  alerting_tasks: number
}

export interface Pagination {
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface PaginatedResponse<T> {
  items: T[]
  pagination: Pagination
}

export interface ApiError {
  error: {
    code: number
    type: string
    message: string
  }
}

export interface Settings {
  [key: string]: any
}
