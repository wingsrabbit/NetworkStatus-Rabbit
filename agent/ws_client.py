"""Agent WebSocket client - connects to center, handles auth/heartbeat/data."""
import logging
import threading
import time
import platform
from datetime import datetime, timezone

import socketio

logger = logging.getLogger(__name__)


class WSClient:
    def __init__(self, config, local_cache, scheduler):
        """
        config: AgentConfig
        local_cache: LocalCache
        scheduler: TaskScheduler
        """
        self.config = config
        self.cache = local_cache
        self.scheduler = scheduler
        self.sio = socketio.Client(reconnection=True, reconnection_delay=2, reconnection_delay_max=30)
        self.connected = False
        self.authenticated = False
        self.config_version = 0
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._seq = 0

        self._register_handlers()

    def _register_handlers(self):
        sio = self.sio

        @sio.on('connect', namespace='/agent')
        def on_connect():
            logger.info("Connected to center server")
            self.connected = True
            self._authenticate()

        @sio.on('disconnect', namespace='/agent')
        def on_disconnect():
            logger.warning("Disconnected from center server")
            self.connected = False
            self.authenticated = False
            self._stop_heartbeat()

        @sio.on('center_auth_result', namespace='/agent')
        def on_auth_result(data):
            if data.get('success'):
                logger.info("Authentication successful")
                self.authenticated = True
                self._start_heartbeat()
                self._backfill()
            else:
                logger.error(f"Authentication failed: {data.get('message')}")
                self.authenticated = False

        @sio.on('center_task_sync', namespace='/agent')
        def on_task_sync(data):
            cv = data.get('config_version', 0)
            tasks = data.get('tasks', [])
            logger.info(f"Received full task sync: config_version={cv}, {len(tasks)} tasks")
            self.scheduler.update_tasks(tasks)
            self.config_version = cv
            sio.emit('agent_task_ack', {'config_version': cv}, namespace='/agent')

        @sio.on('center_task_assign', namespace='/agent')
        def on_task_assign(data):
            cv = data.get('config_version', 0)
            logger.info(f"Received task assign: {data.get('task_id')}")
            self.scheduler.start_task(data)
            self.config_version = cv
            sio.emit('agent_task_ack', {'config_version': cv}, namespace='/agent')

        @sio.on('center_task_update', namespace='/agent')
        def on_task_update(data):
            cv = data.get('config_version', 0)
            task_id = data.get('task_id')
            logger.info(f"Received task update: {task_id}")
            self.scheduler.stop_task(task_id)
            if data.get('enabled', True):
                self.scheduler.start_task(data)
            self.config_version = cv
            sio.emit('agent_task_ack', {'config_version': cv}, namespace='/agent')

        @sio.on('center_task_remove', namespace='/agent')
        def on_task_remove(data):
            cv = data.get('config_version', 0)
            task_id = data.get('task_id')
            logger.info(f"Received task remove: {task_id}")
            self.scheduler.stop_task(task_id)
            self.config_version = cv
            sio.emit('agent_task_ack', {'config_version': cv}, namespace='/agent')

        @sio.on('center_result_ack', namespace='/agent')
        def on_result_ack(data):
            result_id = data.get('result_id')
            self.cache.mark_acked(result_id)

        @sio.on('center_batch_ack', namespace='/agent')
        def on_batch_ack(data):
            accepted_ids = data.get('accepted_ids', [])
            self.cache.mark_batch_acked(accepted_ids)
            logger.info(f"Batch ACK received: {len(accepted_ids)} results confirmed")

    def _authenticate(self):
        """Send auth event with capabilities."""
        from agent.probes.base import get_all_probes
        probes = get_all_probes()

        protocols = []
        unsupported = []
        unsupported_reasons = {}

        for name, probe in probes.items():
            try:
                if probe.self_test():
                    protocols.append(name)
                else:
                    unsupported.append(name)
                    unsupported_reasons[name] = probe.self_test_reason() or 'Self-test failed'
            except Exception as e:
                unsupported.append(name)
                unsupported_reasons[name] = str(e)

        import psutil
        try:
            # Get IPs
            public_ip = None
            private_ip = None
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family.name == 'AF_INET':
                        ip = addr.address
                        if ip.startswith(('10.', '172.', '192.168.')):
                            private_ip = private_ip or ip
                        elif ip != '127.0.0.1':
                            public_ip = public_ip or ip
        except Exception:
            public_ip = None
            private_ip = None

        capabilities = {
            'protocols': protocols,
            'unsupported': unsupported,
            'unsupported_reasons': unsupported_reasons,
            'agent_version': '0.1.0',
            'os': f'{platform.system()} {platform.release()}',
            'public_ip': public_ip,
            'private_ip': private_ip,
        }

        self.sio.emit('agent_auth', {
            'node_id': self.config.node_id,
            'token': self.config.token,
            'config_version': self.config_version,
            'capabilities': capabilities,
        }, namespace='/agent')

    def _start_heartbeat(self):
        """Start heartbeat thread (1/sec)."""
        self._heartbeat_stop.clear()

        def heartbeat_loop():
            while not self._heartbeat_stop.is_set():
                if self.connected and self.authenticated:
                    self._seq += 1
                    try:
                        self.sio.emit('agent_heartbeat', {
                            'node_id': self.config.node_id,
                            'seq': self._seq,
                        }, namespace='/agent')
                    except Exception:
                        pass
                self._heartbeat_stop.wait(1)

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self):
        self._heartbeat_stop.set()

    def _backfill(self):
        """Send unacked results as batch after reconnect."""
        unacked = self.cache.get_unacked_results()
        if not unacked:
            return

        batch_id = f'batch-{self.config.node_id}-{int(time.time())}'
        logger.info(f"Backfilling {len(unacked)} results as batch {batch_id}")

        # Send in chunks of 100
        for i in range(0, len(unacked), 100):
            chunk = unacked[i:i + 100]
            chunk_batch_id = f'{batch_id}-{i}'
            self.sio.emit('agent_probe_batch', {
                'batch_id': chunk_batch_id,
                'results': chunk,
            }, namespace='/agent')

    def send_probe_result(self, task_id, protocol, result, seq, timestamp):
        """Send a probe result to center and cache locally."""
        node_id = self.config.node_id
        ts_ms = int(timestamp.timestamp() * 1000)
        result_id = f'{node_id}-{ts_ms}-{protocol}-{seq:04d}'

        payload = {
            'result_id': result_id,
            'task_id': task_id,
            'timestamp': timestamp.isoformat() + 'Z',
            'protocol': protocol,
            'metrics': result.to_dict(),
        }

        # Cache locally first
        self.cache.store_result(result_id, task_id, payload)

        if self.connected and self.authenticated:
            try:
                self.sio.emit('agent_probe_result', payload, namespace='/agent')
                self.cache.mark_sent(result_id)
            except Exception as e:
                logger.warning(f"Failed to send result {result_id}: {e}")

    def connect(self):
        """Connect to the center server."""
        url = self.config.server_url
        logger.info(f"Connecting to {url}")
        try:
            self.sio.connect(url, namespaces=['/agent'], wait_timeout=10)
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    def wait(self):
        """Block until disconnected."""
        self.sio.wait()

    def disconnect(self):
        self._stop_heartbeat()
        self.scheduler.stop_all()
        self.sio.disconnect()
