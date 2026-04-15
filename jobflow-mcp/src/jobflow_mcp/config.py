"""config.yaml 전역 싱글톤 모듈.

첫 접근 시 ~/.jobflow/config.yaml을 로드하고 캐싱한다.
파일 변경 시 reload()를 호출하거나 _instance를 초기화한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

JOBFLOW_HOME = Path.home() / ".jobflow"
CONFIG_PATH  = JOBFLOW_HOME / "config.yaml"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if not CONFIG_PATH.exists():
        _cache = {}
        return _cache
    with CONFIG_PATH.open(encoding="utf-8") as f:
        _cache = yaml.safe_load(f) or {}
    return _cache


def reload() -> None:
    """캐시를 초기화하여 다음 접근 시 파일을 다시 읽도록 한다."""
    global _cache
    _cache = None


def get(key: str, default: Any = None) -> Any:
    """점 표기법 키로 설정값 조회.

    예: get("slack.notify_events") → ["task_done", ...]
        get("vercel.dashboard_url") → "https://..."
    """
    cfg   = _cache if _cache is not None else _load()
    parts = key.split(".")
    node  = cfg
    for part in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(part, default)
        if node is default:
            return default
    return node
