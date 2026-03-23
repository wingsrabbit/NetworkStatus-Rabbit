"""Agent task scheduler - runs probe tasks at configured intervals."""
import logging
import threading
import time
from datetime import datetime, timezone

from agent.probes.base import get_probe

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, on_result_callback):
        """
        on_result_callback: function(task_id, protocol, result_data) called with each probe result
        """
        self.tasks = {}  # task_id -> task_config
        self._threads = {}  # task_id -> thread
        self._stop_events = {}  # task_id -> Event
        self._on_result = on_result_callback
        self._seq_counter = 0
        self._seq_lock = threading.Lock()

    def _next_seq(self):
        with self._seq_lock:
            self._seq_counter += 1
            return self._seq_counter

    def update_tasks(self, tasks_list):
        """Replace all tasks with a new list (full sync)."""
        new_task_ids = {t['task_id'] for t in tasks_list}

        # Stop removed tasks
        for task_id in list(self.tasks.keys()):
            if task_id not in new_task_ids:
                self.stop_task(task_id)

        # Add/update tasks
        for task_config in tasks_list:
            task_id = task_config['task_id']
            if task_id in self.tasks:
                # Check if config changed
                old = self.tasks[task_id]
                if (old.get('interval') != task_config.get('interval') or
                    old.get('target_address') != task_config.get('target_address') or
                    old.get('protocol') != task_config.get('protocol') or
                    old.get('enabled') != task_config.get('enabled')):
                    self.stop_task(task_id)
                    if task_config.get('enabled', True):
                        self.start_task(task_config)
                    else:
                        self.tasks[task_id] = task_config
                else:
                    self.tasks[task_id] = task_config
            else:
                if task_config.get('enabled', True):
                    self.start_task(task_config)
                else:
                    self.tasks[task_id] = task_config

    def start_task(self, task_config):
        """Start a probe task."""
        task_id = task_config['task_id']
        self.tasks[task_id] = task_config

        stop_event = threading.Event()
        self._stop_events[task_id] = stop_event

        t = threading.Thread(target=self._task_loop, args=(task_id, stop_event), daemon=True)
        self._threads[task_id] = t
        t.start()
        logger.info(f"Started task {task_id}: {task_config.get('protocol')} -> {task_config.get('target_address')}")

    def stop_task(self, task_id):
        """Stop a running task."""
        event = self._stop_events.pop(task_id, None)
        if event:
            event.set()
        self._threads.pop(task_id, None)
        self.tasks.pop(task_id, None)
        logger.info(f"Stopped task {task_id}")

    def stop_all(self):
        """Stop all tasks."""
        for task_id in list(self.tasks.keys()):
            self.stop_task(task_id)

    def _task_loop(self, task_id, stop_event):
        """Main loop for a single task."""
        while not stop_event.is_set():
            config = self.tasks.get(task_id)
            if not config:
                break

            protocol = config.get('protocol', 'icmp')
            target = config.get('target_address', '')
            port = config.get('target_port')
            timeout = config.get('timeout', 10)
            interval = config.get('interval', 5)

            probe = get_probe(protocol)
            if not probe:
                logger.warning(f"No probe plugin for protocol '{protocol}'")
                stop_event.wait(interval)
                continue

            try:
                result = probe.probe(target, port=port, timeout=timeout)
                seq = self._next_seq()
                now = datetime.now(timezone.utc)
                self._on_result(task_id, protocol, result, seq, now)
            except Exception as e:
                logger.error(f"Probe error for task {task_id}: {e}")

            stop_event.wait(interval)
