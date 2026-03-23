"""InfluxDB read/write service."""
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

# In-memory dedup cache: result_id -> insertion_time
# Evicts entries older than _DEDUP_TTL seconds, capped at _DEDUP_MAX_SIZE
_DEDUP_TTL = 600  # 10 minutes
_DEDUP_MAX_SIZE = 100_000
_dedup_cache: OrderedDict[str, float] = OrderedDict()
_dedup_lock = threading.Lock()


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

        # Set timestamp
        ts = result_data.get('timestamp')
        if ts:
            if isinstance(ts, str):
                point = point.time(ts, WritePrecision.S)
            else:
                point = point.time(ts, WritePrecision.NS)

        self.write_api.write(bucket=self.bucket_raw, record=point)

    def check_result_exists(self, result_id, task_id):
        """Check if a result_id already exists using in-memory dedup cache."""
        if not result_id:
            return False
        now = time.time()
        with _dedup_lock:
            # Evict expired entries
            while _dedup_cache:
                oldest_key, oldest_time = next(iter(_dedup_cache.items()))
                if now - oldest_time > _DEDUP_TTL:
                    _dedup_cache.pop(oldest_key)
                else:
                    break
            return result_id in _dedup_cache

    def mark_result_written(self, result_id):
        """Mark a result_id as written in the dedup cache."""
        if not result_id:
            return
        with _dedup_lock:
            _dedup_cache[result_id] = time.time()
            _dedup_cache.move_to_end(result_id)
            # Cap size
            while len(_dedup_cache) > _DEDUP_MAX_SIZE:
                _dedup_cache.popitem(last=False)

    def query_task_data(self, task_id, time_range='6h'):
        """Query time-series data for a specific task."""
        bucket = self._select_bucket(time_range)
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
                results.append({
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
        """Select appropriate bucket based on time range."""
        # Parse time range string to hours
        hours = self._parse_range_to_hours(time_range)
        if hours <= 24:
            return self.bucket_raw
        elif hours <= 7 * 24:
            return self.bucket_1m
        else:
            return self.bucket_1h

    @staticmethod
    def _parse_range_to_hours(time_range):
        """Parse time range string like '6h', '3d', '14d' to hours."""
        if time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        return 6  # default


influx_service = InfluxService()
