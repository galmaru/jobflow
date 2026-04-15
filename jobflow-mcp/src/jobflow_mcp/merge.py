"""Task 단위 충돌 감지 및 병합 모듈.

두 Job 객체를 Task ID 단위로 비교하여 자동 병합하거나
충돌 정보를 TaskConflict 예외로 반환한다.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from .file_parser import Job, Task

KST = ZoneInfo("Asia/Seoul")


class TaskConflict(Exception):
    """Task 단위 충돌이 감지되었을 때 발생하는 예외."""

    def __init__(self, conflicts: dict[str, dict]) -> None:
        self.conflicts = conflicts
        super().__init__(f"태스크 충돌 감지: {list(conflicts.keys())}")


def _task_summary(t: Task) -> dict:
    """Task → JSON 직렬화 가능한 요약 dict.

    Enum과 datetime은 문자열로 변환한다
    (dataclasses.asdict()는 이들을 변환하지 않음).
    """
    return {
        "title":      t.title,
        "status":     t.status.value,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def merge_job(
    local:       Job,
    remote:      Job,
    resolutions: dict[str, str] | None = None,
) -> Job:
    """두 Job을 Task 단위로 병합.

    병합 규칙:
    - 한쪽에만 있는 Task → 해당 쪽 사용
    - 양쪽 동일 → local 사용
    - updated_at 동일 → local 사용
    - resolutions에 명시된 Task → 지정된 쪽 사용
    - 양쪽 모두 수정 (updated_at 다름) + resolutions 없음 → TaskConflict 발생

    Args:
        local:       로컬 Job 객체
        remote:      원격 Job 객체
        resolutions: { task_id: "local" | "remote" } 충돌 해결 방침

    Returns:
        병합된 Job 객체 (local 메타데이터 기반, tasks/updated_at 교체)

    Raises:
        TaskConflict: 미해결 충돌이 있을 때
    """
    resolutions = resolutions or {}

    local_by_id  = {t.id: t for t in local.tasks}
    remote_by_id = {t.id: t for t in remote.tasks}
    all_ids      = sorted(set(local_by_id) | set(remote_by_id))

    merged:    list[Task] = []
    conflicts: dict[str, dict] = {}

    for tid in all_ids:
        l = local_by_id.get(tid)
        r = remote_by_id.get(tid)

        if l and not r:
            # 로컬에만 존재
            merged.append(l)

        elif r and not l:
            # 원격에만 존재
            merged.append(r)

        elif l == r:
            # 동일 (dataclass 동등 비교)
            merged.append(l)

        elif _same_updated_at(l, r):
            # updated_at이 같으면 로컬 우선
            merged.append(l)

        elif tid in resolutions:
            # 사용자가 해결 방침을 지정
            chosen = resolutions[tid]
            if chosen == "local":
                merged.append(l)
            elif chosen == "remote":
                merged.append(r)
            else:
                raise ValueError(f"resolutions 값은 'local' 또는 'remote'이어야 합니다: {chosen}")

        else:
            # 양쪽 모두 수정 → 충돌
            conflicts[tid] = {
                "local":  _task_summary(l),
                "remote": _task_summary(r),
            }

    if conflicts:
        raise TaskConflict(conflicts)

    return replace(
        local,
        tasks      = merged,
        updated_at = datetime.now(tz=KST),
    )


def _same_updated_at(a: Task, b: Task) -> bool:
    """두 Task의 updated_at이 동일한지 비교.

    None == None도 True로 처리한다.
    """
    if a.updated_at is None and b.updated_at is None:
        return True
    if a.updated_at is None or b.updated_at is None:
        return False
    # timezone-aware datetime 비교 (UTC 기준 정규화)
    return a.updated_at.utctimetuple() == b.updated_at.utctimetuple()
