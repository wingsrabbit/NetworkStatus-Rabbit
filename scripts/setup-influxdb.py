"""InfluxDB initialization script: create buckets, retention policies, and downsampling tasks."""
import os
import sys
import time

from influxdb_client import InfluxDBClient, BucketRetentionRules
from influxdb_client.client.exceptions import InfluxDBError


def wait_for_influxdb(url, token, retries=30, delay=2):
    """Wait for InfluxDB to become available."""
    client = InfluxDBClient(url=url, token=token)
    for i in range(retries):
        try:
            health = client.health()
            if health.status == 'pass':
                print(f"InfluxDB is ready (attempt {i + 1})")
                client.close()
                return True
        except Exception:
            pass
        print(f"Waiting for InfluxDB... (attempt {i + 1}/{retries})")
        time.sleep(delay)
    client.close()
    return False


def setup_influxdb():
    url = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
    token = os.environ.get('INFLUXDB_TOKEN', '')
    org = os.environ.get('INFLUXDB_ORG', 'networkstatus')

    if not wait_for_influxdb(url, token):
        print("ERROR: InfluxDB not available after retries")
        sys.exit(1)

    client = InfluxDBClient(url=url, token=token, org=org)
    buckets_api = client.buckets_api()

    # Bucket definitions: name -> retention (seconds), 0 = infinite
    bucket_defs = {
        'raw': 3 * 24 * 3600,        # 3 days
        'agg_1m': 7 * 24 * 3600,     # 7 days
        'agg_1h': 30 * 24 * 3600,    # 30 days
    }

    for bucket_name, retention_seconds in bucket_defs.items():
        existing = buckets_api.find_bucket_by_name(bucket_name)
        if existing:
            print(f"Bucket '{bucket_name}' already exists, skipping")
            continue

        retention_rules = BucketRetentionRules(
            type='expire',
            every_seconds=retention_seconds
        )
        buckets_api.create_bucket(
            bucket_name=bucket_name,
            retention_rules=retention_rules,
            org=org
        )
        print(f"Created bucket '{bucket_name}' with retention {retention_seconds}s")

    # Create downsampling tasks
    tasks_api = client.tasks_api()

    # 1-minute aggregation task: raw -> agg_1m
    task_1m_flux = '''
option task = {name: "downsample_1m", every: 1m}

from(bucket: "raw")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r._field == "latency" or r._field == "packet_loss" or r._field == "jitter")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
  |> set(key: "_measurement", value: "probe_result")
  |> to(bucket: "agg_1m", org: "%s")
''' % org

    # 1-hour aggregation task: agg_1m -> agg_1h
    task_1h_flux = '''
option task = {name: "downsample_1h", every: 1h}

from(bucket: "agg_1m")
  |> range(start: -2h)
  |> filter(fn: (r) => r._measurement == "probe_result")
  |> filter(fn: (r) => r._field == "latency" or r._field == "packet_loss" or r._field == "jitter")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> set(key: "_measurement", value: "probe_result")
  |> to(bucket: "agg_1h", org: "%s")
''' % org

    # Check existing tasks before creating
    existing_tasks = tasks_api.find_tasks()
    existing_names = {t.name for t in existing_tasks}

    for task_name, flux in [('downsample_1m', task_1m_flux), ('downsample_1h', task_1h_flux)]:
        if task_name in existing_names:
            print(f"Task '{task_name}' already exists, skipping")
            continue
        try:
            tasks_api.create_task_every(
                name=task_name,
                flux=flux,
                every='1m' if '1m' in task_name else '1h',
                organization=org
            )
            print(f"Created downsampling task '{task_name}'")
        except InfluxDBError as e:
            print(f"Warning: Could not create task '{task_name}': {e}")

    client.close()
    print("InfluxDB setup complete")


if __name__ == '__main__':
    setup_influxdb()
