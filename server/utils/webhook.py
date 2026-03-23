import requests as http_requests
import logging

logger = logging.getLogger(__name__)


def send_webhook(url, payload):
    """Send a webhook notification. Returns True on success."""
    try:
        resp = http_requests.post(
            url,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        if resp.status_code < 400:
            return True
        logger.warning(f"Webhook returned status {resp.status_code}: {resp.text[:200]}")
        return False
    except http_requests.RequestException as e:
        logger.error(f"Webhook request failed: {e}")
        return False
