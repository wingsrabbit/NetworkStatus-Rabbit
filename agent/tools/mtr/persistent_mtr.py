"""Persistent MTR process — streams mtr --raw output and accumulates per-hop statistics."""
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HopState:
    """Running statistics for a single hop, updated via Welford's online algorithm."""
    hop: int = 0
    host: str = '???'
    dns_name: str = ''
    sent: int = 0
    received: int = 0
    last: float = 0.0       # ms
    best: float = float('inf')
    worst: float = 0.0      # ms
    _mean: float = 0.0
    _m2: float = 0.0

    @property
    def avg(self) -> float:
        return self._mean if self.received > 0 else 0.0

    @property
    def stdev(self) -> float:
        if self.received < 2:
            return 0.0
        return (self._m2 / self.received) ** 0.5

    def record_latency(self, latency_ms: float):
        self.received += 1
        self.last = latency_ms
        if latency_ms < self.best:
            self.best = latency_ms
        if latency_ms > self.worst:
            self.worst = latency_ms
        # Welford's online algorithm
        delta = latency_ms - self._mean
        self._mean += delta / self.received
        delta2 = latency_ms - self._mean
        self._m2 += delta * delta2


class PersistentMtr:
    """Manages a long-running ``mtr --raw`` process with streaming stats accumulation.

    Raw output format (mtr 0.95+)::

        x <hop> <seq>              — probe sent to hop
        h <hop> <ip>               — host discovered at hop (may appear twice)
        d <hop> <dns_name>         — DNS reverse lookup result
        p <hop> <latency_us> <seq> — ping response received

    Usage::

        pm = PersistentMtr('8.8.8.8', 'icmp')
        pm.start()
        ...
        result = pm.snapshot()   # ProbeResult with current accumulated hops
        ...
        pm.stop()
    """

    def __init__(self, target: str, protocol: str = 'icmp', port: int = None, interval: float = 1):
        self.target = target
        self.protocol = protocol
        self.port = port
        self.interval = interval

        self._hops: Dict[int, HopState] = {}
        self._src: str = ''
        self._dst: str = target
        self._lock = threading.Lock()

        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._error: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Spawn the mtr process and start the reader thread."""
        if self._process and self._process.poll() is None:
            return  # already running

        self._stop_event.clear()
        self._error = None

        cmd = self._build_cmd()
        logger.info(f"PersistentMtr starting: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered
            )
        except FileNotFoundError:
            self._error = 'mtr command not found'
            logger.error(self._error)
            return
        except Exception as e:
            self._error = str(e)[:200]
            logger.error(f"PersistentMtr failed to start: {self._error}")
            return

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def stop(self):
        """Kill the mtr process and wait for the reader thread."""
        self._stop_event.set()
        proc = self._process
        if proc:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            self._process = None
        if self._reader_thread:
            self._reader_thread.join(timeout=3)
            self._reader_thread = None

    def is_alive(self) -> bool:
        proc = self._process
        return proc is not None and proc.poll() is None

    # ------------------------------------------------------------------
    # Snapshot — called from scheduler at probe interval
    # ------------------------------------------------------------------

    def snapshot(self):
        """Return a :class:`ProbeResult` reflecting the current accumulated state."""
        from agent.probes.base import ProbeResult

        with self._lock:
            if self._error and not self._hops:
                return ProbeResult(success=False, error=self._error)

            if not self._hops:
                return ProbeResult(success=False, error='Waiting for first mtr round')

            hops_data = []
            sorted_hops = sorted(self._hops.values(), key=lambda h: h.hop)
            for h in sorted_hops:
                sent = h.sent
                loss_pct = (1.0 - h.received / sent) * 100.0 if sent > 0 else 0.0
                hops_data.append({
                    'hop': h.hop,
                    'host': h.dns_name or h.host,
                    'loss': round(loss_pct, 1),
                    'sent': sent,
                    'last': round(h.last, 2),
                    'avg': round(h.avg, 2),
                    'best': round(h.best, 2) if h.best != float('inf') else 0.0,
                    'worst': round(h.worst, 2),
                    'stdev': round(h.stdev, 2),
                })

            if not hops_data:
                return ProbeResult(success=False, error='No hops discovered yet')

            final = hops_data[-1]
            latency = final['avg'] if final['avg'] > 0 else None
            packet_loss = final['loss']
            jitter = final['stdev'] if final['stdev'] > 0 else None

            result = ProbeResult(
                success=packet_loss < 100.0,
                latency=latency,
                packet_loss=packet_loss,
                jitter=jitter,
            )
            result.hops = hops_data
            result.extra = {
                'mtr_src': self._src,
                'mtr_dst': self._dst,
            }
            return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_cmd(self) -> list:
        cmd = ['mtr', '--raw', '-c', '999999', '-i', str(self.interval)]
        if self.protocol == 'tcp':
            cmd.append('--tcp')
            cmd.extend(['-P', str(self.port or 80)])
        elif self.protocol == 'udp':
            cmd.append('--udp')
            cmd.extend(['-P', str(self.port or 53)])
        cmd.append(self.target)
        return cmd

    def _reader_loop(self):
        """Read stdout line-by-line and parse raw mtr output."""
        proc = self._process
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break
                line = line.strip()
                if line:
                    self._parse_line(line)
        except Exception as e:
            logger.error(f"PersistentMtr reader error: {e}")
        finally:
            # Capture stderr if process exited with error
            if proc.poll() is not None and proc.returncode != 0:
                stderr = ''
                try:
                    stderr = proc.stderr.read().strip()[:200] if proc.stderr else ''
                except Exception:
                    pass
                with self._lock:
                    self._error = f'mtr exited (rc={proc.returncode}): {stderr}'
                logger.warning(f"PersistentMtr process ended: {self._error}")

    def _parse_line(self, line: str):
        """Parse a single raw mtr output line.

        mtr 0.95 raw format::

            x <hop> <seq>              — probe sent
            h <hop> <ip>               — host at hop (may repeat)
            d <hop> <dns_name>         — DNS name
            p <hop> <latency_us> <seq> — response received
        """
        parts = line.split()
        if len(parts) < 3:
            return

        code = parts[0]
        try:
            hop_num = int(parts[1])
        except ValueError:
            return

        with self._lock:
            if code == 'x':
                # Probe sent to this hop
                self._ensure_hop(hop_num)
                self._hops[hop_num].sent += 1

            elif code == 'h':
                ip = parts[2]
                self._ensure_hop(hop_num)
                # Only set host if not already set (first h line per hop)
                if self._hops[hop_num].host == '???':
                    self._hops[hop_num].host = ip
                # Use hop 0's IP as source
                if hop_num == 0:
                    self._src = ip

            elif code == 'd':
                dns_name = parts[2]
                self._ensure_hop(hop_num)
                self._hops[hop_num].dns_name = dns_name

            elif code == 'p':
                if len(parts) < 3:
                    return
                try:
                    latency_us = int(parts[2])
                except ValueError:
                    return
                latency_ms = latency_us / 1000.0

                self._ensure_hop(hop_num)
                self._hops[hop_num].record_latency(latency_ms)

    def _ensure_hop(self, hop_num: int):
        if hop_num not in self._hops:
            self._hops[hop_num] = HopState(hop=hop_num)
