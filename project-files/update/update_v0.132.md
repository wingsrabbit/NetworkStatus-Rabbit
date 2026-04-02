# v0.132 更新日志

日期：来源文档记录为 2025-07

来源：由 `project-files/update_v0.132.md` 整理。

## 新功能

1. 新增根目录 `install.sh` 一键安装脚本。
   - 同时支持服务端模式和 Agent 模式。

2. 新增 `update.sh` 热更新脚本。
   - 后端改动时直接热拷贝并重启。
   - 前端改动时自动触发重建。

3. 仪表盘支持卡片/列表双视图。
   - 加入分页。
   - 任务默认按首字母排序。
   - 搜索与筛选会自动重置页码。

4. TCP/UDP 图表补充抖动展示。
   - TCP 使用窗口抖动。
   - UDP 优先使用后端 jitter，再回退到窗口计算。

## 改进

1. InfluxDB 不再对外暴露端口。
2. Compose 开始支持 `NSR_WEB_PORT` 与 `NSR_AGENT_PORT` 环境变量。
3. README 按 Docker-first 方式重写。

## 文件层面

1. 新增 `install.sh`
2. 新增 `update.sh`
3. 修改 `docker-compose.yml`
4. 重写 `README.md`
5. 版本号提升到 0.132.0