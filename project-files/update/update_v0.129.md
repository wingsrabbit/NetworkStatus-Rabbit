# v0.129 更新日志

日期：2026-03-28

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 内部 UDP 任务终于具备目标侧回显服务。
   - Agent 内建 UDP echo server，默认监听 `0.0.0.0:9999`。
   - 认证时上报 `capabilities.udp_echo_port`。
   - 服务端对内部 UDP 任务改为使用目标节点 echo 端口。

2. 后端镜像补齐 Agent 源码与共享版本文件。
   - `Dockerfile`、`Dockerfile.agent`、打包端点统一包含 `agent/`、`requirements-agent.txt`、`version.py`。
   - 增加 `GET /api/version` 公开接口。

## 版本变更

1. 新增根级 `version.py`，统一维护版本号。
2. `web/package.json`：0.128.0 → 0.129.0
3. Agent 上报版本改为读取 `APP_VERSION`