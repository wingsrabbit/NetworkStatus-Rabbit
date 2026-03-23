#!/usr/bin/env python3
"""NetworkStatus-Rabbit Agent entry point."""
import logging
import sys
import time
import threading

from agent.config import AgentConfig
from agent.local_cache import LocalCache
from agent.scheduler import TaskScheduler
from agent.ws_client import WSClient

# Import probes to trigger registration
import agent.probes  # noqa


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    logger = logging.getLogger('agent')

    try:
        config = AgentConfig.from_args()
    except SystemExit:
        sys.exit(1)

    logger.info(f"NetworkStatus-Rabbit Agent starting...")
    logger.info(f"Node ID: {config.node_id}")
    logger.info(f"Server: {config.server_url}")

    # Initialize local cache
    cache = LocalCache(config.db_path)

    # Initialize scheduler (callback will be set after ws_client is created)
    def on_probe_result(task_id, protocol, result, seq, timestamp):
        ws_client.send_probe_result(task_id, protocol, result, seq, timestamp)

    scheduler = TaskScheduler(on_result_callback=on_probe_result)

    # Initialize WebSocket client
    ws_client = WSClient(config, cache, scheduler)

    # Periodic cleanup of old cached data (every hour)
    def cleanup_loop():
        while True:
            time.sleep(3600)
            try:
                cache.cleanup_old_acked()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()

    # Connect and run
    while True:
        try:
            ws_client.connect()
            ws_client.wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            ws_client.disconnect()
            break
        except Exception as e:
            logger.error(f"Connection error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == '__main__':
    main()
