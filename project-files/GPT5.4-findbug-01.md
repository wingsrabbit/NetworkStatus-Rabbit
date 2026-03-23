# NetworkStatus-Rabbit — Bug 发现报告（第一轮）

> **审查人**：GPT-5.4  
> **审查日期**：2026-03-23  
> **参考规格**：PROJECT.md v1.5  
> **审查范围**：server/（后端）、agent/（探测节点）、nginx/、docker-compose.yml、Dockerfile

---

## 总结

本次审查共发现 **4 个严重 Bug**（会导致运行时崩溃/功能完全失效）和 **9 个设计偏离**（与 PROJECT.md 规格不符）。

---

## 一、严重 Bug（运行时崩溃 / 功能完全失效）

---

### BUG-01 ⛔ `push_alert` 函数签名不匹配

**文件**：`server/services/alert_service.py:165` 与 `server/ws/dashboard_handler.py:102`

**现象**：

```python
# alert_service.py 第165行 — 调用方（4个参数）
push_alert(task_id, event_type, metric, actual_value)

# dashboard_handler.py 第102行 — 被调用方（只接受1个参数）
def push_alert(alert_data):
    socketio.emit('dashboard:alert', alert_data, namespace='/dashboard')
```

**后果**：每次告警触发时都会抛出 `TypeError: push_alert() takes 1 positional argument but 4 were given`，导致告警推送功能完全失效，前端无法收到任何告警通知。

**修改建议**：

方案一：修改 `alert_service.py` 调用方，将4个参数打包成字典传入：

```python
push_alert({
    'task_id': task_id,
    'event_type': event_type,
    'metric': metric,
    'actual_value': actual_value,
})
```

方案二：修改 `dashboard_handler.py` 的函数签名：

```python
def push_alert(task_id, event_type, metric, actual_value):
    socketio.emit('dashboard:alert', {
        'task_id': task_id,
        'event_type': event_type,
        'metric': metric,
        'actual_value': actual_value,
    }, namespace='/dashboard')
```

---

### BUG-02 ⛔ `AlertHistory` 构造函数传入不存在的字段 `operator`

**文件**：`server/services/alert_service.py:113-122`

**现象**：

```python
# alert_service.py — 构造时传入了 operator= 参数
history = AlertHistory(
    task_id=task_id,
    event_type=event_type,
    metric=metric,
    actual_value=actual_value,
    threshold=threshold,
    operator=alert_operator,   # ← 这个字段不存在！
    notified=False,
    created_at=datetime.now(timezone.utc),
)
```

但 `AlertHistory` 模型（`server/models/alert.py`）中没有 `operator` 列：

```python
class AlertHistory(db.Model):
    id, task_id, event_type, metric, actual_value, threshold,
    message, alert_started_at, duration_seconds, notified, created_at
    # 没有 operator 列
```

**后果**：每次写入告警历史时都会抛出 `TypeError`，告警历史记录功能完全失效。

**修改建议**：从 `AlertHistory(...)` 构造调用中删除 `operator=alert_operator` 参数。如果业务上需要记录告警比较符，应先在模型中新增 `operator` 列。

---

### BUG-03 ⛔ `alert_service.py` 引用了 `ProbeTask` 中不存在的字段

**文件**：`server/services/alert_service.py:48-58`

**现象**：

```python
# alert_service.py
task = db.session.get(ProbeTask, task_id)
if not task or not task.alert_enabled:    # ← alert_enabled 不存在
    return None

alert_metric = task.alert_metric          # ← alert_metric 不存在
alert_operator = task.alert_operator      # ← alert_operator 不存在
alert_threshold = task.alert_threshold    # ← alert_threshold 不存在
```

而 `ProbeTask` 模型（`server/models/task.py`）的告警字段实际是：

```python
alert_latency_threshold = db.Column(db.Float, nullable=True)
alert_loss_threshold = db.Column(db.Float, nullable=True)
alert_fail_count = db.Column(db.Integer, nullable=True)
alert_eval_window = db.Column(db.Integer, nullable=False, default=5)
alert_trigger_count = db.Column(db.Integer, nullable=False, default=3)
alert_recovery_count = db.Column(db.Integer, nullable=False, default=3)
alert_cooldown_seconds = db.Column(db.Integer, nullable=False, default=300)
```

**后果**：每次调用 `evaluate_probe_result` 时都会抛出 `AttributeError`，**整个告警系统不可用**。

**修改建议**：重写 `evaluate_probe_result` 函数，改为基于 `alert_latency_threshold`、`alert_loss_threshold`、`alert_fail_count` 这3个字段各自独立评估（参见下文 BUG-06 的窗口化方案）。

---

### BUG-04 ⛔ Webhook 通道 URL 通过不存在的字段读取

