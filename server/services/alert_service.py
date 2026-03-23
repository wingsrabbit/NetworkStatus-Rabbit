"""Alert engine service - window-based evaluation with state machine.

States per task: normal -> triggered -> (cooldown) -> normal
Evaluation: sliding window of last N results, check threshold condition.
"""
import logging
import operator as op
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

from server.extensions import db

logger = logging.getLogger(__name__)

# Operator map
OPERATORS = {
    '>': op.gt,
    '>=': op.ge,
    '<': op.lt,
    '<=': op.le,
    '==': op.eq,
    '!=': op.ne,
}

# Alert state per task_id
# state: 'normal' | 'triggered'
_alert_state: dict[int, str] = {}
# sliding window of metric values per task: task_id -> deque of (timestamp, value)
_windows: dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
# Count of consecutive threshold-breaching results: task_id -> int
_breach_counts: dict[int, int] = defaultdict(int)
# Count of consecutive OK results (for recovery): task_id -> int
_ok_counts: dict[int, int] = defaultdict(int)
# Last alert time (for cooldown): task_id -> timestamp
_last_alert_time: dict[int, float] = {}
_lock = Lock()


def evaluate_probe_result(task_id: int, metrics: dict):
    """Evaluate a single probe result against alert rules.

    Called from agent_handler on each probe_result received.
    Returns: ('triggered', metric, value, threshold, operator) or ('recovered', ...) or None
    """
    from server.models.task import ProbeTask

    task = db.session.get(ProbeTask, task_id)
    if not task or not task.alert_enabled:
        return None

    alert_metric = task.alert_metric
    alert_operator = task.alert_operator
    alert_threshold = task.alert_threshold
    trigger_count = task.alert_trigger_count
    recovery_count = task.alert_recovery_count
    cooldown = task.alert_cooldown_seconds

    if alert_threshold is None or alert_operator not in OPERATORS:
        return None

    # Extract metric value
    value = metrics.get(alert_metric)
    if value is None:
        return None

    try:
        value = float(value)
    except (ValueError, TypeError):
        return None

    compare = OPERATORS[alert_operator]
    is_breach = compare(value, alert_threshold)

    with _lock:
        state = _alert_state.get(task_id, 'normal')
        now = time.time()

        if is_breach:
            _breach_counts[task_id] += 1
            _ok_counts[task_id] = 0
        else:
            _ok_counts[task_id] += 1
            _breach_counts[task_id] = 0

        if state == 'normal':
            if _breach_counts[task_id] >= trigger_count:
                # Check cooldown
                last = _last_alert_time.get(task_id, 0)
                if now - last >= cooldown:
                    _alert_state[task_id] = 'triggered'
                    _last_alert_time[task_id] = now
                    _breach_counts[task_id] = 0
                    return ('triggered', alert_metric, value, alert_threshold, alert_operator)

        elif state == 'triggered':
            if _ok_counts[task_id] >= recovery_count:
                _alert_state[task_id] = 'normal'
                _ok_counts[task_id] = 0
                return ('recovered', alert_metric, value, alert_threshold, alert_operator)

    return None


def record_alert_event(task_id: int, event_type: str, metric: str,
                       actual_value: float, threshold: float, alert_operator: str):
    """Record an alert event to alert_history and send webhook notifications."""
    from server.models.alert import AlertHistory, AlertChannel
    from server.utils.webhook import send_webhook

    # Record history
    history = AlertHistory(
        task_id=task_id,
        event_type=event_type,
        metric=metric,
        actual_value=actual_value,
        threshold=threshold,
        operator=alert_operator,
        notified=False,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(history)
    db.session.commit()

    # Send to all enabled webhook channels
    channels = AlertChannel.query.filter_by(enabled=True).all()
    notified = False
    for channel in channels:
        if channel.type == 'webhook':
            url = channel.config_data.get('url') if hasattr(channel, 'config_data') else None
            if not url:
                try:
                    import json
                    config = json.loads(channel.config) if isinstance(channel.config, str) else channel.config
                    url = config.get('url')
                except Exception:
                    continue

            if url:
                from server.models.task import ProbeTask
                task = db.session.get(ProbeTask, task_id)
                payload = {
                    'event': event_type,
                    'task_id': task_id,
                    'task_name': task.name if task else str(task_id),
                    'metric': metric,
                    'actual_value': actual_value,
                    'threshold': threshold,
                    'operator': alert_operator,
                    'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
                }
                try:
                    send_webhook(url, payload)
                    notified = True
                except Exception as e:
                    logger.error(f"Webhook send failed to {url}: {e}")

    if notified:
        history.notified = True
        db.session.commit()

    # Push to dashboard
    from server.ws.dashboard_handler import push_alert
    push_alert(task_id, event_type, metric, actual_value)

    return history


def process_probe_result(task_id: int, metrics: dict):
    """Main entry point: evaluate and handle alert for a probe result."""
    result = evaluate_probe_result(task_id, metrics)
    if result:
        event_type, metric, value, threshold, alert_op = result
        record_alert_event(task_id, event_type, metric, value, threshold, alert_op)
        return result
    return None
