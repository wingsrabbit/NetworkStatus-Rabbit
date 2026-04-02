"""InfluxDB read/write service."""
import logging
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

# In-memory dedup cache (performance optimization layer only)
_DEDUP_TTL = 600  # 10 minutes
_DEDUP_MAX_SIZE = 100_000
_dedup_cache: OrderedDict[str, float] = OrderedDict()
_dedup_lock = threading.Lock()

# Persistent dedup via SQLite (correctness layer)
_dedup_db_path: str | None = None
_dedup_db_lock = threading.Lock()


def _init_dedup_db(data_dir: str):
    """Initialize persistent dedup SQLite database."""
    global _dedup_db_path
    os.makedirs(data_dir, exist_ok=True)
    _dedup_db_path = os.path.join(data_dir, 'dedup.db')
    conn = sqlite3.connect(_dedup_db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS written_results (
            result_id TEXT PRIMARY KEY,
            written_at REAL NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_written_at ON written_results(written_at)')
    conn.commit()
    conn.close()
    # Cleanup old entries (> 7 days)
    _cleanup_dedup_db()


def _cleanup_dedup_db():
    """Remove dedup entries older than 7 days."""
    if not _dedup_db_path:
        return
    cutoff = time.time() - 7 * 86400
    with _dedup_db_lock:
        conn = sqlite3.connect(_dedup_db_path)
        try:
            conn.execute('DELETE FROM written_results WHERE written_at < ?', (cutoff,))
            conn.commit()
        finally:
            conn.close()


class InfluxService:
    def __init__(self, app=None):
        self.client = None
        self.write_api = None
        self.query_api = None
        self.org = None
        self.bucket_raw = None
        self.bucket_1m = None
        self.bucket_1h = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.org = app.config['INFLUXDB_ORG']
        self.bucket_raw = app.config['INFLUXDB_BUCKET_RAW']
        self.bucket_1m = app.config['INFLUXDB_BUCKET_1M']
        self.bucket_1h = app.config['INFLUXDB_BUCKET_1H']
        self.client = InfluxDBClient(
            url=app.config['INFLUXDB_URL'],
            token=app.config['INFLUXDB_TOKEN'],
            org=self.org
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
        # Initialize persistent dedup database
        _init_dedup_db(app.config['DATA_DIR'])

    def write_probe_result(self, result_data):
        """Write a single probe result to InfluxDB raw bucket.

        result_data: dict with keys: task_id, result_id, source_node, target, protocol, timestamp, metrics
        """
        metrics = result_data.get('metrics', {})
        point = Point('probe_result') \
            .tag('task_id', result_data['task_id']) \
            .tag('source_node', result_data.get('source_node', '')) \
            .tag('target', result_data.get('target', '')) \
            .tag('protocol', result_data.get('protocol', ''))

        # Write result_id as a field for dedup traceability
        result_id = result_data.get('result_id')
        if result_id:
            point = point.field('result_id', str(result_id))

        # Add fields based on available metrics
        field_map = {
            'latency': float, 'packet_loss': float, 'jitter': float,
            'success': bool, 'status_code': int, 'dns_time': float,
            'tcp_time': float, 'tls_time': float, 'ttfb': float,
            'total_time': float, 'resolved_ip': str
        }
        for field_name, field_type in field_map.items():
            value = metrics.get(field_name)
            if value is not None:
                if field_type == bool:
                    point = point.field(field_name, bool(value))
                elif field_type == float:
                    point = point.field(field_name, float(value))
                elif field_type == int:
                    point = point.field(field_name, int(value))
                else:
                    point = point.field(field_name, str(value))

        # Store MTR hops as JSON string
        hops = metrics.get('hops')
        if hops is not None:
            import json as _json
            point = point.field('hops', _json.dumps(hops, ensure_ascii=False))

        # Store extra metadata (e.g. mtr_src, mtr_dst) as JSON string
        extra = metrics.get('extra')
        if extra is not None:
            import json as _json
            point = point.field('extra', _json.dumps(extra, ensure_ascii=False))

        # Set timestamp
        ts = result_data.get('timestamp')
        if ts:
            if isinstance(ts, str):
                point = point.time(ts, WritePrecision.S)
            else:
                point = point.time(ts, WritePrecision.NS)

        self.write_api.write(bucket=self.bucket_raw, record=point)

    def check_result_exists(self, result_id, task_id):
        """Check if a result_id already exists using memory cache + persistent SQLite."""
        if not result_id:
            return False
        now = time.time()
        # Fast path: check memory cache
        with _dedup_lock:
            # Evict expired entries
            while _dedup_cache:
                oldest_key, oldest_time = next(iter(_dedup_cache.items()))
                if now - oldest_time > _DEDUP_TTL:
                    _dedup_cache.pop(oldest_key)
                else:
                    break
            if result_id in _dedup_cache:
                return True
        # Slow path: check persistent SQLite
        if _dedup_db_path:
            with _dedup_db_lock:
                conn = sqlite3.connect(_dedup_db_path)
                try:
                    cursor = conn.execute(
                        'SELECT 1 FROM written_results WHERE result_id = ?', (result_id,))
                    exists = cursor.fetchone() is not None
                finally:
                    conn.close()
                if exists:
                    # Backfill memory cache
                    with _dedup_lock:
                        _dedup_cache[result_id] = now
                    return True
        return False

    def mark_result_written(self, result_id):
        """Mark a result_id as written in both memory cache and persistent SQLite."""
        if not result_id:
            return
        now = time.time()
        with _dedup_lock:
            _dedup_cache[result_id] = now
            _dedup_cache.move_to_end(result_id)
            # Cap size
            while len(_dedup_cache) > _DEDUP_MAX_SIZE:
                _dedup_cache.popitem(last=False)
        # Persist to SQLite
        if _dedup_db_path:
            with _dedup_db_lock:
                conn = sqlite3.connect(_dedup_db_path)
                try:
                    conn.execute(
                        'INSERT OR IGNORE INTO written_results (result_id, written_at) VALUES (?, ?)',
                        (result_id, now))
                    conn.commit()
                finally:
                    conn.close()

    def query_task_data(self, task_id, time_range='6h'):
        """Query time-series data for a specific task.
        Falls back to raw bucket with server-side aggregation if agg bucket is empty.
        """
        bucket = self._select_bucket(time_range)
        results = self._query_task_data_from_bucket(task_id, time_range, bucket)

        # Fallback: if using an aggregation bucket and got no data, query raw with aggregation
        if not results and bucket != self.bucket_raw:
            agg_window = '1h' if bucket == self.bucket_1h else '1m'
            results = self._query_task_data_aggregated_from_raw(task_id, time_range, agg_window)

        return results

    def _query_task_data_from_bucket(self, task_id, time_range, bucket):
        """Direct query from a specific bucket."""
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r.task_id == "{task_id}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
        tables = self.query_api.query(flux, org=self.org)
        results = []
        for table in tables:
            for record in table.records:
                row = {
                    'timestamp': record.get_time().isoformat(),
                    'latency': record.values.get('latency'),
                    'packet_loss': record.values.get('packet_loss'),
                    'jitter': record.values.get('jitter'),
                    'success': record.values.get('success'),
                    'status_code': record.values.get('status_code'),
                    'dns_time': record.values.get('dns_time'),
                    'tcp_time': record.values.get('tcp_time'),
                    'tls_time': record.values.get('tls_time'),
                    'ttfb': record.values.get('ttfb'),
                    'total_time': record.values.get('total_time'),
                    'resolved_ip': record.values.get('resolved_ip'),
                }
                hops_raw = record.values.get('hops')
                if hops_raw:
                    import json as _json
                    try:
                        row['hops'] = _json.loads(hops_raw)
                    except (ValueError, TypeError):
                        row['hops'] = None
                extra_raw = record.values.get('extra')
                if extra_raw:
                    import json as _json
                    try:
                        row['extra'] = _json.loads(extra_raw)
                    except (ValueError, TypeError):
                        row['extra'] = None
                results.append(row)
        return results

    def _query_task_data_aggregated_from_raw(self, task_id, time_range, window):
        """Fallback: aggregate raw data on-the-fly when agg bucket is empty."""
        flux = f'''
import "math"

numeric = from(bucket: "{self.bucket_raw}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r.task_id == "{task_id}")
  |> filter(fn: (r) => r._field == "latency" or r._field == "packet_loss" or r._field == "jitter"
                     or r._field == "status_code"
                     or r._field == "dns_time" or r._field == "tcp_time"
                     or r._field == "tls_time" or r._field == "ttfb" or r._field == "total_time")
  |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)

bools = from(bucket: "{self.bucket_raw}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r.task_id == "{task_id}")
  |> filter(fn: (r) => r._field == "success")
  |> map(fn: (r) => ({{r with _value: if r._value then 1.0 else 0.0}}))
  |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)

union(tables: [numeric, bools])
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
        tables = self.query_api.query(flux, org=self.org)
        results = []
        for table in tables:
            for record in table.records:
                success_val = record.values.get('success')
                results.append({
                    'timestamp': record.get_time().isoformat(),
                    'latency': record.values.get('latency'),
                    'packet_loss': record.values.get('packet_loss'),
                    'jitter': record.values.get('jitter'),
                    'success': success_val > 0.5 if success_val is not None else None,
                    'status_code': record.values.get('status_code'),
                    'dns_time': record.values.get('dns_time'),
                    'tcp_time': record.values.get('tcp_time'),
                    'tls_time': record.values.get('tls_time'),
                    'ttfb': record.values.get('ttfb'),
                    'total_time': record.values.get('total_time'),
                    'resolved_ip': None,
                })
        return results

    def query_task_stats(self, task_id, time_range='24h'):
        """Query statistics for a specific task."""
        bucket = self._select_bucket(time_range)
        flux = f'''
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r.task_id == "{task_id}")
  |> filter(fn: (r) => r._field == "latency" or r._field == "packet_loss" or r._field == "success")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
'''
        tables = self.query_api.query(flux, org=self.org)
        latencies = []
        losses = []
        total = 0
        success_count = 0
        for table in tables:
            for record in table.records:
                total += 1
                lat = record.values.get('latency')
                if lat is not None:
                    latencies.append(lat)
                loss = record.values.get('packet_loss')
                if loss is not None:
                    losses.append(loss)
                if record.values.get('success'):
                    success_count += 1

        if not latencies:
            return {
                'avg_latency': None, 'max_latency': None, 'min_latency': None, 'p95_latency': None,
                'avg_packet_loss': None, 'total_probes': total, 'success_count': success_count,
                'availability': 0
            }

        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        return {
            'avg_latency': round(sum(latencies) / len(latencies), 2),
            'max_latency': round(max(latencies), 2),
            'min_latency': round(min(latencies), 2),
            'p95_latency': round(latencies[min(p95_idx, len(latencies) - 1)], 2),
            'avg_packet_loss': round(sum(losses) / len(losses), 2) if losses else None,
            'total_probes': total,
            'success_count': success_count,
            'availability': round(success_count / total * 100, 2) if total > 0 else 0,
        }

    def _select_bucket(self, time_range):
        """Select appropriate bucket based on time range.

        v0.130 scheme: ≤1h → raw (秒), ≤3d → agg_1m (分), >3d → agg_1h (时)
        """
        hours = self._parse_range_to_hours(time_range)
        if hours <= 1:
            return self.bucket_raw
        elif hours <= 3 * 24:
            return self.bucket_1m
        else:
            return self.bucket_1h

    @staticmethod
    def _parse_range_to_hours(time_range):
        """Parse time range string like '30m', '6h', '3d' to hours."""
        if time_range.endswith('m'):
            return int(time_range[:-1]) / 60
        elif time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        return 6  # default


influx_service = InfluxService()