**文件**：`server/services/alert_service.py:131-138`

**现象**：

```python
for channel in channels:
    if channel.type == 'webhook':
        url = channel.config_data.get('url') if hasattr(channel, 'config_data') else None
        if not url:
            try:
                config = json.loads(channel.config) if isinstance(channel.config, str) else channel.config
                url = config.get('url')
            except Exception:
                continue
```

但 `AlertChannel` 模型（`server/models/alert.py`）中没有 `config_data` 或 `config` 字段，URL 直接存在 `url` 字段：

```python
class AlertChannel(db.Model):
    id, name, type, url, enabled, created_at  # url 是直接字段
```

**后果**：`hasattr(channel, 'config_data')` 永远为 `False`，`channel.config` 也不存在，`url` 最终为 `None`，**所有 Webhook 通知永远无法发出**。

**修改建议**：将 URL 读取逻辑改为直接访问 `channel.url`：

```python
for channel in channels:
    if channel.type == 'webhook' and channel.url:
        try:
            send_webhook(channel.url, payload)
            notified = True
        except Exception as e:
            logger.error(f"Webhook send failed to {channel.url}: {e}")
```

---

## 二、设计偏离（与 PROJECT.md 规格不符）

---

### BUG-05 📐 InfluxDB Measurement 名称与规格不符

**文件**：`server/services/influx_service.py:42` 及 `server/services/influx_service.py:89, 122`

**现象**：代码写入和查询的 Measurement 名称为 `probe_result`（单数）：

```python
point = Point('probe_result')  # 写入

# 查询也使用同一名称
filter(fn: (r) => r._measurement == "probe_result")
```

**规格要求**（PROJECT.md 6.1节）：Measurement 名称为 `probe_results`（**复数**）。

**影响**：虽然内部写入和查询暂时一致不会报错，但与规格文档不符，且将来若有其他工具或脚本按规格中的 `probe_results` 查询则会返回空结果。

**修改建议**：将所有 `'probe_result'` 改为 `'probe_results'`（包括 `Point('probe_result')` 和 Flux 查询中的 `r._measurement == "probe_result"`）。

---

### BUG-06 📐 告警评估算法偏离规格（连续计数 ≠ 滑动窗口）

**文件**：`server/services/alert_service.py:76-103`

**现象**：代码使用 `_breach_counts` 对连续超阈值次数计数：

```python
if is_breach:
    _breach_counts[task_id] += 1
    _ok_counts[task_id] = 0
else:
    _ok_counts[task_id] += 1
    _breach_counts[task_id] = 0

if state == 'normal':
    if _breach_counts[task_id] >= trigger_count:
        # 告警
```

**规格要求**（PROJECT.md 12.1节）：

> 延迟告警：**最近 N 次探测中有 ≥ M 次超阈值**才告警（滑动窗口）

这两种算法有明显差异：
- **连续计数**：只要中间有一次正常，计数就重置为 0，难以触发告警。
- **滑动窗口**：看最近 N 次的总体表现，偶尔1次正常不会重置窗口统计。

另外，`_windows` 字典在代码中有定义但从未参与评估逻辑（完全没有被使用）。

**还有**，规格要求对 3 个指标（`latency`/`packet_loss`/`continuous_fail`）**分别独立评估**，当前代码只能处理单个 `alert_metric`（而且该字段不存在，见 BUG-03）。

**修改建议**：重构告警评估逻辑，改为对每个任务分别维护3个指标的滑动窗口（用 `deque(maxlen=N)`），在窗口满足条件时触发告警：

```python
# 维护结构：task_id -> {metric: deque(maxlen=eval_window)}
_windows: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque()))

def evaluate_window(task_id, metrics):
    task = ProbeTask.query.get(task_id)
    
    results = []
    
    # 延迟评估
    if task.alert_latency_threshold is not None and metrics.get('latency') is not None:
        window = _get_window(task_id, 'latency', task.alert_eval_window)
        window.append(metrics['latency'] > task.alert_latency_threshold)
        breach_count = sum(window)
        if breach_count >= task.alert_trigger_count:
            results.append(('latency', metrics['latency'], task.alert_latency_threshold))
    
    # 丢包评估（类似）
    # 连续失败评估（类似）
    
    return results
```

---

### BUG-07 📐 告警状态机状态名偏离规格

**文件**：`server/services/alert_service.py:29, 87-101`

**现象**：代码中的告警状态只有 `'normal'` 和 `'triggered'`：

```python
_alert_state: dict[int, str] = {}  # state: 'normal' | 'triggered'
```

**规格要求**（PROJECT.md 8.2节）：

```
normal → alerting → recovering → normal
```

