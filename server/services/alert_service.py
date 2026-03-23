"""Alert engine service - window-based evaluation with state machine.

States per (task_id, metric): normal -> alerting -> normal
Evaluation (PROJECT.md §12.1):
  - Sliding window of last N results per (task_id, metric)
  - Trigger: window has >= M breaches
  - Recovery: consecutive K normal results
  - Cooldown: same (task_id, metric) won't re-alert within cooldown_seconds
Event types: 'alert' / 'recovery' (PROJECT.md §6.3)
Alert status: 'normal' / 'alerting' (PROJECT.md §8.2)
"""
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock

from server.extensions import db

logger = logging.getLogger(__name__)

# Sliding window of breach booleans per (task_id, metric)
_windows: dict[tuple[str, str], deque[bool]] = {}
# Alert state: 'normal' | 'alerting'
_alert_state: dict[tuple[str, str], str] = {}
# Consecutive OK counts for recovery
_ok_counts: dict[tuple[str, str], int] = defaultdict(int)
# Last alert time for cooldown
_last_alert_time: dict[tuple[str, str], float] = {}
# Continuous fail counter per task
_fail_counts: dict[str, int] = defaultdict(int)
_lock = Lock()


def get_alert_status(task_id: str) -> str:
    """Get current alert status: 'normal' or 'alerting'."""
    with _lock:
        for (tid, _), state in _alert_state.items():
            if tid == task_id and state == 'alerting':
                return 'alerting'
    return 'normal'


def _check_threshold(task_id: str, metric_name: str, value: float,
                     threshold: float, eval_window: int,
                     trigger_count: int, recovery_count: int,
                     cooldown: int):
    """Window-based threshold check. Returns 'alert', 'recovery', or None."""
    key = (task_id, metric_name)
    is_breach = value > threshold

    with _lock:
        state = _alert_state.get(key, 'normal')
        now = time.time()

        # Ensure window exists with correct maxlen
        if key not in _windows or _windows[key].maxlen != eval_window:
            old = _windows.get(key, deque())
            _windows[key] = deque(old, maxlen=eval_window)
        _windows[key].append(is_breach)

        if is_breach:
            _ok_counts[key] = 0
        else:
            _ok_counts[key] += 1

        if state == 'normal':
            breach_count = sum(1 for b in _windows[key] if b)
            if breach_count >= trigger_count:
                last = _last_alert_time.get(key, 0)
                if now - last >= cooldown:
                    _alert_state[key] = 'alerting'
                    _last_alert_time[key] = now
                    _ok_counts[key] = 0
                    return 'alert'

        elif state == 'alerting':
            if _ok_counts[key] >= recovery_count:
                _alert_state[key] = 'normal'
                _ok_counts[key] = 0
                return 'recovery'

    return None


def evaluate_probe_result(task_id: str, metrics: dict):
    """Evaluate a single probe result against all configured alert rules.

    Returns list of (event_type, metric_name, actual_value, threshold) tuples.
    """
    from server.models.task import ProbeTask

    task = db.session.get(ProbeTask, task_id)
    if not task:
        return []

    # Check if any alert threshold is configured
    has_alert = (task.alert_latency_threshold is not None
                 or task.alert_loss_threshold is not None
                 or task.alert_fail_count is not None)
    if not has_alert:
        return []

    eval_window = task.alert_eval_window
    trigger_count = task.alert_trigger_count
    recovery_count = task.alert_recovery_count
    cooldown = task.alert_cooldown_seconds
    events = []

    # Rule 1: latency
    if task.alert_latency_threshold is not None:
        latency = metrics.get('latency')
        if latency is not None:
            try:
                latency = float(latency)
                event = _check_threshold(
                    task_id, 'latency', latency,
                    task.alert_latency_threshold,
                    eval_window, trigger_count, recovery_count, cooldown)
                if event:
                    events.append((event, 'latency', latency, task.alert_latency_threshold))
            except (ValueError, TypeError):
                pass

    # Rule 2: packet_loss
    if task.alert_loss_threshold is not None:
        loss = metrics.get('packet_loss')
        if loss is not None:
            try:
                loss = float(loss)
                event = _check_threshold(
                    task_id, 'packet_loss', loss,
                    task.alert_loss_threshold,
                    eval_window, trigger_count, recovery_count, cooldown)
                if event:
                    events.append((event, 'packet_loss', loss, task.alert_loss_threshold))
            except (ValueError, TypeError):
                pass

    # Rule 3: continuous_fail
    if task.alert_fail_count is not None:
        success = metrics.get('success', True)
        with _lock:
            if not success:
                _fail_counts[task_id] += 1
            else:
                _fail_counts[task_id] = 0

            fail_val = float(_fail_counts[task_id])

        event = _check_threshold(
            task_id, 'continuous_fail', fail_val,
            float(task.alert_fail_count),
            eval_window, trigger_count, recovery_count, cooldown)
        if event:
            events.append((event, 'continuous_fail', fail_val, float(task.alert_fail_count)))

    return events


def record_alert_event(task_id: str, event_type: str, metric: str,
                       actual_value: float, threshold: float):
    """Record an alert event to alert_history and send webhook notifications."""
    from server.models.alert import AlertHistory, AlertChannel
    from server.utils.webhook import send_webhook

    history = AlertHistory(
        task_id=task_id,
        event_type=event_type,
        metric=metric,
        actual_value=actual_value,
        threshold=threshold,
        notified=False,
    )
    db.session.add(history)
    db.session.commit()

    # Send to all enabled webhook channels
    channels = AlertChannel.query.filter_by(enabled=True).all()
    notified = False
    for channel in channels:
        if channel.type == 'webhook':
            url = channel.url
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
    push_alert({
        'task_id': task_id,
        'event_type': event_type,
        'metric': metric,
        'actual_value': actual_value,
        'threshold': threshold,
    })

    return history


def process_probe_result(task_id: str, metrics: dict):
    """Main entry point: evaluate and handle alert for a probe result."""
    events = evaluate_probe_result(task_id, metrics)
    for event_type, metric, value, threshold in events:
        record_alert_event(task_id, event_type, metric, value, threshold)
    return events
