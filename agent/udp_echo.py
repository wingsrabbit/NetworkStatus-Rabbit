"""Dual TCP+UDP echo server for agent-to-agent probes.

When --listen-port is specified, the agent starts both a TCP and UDP echo
service on that port.  This allows the agent to be a target for internal
TCP and UDP probes from other agents.
"""
import logging
import socket
import threading

logger = logging.getLogger(__name__)


class EchoServer:
    """Runs a TCP echo and UDP echo on the same port number."""

    def __init__(self, port: int, host: str = '0.0.0.0', buffer_size: int = 4096):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self._stop_event = threading.Event()
        self._udp_socket = None
        self._tcp_socket = None
        self._threads: list[threading.Thread] = []

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def start(self) -> bool:
        """Attempt to bind both TCP and UDP on self.port. Returns True if at least one succeeds."""
        ok = False

        # --- UDP echo ---
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            self._udp_socket = sock
            t = threading.Thread(target=self._udp_loop, daemon=True)
            t.start()
            self._threads.append(t)
            logger.info('UDP echo listening on %s:%s', self.host, self.port)
            ok = True
        except OSError as exc:
            logger.error('UDP echo bind failed on %s:%s: %s', self.host, self.port, exc)

        # --- TCP echo ---
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(16)
            sock.settimeout(1.0)
            self._tcp_socket = sock
            t = threading.Thread(target=self._tcp_accept_loop, daemon=True)
            t.start()
            self._threads.append(t)
            logger.info('TCP echo listening on %s:%s', self.host, self.port)
            ok = True
        except OSError as exc:
            logger.error('TCP echo bind failed on %s:%s: %s', self.host, self.port, exc)

        return ok

    def stop(self):
        self._stop_event.set()
        for s in (self._udp_socket, self._tcp_socket):
            if s:
                try:
                    s.close()
                except OSError:
                    pass
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()

    # ---- internal loops ----

    def _udp_loop(self):
        while not self._stop_event.is_set():
            try:
                data, addr = self._udp_socket.recvfrom(self.buffer_size)
            except OSError:
                if self._stop_event.is_set():
                    break
                continue
            try:
                self._udp_socket.sendto(data, addr)
            except OSError:
                pass

    def _tcp_accept_loop(self):
        while not self._stop_event.is_set():
            try:
                conn, addr = self._tcp_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break
                continue
            # Handle each TCP connection in its own thread
            t = threading.Thread(target=self._tcp_client_handler, args=(conn,), daemon=True)
            t.start()

    def _tcp_client_handler(self, conn: socket.socket):
        """Echo back whatever arrives on a TCP connection, then close."""
        conn.settimeout(10)
        try:
            while not self._stop_event.is_set():
                data = conn.recv(self.buffer_size)
                if not data:
                    break
                conn.sendall(data)
        except (OSError, socket.timeout):
            pass
        finally:
            conn.close()