代码中：
1. 使用了 `'triggered'` 而不是 `'alerting'`
2. 缺少 `'recovering'` 中间状态
3. 从 `alerting` 到 `normal` 的转换应经过 `recovering` 状态，且 `recovering` 时应**发送恢复通知**

**修改建议**：将状态名改为 `'alerting'`，并实现 `'recovering'` 状态（在 `recovering` 时发送恢复通知，之后自动转为 `normal`）。

---

### BUG-08 📐 未实现历史补传数据的告警抑制

**文件**：`server/ws/agent_handler.py:117-165`

**现象**：`on_agent_probe_result` 对所有收到的探测结果都调用告警评估，不检查时间戳：

```python
def on_agent_probe_result(self, data):
    ...
    # 写入 InfluxDB
    influx_service.write_probe_result(...)
    
    # ACK
    emit('center:result_ack', {'result_id': result_id})
    
    # 告警评估（无时间戳检查！）
    process_probe_result(task_id, data.get('metrics', {}))
```

**规格要求**（PROJECT.md 7.4.3节）：

> **关键规则：历史补传数据不触发实时告警**  
> 若 `timestamp` 早于当前时间超过 **60 秒**，视为历史补传数据，只入库不告警。

**修改建议**：在调用 `process_probe_result` 之前，先检查时间戳：

```python
from datetime import datetime, timezone, timedelta

ts_str = data.get('timestamp')
if ts_str:
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
        if age_seconds > 60:
            # 历史数据，只入库不告警
            return
    except Exception:
        pass

# 实时数据，正常评估告警
process_probe_result(task_id, data.get('metrics', {}))
```

---

### BUG-09 📐 Dashboard 搜索缺少节点名和目标地址匹配

**文件**：`server/api/data.py:43-46`

**现象**：

```python
if search_filter:
    tasks_query = tasks_query.filter(
        db.or_(
            ProbeTask.name.ilike(f'%{search_filter}%'),  # 只搜索任务名
        )
    )
```

**规格要求**（PROJECT.md 14.4节）：

> `search`：关键词搜索（匹配 **任务名称 / 节点名称 / 目标地址**，大小写不敏感）

**修改建议**：添加对源节点名和目标地址的搜索：

```python
if search_filter:
    # 需要 JOIN nodes 表搜索节点名
    tasks_query = tasks_query.join(
        Node, ProbeTask.source_node_id == Node.id, isouter=True
    ).filter(
        db.or_(
            ProbeTask.name.ilike(f'%{search_filter}%'),
            Node.name.ilike(f'%{search_filter}%'),
            ProbeTask.target_address.ilike(f'%{search_filter}%'),
        )
    )
```

---

### BUG-10 📐 Dashboard 任务排序未实现"告警优先"规则

**文件**：`server/api/data.py:50`

**现象**：

```python
tasks = tasks_query.order_by(ProbeTask.name.asc()).all()
```

**规格要求**（PROJECT.md 14.4节 Dashboard默认排序规则）：

| 数据类型 | 默认排序 | 说明 |
|---|---|---|
| `tasks` | `alert_status DESC, name ASC` | 告警中的任务置顶，其余按名称排序 |

当前实现中 `alert_status` 是一个运行时内存中的状态（来自告警引擎），不是数据库字段，这使得实现稍微复杂。

**修改建议**：可以先查出所有任务，然后在内存中排序（告警引擎状态 → 按名字）；或者在数据库中增加 `alert_status` 字段并由告警引擎更新。

---

### BUG-11 📐 Dockerfile 使用 Flask 开发服务器，与 eventlet 不兼容

**文件**：`Dockerfile:16`

**现象**：

```dockerfile
CMD ["python", "-m", "flask", "--app", "server.app:create_app", "run", \
     "--host", "0.0.0.0", "--port", "5000"]
```

**问题**：`server/extensions.py` 中 SocketIO 配置了 `async_mode='eventlet'`：

```python
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')
```

使用 `flask run`（Werkzeug 开发服务器）+ `eventlet` 异步模式时，WebSocket 连接不稳定，且在生产环境中存在性能瓶颈。flask-socketio 官方要求：**`eventlet` 模式必须配合 `gunicorn + eventlet worker` 或直接使用 `socketio.run()` 启动**。

**修改建议**：将 Dockerfile 的启动命令改为：

```dockerfile
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", \
     "--bind", "0.0.0.0:5000", "server.app:create_app()"]
```

或（使用 `socketio.run`）：

```python
# 新建 run.py
from server.app import create_app
from server.extensions import socketio

app = create_app()
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
```

```dockerfile
CMD ["python", "run.py"]
```

---

### BUG-12 📐 心跳处理每次都执行数据库写入（性能问题）

**文件**：`server/ws/agent_handler.py:112-115`

**现象**：

