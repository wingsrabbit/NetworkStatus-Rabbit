# v0.128 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心更新

1. 上游探测工具 vendor 化纳入仓库。
   - 新增 `agent/vendor/Network-Monitoring-Tools/`。
   - 打包端点会将 vendor 代码随 Agent 一起分发。

2. `network_tools` 重写为 vendor 薄代理。
   - 五个协议子模块统一改为“参数适配 + 调上游 + 结果归一化”的模式。
   - `probes/` 层不再承担底层探测逻辑。

3. TCP self-test 加强。
   - 从简单检查 API 存在，升级为实际进行一次最小 `socket.create_connection()` 验证。

## 影响

1. 探测核心与底层工具来源进一步统一。
2. 后续升级底层探测工具时边界更清晰。