# v0.132.0 更新日志

**发布日期**: 2025-07

---

## 新功能

### Docker 一键安装
- 新增 `install.sh` 一键安装脚本，支持服务端和 Agent 两种模式
- 服务端模式：自动安装 Docker、克隆代码、生成随机密钥、构建并启动
- Agent 模式：`bash install.sh agent --server IP --port 9192 --node-id ID --token TOKEN`
- 安装命令：`bash <(curl -sL https://raw.githubusercontent.com/wingsrabbit/NetworkStatus-Rabbit/NetworkStatus-Rabbit-NG/install.sh)`

### 热更新支持
- 新增 `update.sh` 热更新脚本
- 仅后端变动时，docker cp + restart，无需重建镜像
- 自动检测前端变动，需要时自动触发完整重建
- 显示旧版本 → 新版本变化

### 仪表盘增强
- 新增卡片/列表双视图切换（网格▦ / 列表☰）
- 新增分页功能，支持 10 / 20 / 50 条每页
- 任务默认按名称首字母排序
- 搜索/筛选时自动重置页码

### TCP / UDP 抖动显示
- TCP 图表新增窗口抖动曲线（橙色虚线），计算逻辑与 ICMP 一致
- UDP 图表新增抖动曲线，优先使用后端 jitter 字段，回退至窗口抖动计算
- 所有协议图表风格统一

## 改进

### InfluxDB 安全
- InfluxDB 不再对外暴露端口，仅在 Docker 内部网络中使用
- docker-compose.yml 中移除 InfluxDB ports 映射

### docker-compose.yml
- 移除已废弃的 `version: '3.8'` 字段
- Web 端口和 Agent 端口支持环境变量配置（`NSR_WEB_PORT`、`NSR_AGENT_PORT`）

### README 重写
- 参考 ServerStatus-Rabbit 风格完全重写 README
- Docker-first 部署方案，一键安装命令
- 详细的服务端/Agent/更新/CLI 文档
- 架构图 + 协议指标说明表

## 文件变更清单

| 文件 | 变更类型 |
|------|---------|
| `install.sh` | 新增 |
| `update.sh` | 新增 |
| `docker-compose.yml` | 修改 |
| `README.md` | 重写 |
| `version.py` | 版本号 0.130.0 → 0.132.0 |
| `web/src/views/DashboardView.vue` | 重写（视图切换/分页/排序） |
| `web/src/views/TaskDetailView.vue` | 修改（TCP/UDP 抖动） |
| `project-files/update_v0.131.md` | 新增 |
| `project-files/update_v0.132.md` | 新增 |
