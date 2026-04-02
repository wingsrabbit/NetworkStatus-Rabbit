# v0.130 更新日志

日期：2026-03-28

来源：由 `project-files/update.md` 拆分整理。

## 核心更新

1. 项目结构重构，直接使用 `agent/tools/`。
   - 删除旧的 `agent/vendor/` 和 `agent/network_tools/` 层。
   - 五个探针直接调用 `agent.tools` 下的底层实现。

2. 端口拆分为 9191 和 9192。
   - 9191 负责 Web、API 和 Dashboard WebSocket。
   - 9192 专门给 Agent 数据通道使用。

3. Agent `listen-port` 通用化。
   - 旧的 UDP echo 端口命名被统一为 `--listen-port`。
   - 一个端口同时承载 TCP echo 和 UDP echo。

4. 时间窗口和刷新节拍重新调整。
   - 范围精简为 30m、1h、24h、3d、7d、30d。
   - bucket 选择、自动刷新频率和横轴格式随之同步更新。

5. 仪表盘“最后更新”时间戳修复。

6. Docker 部署链路重构。
   - `Dockerfile` 改为多阶段构建。
   - 新增 `scripts/entrypoint.sh`。
   - 前端构建产物通过 named volume 交给 nginx。

7. 清理任务创建中的端口硬编码逻辑。

## 版本变更

1. `version.py`：0.129.0 → 0.130.0
2. `web/package.json`：0.129.0 → 0.130.0