"""Disari olay bildirimi: ihlal/kriz olaylari yapilandirilmis webhook URL'lerine POST edilir.

CRM, Slack/Teams gibi sistemlere genel amacli JSON webhook. Hata olsa bile
pipeline'i dusurmez (best-effort).
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def emit(event: str, payload: dict) -> None:
    urls = settings.webhook_url_list
    if not urls:
        return
    body = {"event": event, "data": payload}
    for url in urls:
        try:
            httpx.post(url, json=body, timeout=10)
        except httpx.HTTPError as exc:
            logger.warning("Webhook gonderilemedi (%s): %s", url, exc)
