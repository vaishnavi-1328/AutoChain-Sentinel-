"""SMTP-based email alerts on CRITICAL_DELAY status transitions.

Sends one email per (user, order) on transition INTO CRITICAL_DELAY.
Tracks last-sent state in Redis (`alert:order:{order_id}` = last_status) to dedupe.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.db.redis import get_redis

log = logging.getLogger("chainpulse.email")

DEDUPE_TTL = 60 * 60 * 6  # 6h — re-alert if still critical after that


def _send_blocking(to_email: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.smtp_host or not s.smtp_user:
        log.warning("SMTP not configured; would have sent: %s", subject)
        return False
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("smtp send failed")
        return False


async def maybe_alert(user_email: str, order, analysis: dict) -> bool:
    """Send if order is CRITICAL_DELAY and we haven't alerted in last DEDUPE_TTL."""
    s = get_settings()
    if not s.alerts_enabled:
        return False
    if analysis.get("status") != "CRITICAL_DELAY":
        return False

    r = get_redis()
    key = f"alert:order:{order.id}"
    last = await r.get(key)
    if last == "CRITICAL_DELAY":
        return False  # already alerted

    matched = analysis.get("matched", [])
    causes = "\n".join(
        f"- {m.get('title','event')} ({m.get('source_name','source')}: {m.get('source_url','')})"
        for m in matched[:5]
    ) or "(no specific events listed)"

    subject = f"[ChainPulse] ⚠ CRITICAL_DELAY: {order.supplier_name}"
    body = (
        f"Order {order.id} status changed to CRITICAL_DELAY.\n\n"
        f"Supplier:  {order.supplier_name} ({order.supplier_city}, {order.supplier_country})\n"
        f"Materials: {order.materials}\n"
        f"Original ETA: {order.expected_delivery}\n"
        f"Estimated delay: +{analysis['delay_min']} to +{analysis['delay_max']} days\n"
        f"New ETA range: {analysis.get('new_eta_earliest','?')} → {analysis.get('new_eta_latest','?')}\n\n"
        f"Driven by:\n{causes}\n\n"
        f"Sign in to chainpulse to view full analysis and mitigation suggestions.\n"
    )

    sent = await asyncio.to_thread(_send_blocking, user_email, subject, body)
    if sent:
        await r.set(key, "CRITICAL_DELAY", ex=DEDUPE_TTL)
        log.info("alert sent to %s for order %s", user_email, order.id)
    return sent
