"""Webhook alerting for pipeline failures and stale data."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_alert(
    title: str,
    message: str,
    *,
    severity: str = "error",
    chain: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    items_total: Optional[int] = None,
    items_failed: Optional[int] = None,
) -> None:
    """Send an alert to the configured webhook (Discord or Slack).

    Does nothing if ``alert_webhook_url`` is not set. Failures are logged
    but never raised — alerting must not break the pipeline.
    """
    settings = get_settings()
    webhook_url = settings.alert_webhook_url
    if not webhook_url:
        return

    try:
        payload = _build_payload(
            webhook_url,
            title=title,
            message=message,
            severity=severity,
            chain=chain,
            duration_seconds=duration_seconds,
            items_total=items_total,
            items_failed=items_failed,
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info(f"Alert sent: {title}")
    except Exception as exc:
        logger.warning(f"Failed to send alert ({title}): {exc}")


def _build_payload(
    webhook_url: str,
    *,
    title: str,
    message: str,
    severity: str,
    chain: Optional[str],
    duration_seconds: Optional[float],
    items_total: Optional[int],
    items_failed: Optional[int],
) -> dict:
    """Build a webhook payload, detecting Discord vs Slack by URL."""
    color_map = {"error": 0xFF0000, "warning": 0xFFA500, "info": 0x00BFFF}
    color = color_map.get(severity, 0x808080)

    fields = []
    if chain:
        fields.append(("Chain", chain, True))
    if duration_seconds is not None:
        fields.append(("Duration", f"{duration_seconds:.0f}s", True))
    if items_total is not None:
        fields.append(("Items", str(items_total), True))
    if items_failed is not None:
        fields.append(("Failed", str(items_failed), True))

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Discord webhook
    if "discord" in webhook_url:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "footer": {"text": f"Troll-E Pipeline | {timestamp}"},
        }
        if fields:
            embed["fields"] = [
                {"name": name, "value": value, "inline": inline}
                for name, value, inline in fields
            ]
        return {"embeds": [embed]}

    # Slack webhook (fallback)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": message},
        },
    ]
    if fields:
        field_text = " | ".join(f"*{n}:* {v}" for n, v, _ in fields)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": field_text},
        })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Troll-E Pipeline | {timestamp}"}],
    })
    return {"blocks": blocks}


__all__ = ["send_alert"]