```python
def on_agent_heartbeat(self, data):
    node_service.record_heartbeat(node_id, data.get('seq'))

    # 每秒1次，每次都写 SQLite！
    node = db.session.get(Node, node_id)
    if node:
        node.last_seen = datetime.now(timezone.utc)
        db.session.commit()
```

Agent 每秒发送1次心跳，如果有10个节点，SQLite 每秒会收到10次写入请求。SQLite 的并发写入性能有限，随节点数增加会造成明显延迟。

**修改建议**：将 `last_seen` 更新从心跳处理器中移出，改为在后台的 `heartbeat_checker` 中（每10秒执行一次）批量更新 `last_seen`：

```python
def on_agent_heartbeat(self, data):
    # 只更新内存中的心跳窗口，不写数据库
    node_service.record_heartbeat(node_id, data.get('seq'))
    # last_seen 由 heartbeat_checker 每10秒批量更新
```

---

### BUG-13 📐 探测结果提交未验证 source_node 身份

**文件**：`server/ws/agent_handler.py:117-165`

**现象**：

```python
def on_agent_probe_result(self, data):
    node_id = _agent_sessions.get(sid)  # 当前连接的节点
    task_id = data.get('task_id')
    task = db.session.get(ProbeTask, task_id)
    
    # 没有验证 node_id == task.source_node_id ！
    source_node = db.session.get(Node, task.source_node_id)
    ...
    influx_service.write_probe_result({
        'source_node': source_node.name if source_node else node_id,
        ...
    })
```

已认证的任意节点可以提交**任何**任务的探测结果，包括属于其他节点的任务，导致数据被篡改或污染。

**修改建议**：在写入 InfluxDB 之前，验证提交者身份：

```python
if task.source_node_id != node_id:
    logger.warning(f"Node {node_id} attempted to submit results for task {task_id} "
                   f"which belongs to node {task.source_node_id}. Rejected.")
    emit('center:result_ack', {'result_id': result_id})  # 仍然ACK避免无限重传
    return
```

---

## 三、Bug 严重程度汇总

| # | 文件 | 描述 | 严重程度 |
|---|---|---|---|
| BUG-01 | `alert_service.py` | `push_alert` 函数签名不匹配，导致告警推送完全失效 | ⛔ 严重 |
| BUG-02 | `alert_service.py` | `AlertHistory` 构造函数传入不存在的 `operator` 字段 | ⛔ 严重 |
| BUG-03 | `alert_service.py` | 引用 `ProbeTask` 中不存在的字段，告警系统完全不可用 | ⛔ 严重 |
| BUG-04 | `alert_service.py` | Webhook URL 读取字段不存在，通知永远无法发出 | ⛔ 严重 |
| BUG-05 | `influx_service.py` | Measurement 名称 `probe_result` 应为 `probe_results` | 📐 偏离规格 |
| BUG-06 | `alert_service.py` | 告警评估连续计数而非滑动窗口，且只评估单指标 | 📐 偏离规格 |
| BUG-07 | `alert_service.py` | 状态机状态名 `triggered` 应为 `alerting`，缺少 `recovering` | 📐 偏离规格 |
| BUG-08 | `agent_handler.py` | 未实现历史补传数据的告警抑制（60秒阈值） | 📐 偏离规格 |
| BUG-09 | `data.py` | Dashboard 搜索缺少节点名和目标地址匹配 | 📐 偏离规格 |
| BUG-10 | `data.py` | Dashboard 任务排序未实现告警任务置顶 | 📐 偏离规格 |
| BUG-11 | `Dockerfile` | 使用 Flask 开发服务器，与 eventlet async_mode 不兼容 | 📐 偏离规格 |
| BUG-12 | `agent_handler.py` | 每次心跳都执行 SQLite 写入，高并发下存在性能问题 | ⚠️ 性能 |
| BUG-13 | `agent_handler.py` | 探测结果提交未验证 source_node 身份，存在数据污染风险 | ⚠️ 安全 |

---

## 四、优先修复建议

1. **立刻修复 BUG-01 至 BUG-04**：这4个 Bug 导致整个告警子系统（状态评估、历史记录、Webhook 通知、前端推送）全部不可用，是最高优先级。

2. **次优先修复 BUG-06 + BUG-07**：告警评估算法和状态机是业务核心，必须按规格实现窗口化评估和完整的状态机。

3. **修复 BUG-11**：Dockerfile 启动命令应改为 gunicorn，否则生产部署的 WebSocket 稳定性无法保证。

4. **修复 BUG-05, BUG-08, BUG-09, BUG-10**：InfluxDB 命名和 API 行为的规格对齐。

5. **修复 BUG-13**：安全加固，防止节点数据污染。

6. **优化 BUG-12**：性能优化，减少 SQLite 写入压力。
