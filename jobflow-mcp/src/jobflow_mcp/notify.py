"""MCP → Vercel Slack 알림 모듈.

fire_notify()는 비동기 fire-and-forget 방식으로 동작한다.
실패해도 태스크 작업에 영향을 주지 않는다.

⚠️  채널 정책: Slack Incoming Webhook은 개인 DM 채널 전용으로 구성할 것.
    팀 채널 사용 시 대시보드 URL이 채널 멤버 전원에게 노출된다.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config as cfg

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


async def _notify_event(event_type: str, payload: dict) -> None:
    """Vercel /api/slack/notify 엔드포인트에 POST — 실패 시 조용히 무시."""
    import httpx

    dashboard_url = cfg.get("vercel.dashboard_url", "")
    if not dashboard_url:
        logger.debug("vercel.dashboard_url 미설정, 알림 스킵")
        return

    secret = os.environ.get("NOTIFY_SECRET")
    if not secret:
        logger.warning("NOTIFY_SECRET 미설정, 알림 스킵")
        return

    body = {
        "event":     event_type,
        "secret":    secret,
        "timestamp": datetime.now(tz=KST).isoformat(),
        **payload,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{dashboard_url}/api/slack/notify", json=body)
            if resp.status_code not in (200, 201):
                logger.debug("알림 응답 비정상: %s %s", resp.status_code, resp.text[:100])
    except Exception as e:
        logger.debug("알림 실패 (무시): %s", e)


def fire_notify(event_type: str, payload: dict) -> None:
    """MCP 도구에서 호출하는 진입점.

    config.yaml의 slack.notify_events 목록에 없는 이벤트는 전송 생략.
    asyncio 이벤트 루프가 있으면 create_task로, 없으면 asyncio.run으로 실행.
    """
    allowed: list = cfg.get("slack.notify_events") or []
    if allowed and event_type not in allowed:
        logger.debug("notify_events 목록에 없음, 스킵: %s", event_type)
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_notify_event(event_type, payload))
    except RuntimeError:
        # 이벤트 루프가 없는 컨텍스트 (테스트, CLI 등): 동기 실행
        try:
            asyncio.run(_notify_event(event_type, payload))
        except Exception as e:
            logger.debug("asyncio.run 알림 실패 (무시): %s", e)
