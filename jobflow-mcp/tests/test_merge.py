"""merge.py 단위 테스트 — Task 단위 충돌 감지 및 병합."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jobflow_mcp.file_parser import Job, Task, TaskStatus
from jobflow_mcp.merge import TaskConflict, merge_job

KST = ZoneInfo("Asia/Seoul")


# ── 픽스처 ──────────────────────────────────────────────────────────────────────

def _dt(hour: int) -> datetime:
    return datetime(2026, 4, 14, hour, 0, 0, tzinfo=KST)


def _task(id: str, title: str, status: TaskStatus = TaskStatus.TODO, updated_hour: int = 9) -> Task:
    return Task(
        id         = id,
        title      = title,
        status     = status,
        updated_at = _dt(updated_hour),
    )


def _job(tasks: list[Task]) -> Job:
    return Job(
        job_id     = "job-20260414-001",
        job_name   = "test-job",
        goal       = "테스트",
        created_at = _dt(8),
        updated_at = _dt(9),
        version    = 1,
        status     = "in_progress",
        tasks      = tasks,
    )


# ── 충돌 없음 ────────────────────────────────────────────────────────────────────

def test_merge_no_conflict_local_only():
    """로컬에만 있는 Task → 그대로 유지."""
    local  = _job([_task("TASK-001", "로컬 태스크")])
    remote = _job([])

    merged = merge_job(local, remote)
    assert len(merged.tasks) == 1
    assert merged.tasks[0].id == "TASK-001"


def test_merge_no_conflict_remote_only():
    """원격에만 있는 Task → 병합에 포함."""
    local  = _job([])
    remote = _job([_task("TASK-001", "원격 태스크")])

    merged = merge_job(local, remote)
    assert len(merged.tasks) == 1
    assert merged.tasks[0].id == "TASK-001"


def test_merge_no_conflict_different_tasks():
    """서로 다른 Task를 수정한 경우 → 자동 병합."""
    local  = _job([_task("TASK-001", "로컬 수정", updated_hour=10)])
    remote = _job([_task("TASK-002", "원격 수정", updated_hour=11)])

    merged = merge_job(local, remote)
    ids = {t.id for t in merged.tasks}
    assert ids == {"TASK-001", "TASK-002"}


def test_merge_identical_tasks():
    """양쪽 동일 Task → 로컬 사용."""
    t      = _task("TASK-001", "동일 태스크")
    local  = _job([t])
    remote = _job([replace(t)])  # 동일한 값의 새 객체

    merged = merge_job(local, remote)
    assert len(merged.tasks) == 1


def test_merge_same_updated_at():
    """updated_at 동일 → 로컬 우선."""
    local  = _job([_task("TASK-001", "로컬 제목", updated_hour=10)])
    remote = _job([_task("TASK-001", "원격 제목", updated_hour=10)])

    merged = merge_job(local, remote)
    assert merged.tasks[0].title == "로컬 제목"


# ── 충돌 발생 ────────────────────────────────────────────────────────────────────

def test_merge_conflict_raises():
    """동일 Task를 양쪽에서 다른 시각에 수정 → TaskConflict 발생."""
    local  = _job([_task("TASK-001", "로컬 버전", updated_hour=10)])
    remote = _job([_task("TASK-001", "원격 버전", updated_hour=11)])

    with pytest.raises(TaskConflict) as exc_info:
        merge_job(local, remote)

    assert "TASK-001" in exc_info.value.conflicts
    conflict = exc_info.value.conflicts["TASK-001"]
    assert conflict["local"]["title"]  == "로컬 버전"
    assert conflict["remote"]["title"] == "원격 버전"


def test_merge_multiple_conflicts():
    """복수 Task 충돌 시 모두 포함된 TaskConflict."""
    local  = _job([
        _task("TASK-001", "로컬1", updated_hour=10),
        _task("TASK-002", "로컬2", updated_hour=10),
    ])
    remote = _job([
        _task("TASK-001", "원격1", updated_hour=11),
        _task("TASK-002", "원격2", updated_hour=11),
    ])

    with pytest.raises(TaskConflict) as exc_info:
        merge_job(local, remote)

    assert {"TASK-001", "TASK-002"} == set(exc_info.value.conflicts.keys())


# ── resolutions로 충돌 해결 ────────────────────────────────────────────────────

def test_merge_with_resolution_local():
    """resolution="local" → 로컬 버전 선택."""
    local  = _job([_task("TASK-001", "로컬 버전", updated_hour=10)])
    remote = _job([_task("TASK-001", "원격 버전", updated_hour=11)])

    merged = merge_job(local, remote, resolutions={"TASK-001": "local"})
    assert merged.tasks[0].title == "로컬 버전"


def test_merge_with_resolution_remote():
    """resolution="remote" → 원격 버전 선택."""
    local  = _job([_task("TASK-001", "로컬 버전", updated_hour=10)])
    remote = _job([_task("TASK-001", "원격 버전", updated_hour=11)])

    merged = merge_job(local, remote, resolutions={"TASK-001": "remote"})
    assert merged.tasks[0].title == "원격 버전"


def test_merge_partial_resolution_still_conflicts():
    """일부 Task만 resolution 지정 → 나머지는 여전히 충돌."""
    local  = _job([
        _task("TASK-001", "로컬1", updated_hour=10),
        _task("TASK-002", "로컬2", updated_hour=10),
    ])
    remote = _job([
        _task("TASK-001", "원격1", updated_hour=11),
        _task("TASK-002", "원격2", updated_hour=11),
    ])

    # TASK-001만 해결, TASK-002는 미해결
    with pytest.raises(TaskConflict) as exc_info:
        merge_job(local, remote, resolutions={"TASK-001": "local"})

    assert "TASK-002" in exc_info.value.conflicts
    assert "TASK-001" not in exc_info.value.conflicts


def test_merge_preserves_local_job_metadata():
    """병합 결과의 job 메타데이터는 local 기준."""
    local  = _job([_task("TASK-001", "태스크")])
    remote = _job([_task("TASK-001", "태스크")])
    remote = replace(remote, job_name="다른이름", goal="다른목표")

    merged = merge_job(local, remote)
    assert merged.job_name == "test-job"
    assert merged.goal     == "테스트"


def test_merge_updates_updated_at():
    """병합 후 updated_at이 갱신된다."""
    before = _dt(9)
    local  = _job([_task("TASK-001", "태스크")])
    remote = _job([_task("TASK-001", "태스크")])

    merged = merge_job(local, remote)
    assert merged.updated_at > before


def test_merge_tasks_sorted_by_id():
    """병합된 태스크 목록이 ID 순으로 정렬된다."""
    local  = _job([_task("TASK-003", "세 번째")])
    remote = _job([_task("TASK-001", "첫 번째"), _task("TASK-002", "두 번째")])

    merged = merge_job(local, remote)
    ids = [t.id for t in merged.tasks]
    assert ids == ["TASK-001", "TASK-002", "TASK-003"]


def test_merge_invalid_resolution_raises():
    """resolution 값이 'local'/'remote' 아닌 경우 ValueError."""
    local  = _job([_task("TASK-001", "로컬", updated_hour=10)])
    remote = _job([_task("TASK-001", "원격", updated_hour=11)])

    with pytest.raises(ValueError, match="local.*remote"):
        merge_job(local, remote, resolutions={"TASK-001": "both"})
