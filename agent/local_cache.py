"""Agent local SQLite cache for probe results (Section 6.4)."""
import sqlite3
import json
import time
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class LocalCache:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS local_results (
                result_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                ack_status TEXT NOT NULL DEFAULT 'pending',
                batch_id TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                sent_at DATETIME,
                acked_at DATETIME
            )
        ''')
        conn.commit()
        conn.close()

    def store_result(self, result_id, task_id, payload):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                'INSERT OR REPLACE INTO local_results (result_id, task_id, payload_json, ack_status, created_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (result_id, task_id, json.dumps(payload), 'pending',
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def mark_sent(self, result_id):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                'UPDATE local_results SET ack_status = ?, sent_at = ? WHERE result_id = ?',
                ('sent', datetime.now(timezone.utc).isoformat(), result_id)
            )
            conn.commit()
        finally:
            conn.close()

    def mark_acked(self, result_id):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                'UPDATE local_results SET ack_status = ?, acked_at = ? WHERE result_id = ?',
                ('acked', datetime.now(timezone.utc).isoformat(), result_id)
            )
            conn.commit()
        finally:
            conn.close()

    def mark_batch_acked(self, accepted_ids):
        if not accepted_ids:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now(timezone.utc).isoformat()
            placeholders = ','.join('?' for _ in accepted_ids)
            conn.execute(
                f'UPDATE local_results SET ack_status = ?, acked_at = ? '
                f'WHERE result_id IN ({placeholders})',
                ['acked', now] + list(accepted_ids)
            )
            conn.commit()
        finally:
            conn.close()

    def get_unacked_results(self):
        """Get all results that haven't been acked (for backfill)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT result_id, task_id, payload_json FROM local_results "
                "WHERE ack_status != 'acked' ORDER BY created_at ASC"
            )
            results = []
            for row in cursor:
                payload = json.loads(row[2])
                results.append(payload)
            return results
        finally:
            conn.close()

    def set_batch_id(self, result_ids, batch_id):
        """Assign a batch_id to a group of results for backfill tracking."""
        if not result_ids:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ','.join('?' for _ in result_ids)
            conn.execute(
                f'UPDATE local_results SET batch_id = ? WHERE result_id IN ({placeholders})',
                [batch_id] + list(result_ids)
            )
            conn.commit()
        finally:
            conn.close()

    def increment_retry_count(self, result_ids):
        """Increment retry_count for backfill retry tracking."""
        if not result_ids:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ','.join('?' for _ in result_ids)
            conn.execute(
                f'UPDATE local_results SET retry_count = retry_count + 1 '
                f'WHERE result_id IN ({placeholders})',
                list(result_ids)
            )
            conn.commit()
        finally:
            conn.close()

    def cleanup_old_acked(self):
        """Remove acked results older than 3 days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM local_results WHERE ack_status = 'acked' AND acked_at < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old acked results")
        finally:
            conn.close()
