"""Alert engine service - window-based evaluation with state machine.

States per task: normal -> triggered -> (cooldown) -> normal
Evaluation rules (per v1.5):
  - latency > alert_latency_threshold
  - packet_loss > alert_loss_threshold
  - continuous_fail >= alert_fail_count
Uses sliding window (alert_eval_window), trigger/recovery counts, cooldown.
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from server.extensions import db

logger = logging.getLogger(__name__)

# Per-task, per-metric state
# key: (task_id, metric_name) -> 'normal' | 'triggered'
_alert_state: dict[tuple[str, str], str] = {}
# Consecutive breach counts: (task_id, metric) -> int
_breach_counts: dict[tuple[str, str], int] = defaultdict(int)
# Consecutive OK counts: (task_id, metric) -> int
_ok_counts: dict[tuple[str, str], int] = defaultdict(int)
# Last alert time for cooldown: (task_id, metric) -> timestamp
_last_alert_time: dict[tuple[str, str], float] = {}
# Continuous fail counter: task_id -> int
_fail_counts: dict[str, int] = defaultdict(int)
_lock = Lock()


def _check_threshold(task_id: str, metric_name: str, value: float,
                     threshold: float, trigger_count: int,
                     recovery_count: int, cooldown: int):
    """Generic threshold check with state machine. Returns event or None."""
    key = (task_id, metric_name)
    is_breach = value > threshold

    with _lock:
        state = _alert_state.get(key, 'normal')
        now = time.time()

        if is_breach:
            _breach_counts[key] += 1
            _ok_counts[key] = 0
        else:
            _ok_counts[key] += 1
            _breach_counts[key] = 0

        if state == 'normal':
            if _breach_counts[key] >= trigger_count:
                last = _last_alert_time.get(key, 0)
                if now - last >= cooldown:
                    _alert_state[key] = 'triggered'
                    _last_alert_time[key] = now
                    _breach_counts[key] = 0
                    return 'triggered'

        elif state == 'triggered':
            if _ok_counts[key] >= recovery_count:
                _alert_state[key] = 'normal'
                _ok_counts[key] = 0
                return 'recovered'

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
                    trigger_count, recovery_count, cooldown)
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
                    trigger_count, recovery_count, cooldown)
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
            trigger_count, recovery_count, cooldown)
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
