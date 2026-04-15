"""notify.py 단위 테스트 — graceful skip, fire_notify 로직."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── _notify_event graceful skip 테스트 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_skips_when_no_dashboard_url(monkeypatch):
    """vercel.dashboard_url 미설정 시 HTTP 요청 없이 조용히 스킵."""
    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", lambda key, default=None: None)

    with patch("httpx.AsyncClient") as mock_client:
        from jobflow_mcp.notify import _notify_event
        await _notify_event("task_done", {"job_id": "j1", "job_name": "테스트"})

    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_notify_skips_when_no_secret(monkeypatch):
    """NOTIFY_SECRET 미설정 시 HTTP 요청 없이 스킵."""
    def fake_get(key, default=None):
        if key == "vercel.dashboard_url":
            return "https://example.vercel.app"
        return default

    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", fake_get)
    monkeypatch.delenv("NOTIFY_SECRET", raising=False)

    with patch("httpx.AsyncClient") as mock_client:
        from jobflow_mcp.notify import _notify_event
        await _notify_event("task_done", {"job_id": "j1", "job_name": "테스트"})

    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_notify_sends_when_configured(monkeypatch):
    """dashboard_url + NOTIFY_SECRET 설정 시 HTTP POST 호출."""
    def fake_get(key, default=None):
        if key == "vercel.dashboard_url":
            return "https://example.vercel.app"
        return default

    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", fake_get)
    monkeypatch.setenv("NOTIFY_SECRET", "test-secret")

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    mock_client_instance.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        from jobflow_mcp.notify import _notify_event
        # 모듈 재임포트를 피하기 위해 직접 호출
        import importlib
        import jobflow_mcp.notify as notify_mod
        importlib.reload(notify_mod)

        await notify_mod._notify_event("task_done", {"job_id": "j1", "job_name": "테스트"})

    mock_client_instance.post.assert_called_once()
    call_url = mock_client_instance.post.call_args[0][0]
    assert "api/slack/notify" in call_url


@pytest.mark.asyncio
async def test_notify_ignores_http_failure(monkeypatch):
    """HTTP 요청 실패해도 예외를 발생시키지 않는다 (graceful)."""
    def fake_get(key, default=None):
        return "https://example.vercel.app" if key == "vercel.dashboard_url" else default

    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", fake_get)
    monkeypatch.setenv("NOTIFY_SECRET", "test-secret")

    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    mock_client_instance.post = AsyncMock(side_effect=Exception("네트워크 오류"))

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        import importlib
        import jobflow_mcp.notify as notify_mod
        importlib.reload(notify_mod)

        # 예외가 발생하지 않아야 한다
        await notify_mod._notify_event("task_done", {"job_id": "j1", "job_name": "테스트"})


# ── fire_notify 이벤트 필터 테스트 ────────────────────────────────────────────

def test_fire_notify_skips_unlisted_event(monkeypatch):
    """notify_events 목록에 없는 이벤트는 발송 생략."""
    def fake_get(key, default=None):
        if key == "slack.notify_events":
            return ["task_done"]  # stage_changed 없음
        if key == "vercel.dashboard_url":
            return "https://example.vercel.app"
        return default

    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", fake_get)

    called = []
    async def fake_notify(event, payload):
        called.append(event)

    monkeypatch.setattr("jobflow_mcp.notify._notify_event", fake_notify)

    from jobflow_mcp.notify import fire_notify
    fire_notify("stage_changed", {"job_id": "j1", "job_name": "n"})

    assert called == []


def test_fire_notify_sends_listed_event(monkeypatch):
    """notify_events 목록에 있는 이벤트는 발송."""
    def fake_get(key, default=None):
        if key == "slack.notify_events":
            return ["task_done", "stage_changed"]
        if key == "vercel.dashboard_url":
            return "https://example.vercel.app"
        return default

    monkeypatch.setattr("jobflow_mcp.notify.cfg.get", fake_get)

    called = []
    async def fake_notify(event, payload):
        called.append(event)

    monkeypatch.setattr("jobflow_mcp.notify._notify_event", fake_notify)

    from jobflow_mcp.notify import fire_notify
    fire_notify("task_done", {"job_id": "j1", "job_name": "n"})

    assert "task_done" in called
