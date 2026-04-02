# v0.135 更新日志

日期：2026-04-02

## Bug 修复

1. **MTR 探测次数修正**
   - `mtr_probe.py` count 从 5 改为 1，每次探测仅发一包，SNT 精准反映实际探测轮次。

2. **MTR 探测速度优化**
   - `monitor_mtr.py` 添加 `-G 0.5 -Z 1 -i 0.1` 参数，单次探测耗时从 ~6s 降至 ~0.6s。

3. **重置统计修复**
   - 修复重置后前端自动刷新重新合并全部历史数据导致 SNT 不变的问题。
   - `resetMtrStats()` 将 `mtrStartTime` 设为当前时间而非 null，阻止 fetchData 重新加载历史。
   - `fetchData()` 拆为三分支：首次加载 / 重置后 / 常规刷新，重置后仅合并 reset_time 之后的数据。

4. **任务开始时间显示修复**
   - "开始于" 时间从 `taskInfo.created_at` 取值，而非首条数据时间戳。
   - 重置后更新为服务端下发的 `reset_time`。

## 新增功能

1. **重置统计完整管线**
   - 前端发 `dashboard:reset_mtr` → 服务端发 `center:restart_task` 给 Agent → Agent 停止并重启任务 → 服务端广播 `dashboard:mtr_reset` 回前端。
   - `dashboard_handler.py` 新增 `on_dashboard_reset_mtr`。
   - `ws_client.py` 新增 `center:restart_task` 处理。

2. **内部 MTR 测试任务**
   - 新增 Agent1 → Agent2 (123.253.226.12) ICMP MTR 测试任务，间隔 5s。

## 验证结果

- ICMP MTR：1pt/s，延迟 ~1.0ms（外部 8.8.8.8）
- TCP MTR：1pt/10s，延迟 ~10.1ms（外部 8.8.8.8:443）
- UDP MTR：1pt/10s，延迟 ~10.1ms（外部 8.8.8.8:53）
- 内部 MTR：1 hop，延迟 ~0.3ms（Agent1→Agent2）

## 版本变更

- `version.py`：0.134.0 → 0.135.0
- `web/package.json`：0.134.0 → 0.135.0
