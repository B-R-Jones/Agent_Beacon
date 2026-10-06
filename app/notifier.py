"""Notification service: Asynchronous Discord Webhook dispatch with rich embeds."""
import logging
from typing import Optional
import httpx

from app.config import get_settings

logger = logging.getLogger("beacon.notifier")


async def send_discord_notification(
    agent_identity: str,
    message: str,
    solve_latency_ms: int,
    parent_mission: Optional[str] = None,
    software_stack: Optional[str] = None,
    ip_address: Optional[str] = None,
):
    """
    Sends an alert to Discord via webhook if configured.
    Fails gracefully without impacting the HTTP intake lifecycle.
    """
    settings = get_settings()
    webhook_url = settings.DISCORD_WEBHOOK_URL

    if not webhook_url or not webhook_url.strip():
        # Webhook not configured; silent no-op
        return

    fields = [
        {"name": "🤖 Agent Identity", "value": agent_identity[:100], "inline": True},
        {"name": "⚡ Turnaround Latency", "value": f"{solve_latency_ms:,} ms", "inline": True},
    ]

    if software_stack:
        fields.append({"name": "🛠️ Software Stack", "value": software_stack[:100], "inline": True})

    if parent_mission:
        fields.append({"name": "🎯 Visiting Mission / Goal", "value": parent_mission[:250], "inline": False})

    fields.append({"name": "📝 Dispatch Message", "value": f"```\n{message[:800]}\n```", "inline": False})

    if ip_address:
        fields.append({"name": "🌐 Origin IP", "value": ip_address[:50], "inline": True})

    payload = {
        "username": "AI Beacon Station",
        "avatar_url": "https://raw.githubusercontent.com/google/material-design-icons/master/png/action/satellite/materialicons/48dp/1x/baseline_satellite_black_48dp.png",
        "embeds": [
            {
                "title": "🛰️ New Autonomous Agent Dispatch Intercepted",
                "description": "An autonomous AI agent traversing the web has successfully cleared the inverted CAPTCHA challenge and registered a log entry.",
                "color": 0x00FF99,  # Neon green / cyber aesthetic
                "fields": fields,
                "footer": {"text": "Autonomous Agent Beacon & Intake Station • Constructed by Agentic AI"},
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code >= 400:
                logger.warning(f"Discord webhook responded with HTTP {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.warning(f"Failed to deliver Discord alert: {exc}")
