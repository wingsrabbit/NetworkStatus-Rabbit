# v0.131 更新日志 (2026-03-28)

## Bug 修复

### 1. 前端聚合数据失败标记不显示
- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：TCP/DNS 图表中使用 `p.success === false` 判断失败，但聚合数据（24h+）中 success 为 float (0.0~1.0)，JS 严格等于不匹配 0.0  
- **修复**：新增 `isProbeFailure()` helper 函数，同时处理 boolean false 和 `typeof number && < 1`

### 2. API 无效 range 参数导致 500
- **文件**：`server/api/data.py`
- **问题**：传入 `'999x'` 等非法 range 值直接进入 InfluxDB Flux 查询导致 500 内部错误
- **修复**：在 task_data / task_stats / task_alerts 三个端点添加 `^\d+[mhd]$` 正则校验，无效输入返回 400

### 3. HTTP 计时累积值误叠加
- **文件**：`agent/probes/http_probe.py`、`agent/tools/curl_ping/monitor_curl.py`
- **问题**：curl 的 time_connect / time_pretransfer / time_starttransfer 是累积值，直接存储导致阶段堆叠图总和远超实际
- **修复**：计算增量值 tcp=connect-dns, tls=pretransfer-connect, ttfb=starttransfer-pretransfer；新增 pretransfer_time 字段

### 4. InfluxDB 下采样任务字段不完整
- **文件**：`scripts/setup-influxdb.py`、InfluxDB 任务
- **问题**：下采样仅聚合 latency/packet_loss/jitter 三个字段，HTTP 的 dns_time/tcp_time/tls_time/ttfb/total_time 及 success 字段缺失
- **修复**：重建下采样任务，覆盖所有数值字段 + boolean→float 转换

### 5. 清理
- `docker-compose.yml` 移除废弃的 `version: '3.8'` 字段
