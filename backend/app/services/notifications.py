"""Slack/Teams bildirimi (Dalga 4b).

Webhook (webhooks.py) makine-makine JSON gonderir; bu modul INSANA okunur
mesajlar uretip Slack/Teams incoming webhook'larina dusurur. Ikisi de basit
{"text": ...} govdesini kabul eder (Teams'in eski connector'lari ve yeni
Workflows akislari dahil), bu yuzden tek format yeterli.

Best-effort: gonderim hatasi pipeline'i dusurmez. Hangi olaylarin dusecegi
NOTIFY_EVENTS ile yapilandirilir.
"""

from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_EVENT_EMOJI = {
    "zeroing": "🚫", "crisis": "🚨", "banned_word": "⛔",
    "low_score": "📉", "score_drop": "📉",
}
_EVENT_LABEL = {
    "zeroing": "Sifirlayici ihlal", "crisis": "KRIZ cagrisi",
    "banned_word": "Yasakli ifade", "low_score": "Dusuk puan",
    "score_drop": "Puan dususu",
}


def _format_text(event: str, payload: dict) -> str:
    emoji = _EVENT_EMOJI.get(event, "🔔")
    label = _EVENT_LABEL.get(event, event)
    parts = [f"{emoji} *KaliteGoz — {label}*"]
    if payload.get("agent"):
        parts.append(f"Temsilci: {payload['agent']}")
    if payload.get("message"):
        parts.append(payload["message"])
    if payload.get("call_id"):
        parts.append(f"Cagri #{payload['call_id']}")
    if payload.get("total_score") is not None:
        parts.append(f"Puan: {payload['total_score']}")
    return "\n".join(parts)


def _post(url: str, text: str) -> None:
    try:
        httpx.post(url, json={"text": text}, timeout=10)
    except httpx.HTTPError as exc:
        logger.warning("Bildirim gonderilemedi (%s): %s", url[:40], exc)


def notify(event: str, payload: dict) -> int:
    """Olayi Slack/Teams'e gonderir. Gonderilen kanal sayisini doner.

    - Olay NOTIFY_EVENTS listesinde degilse hic gonderilmez.
    - URL tanimli degilse o kanal atlanir.
    """
    if event not in settings.notify_event_set:
        return 0
    text = _format_text(event, payload)
    sent = 0
    if settings.slack_webhook_url:
        _post(settings.slack_webhook_url, text)
        sent += 1
    if settings.teams_webhook_url:
        _post(settings.teams_webhook_url, text)
        sent += 1
    return sent
