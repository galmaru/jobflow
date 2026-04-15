"""Task CRUD 및 단계 이동 관리 모듈."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import git_ops
from .claude_md import update_claude_md_for_job
from .file_parser import ChecklistItem, Task, TaskStatus
from .job_manager import JOBFLOW_HOME, load_job, save_job
from .notify import fire_notify

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _next_task_id(existing_tasks: list[Task]) -> str:
    """기존 태스크 목록에서 다음 TASK-NNN 번호 결정."""
    nums = []
    for t in existing_tasks:
        try:
            nums.append(int(t.id.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"TASK-{max(nums, default=0) + 1:03d}"


def _commit_and_update(job_name: str, message: str, file_path: Path) -> None:
    """파일 커밋 후 연결된 CLAUDE.md 갱신."""
    rel = str(file_path.relative_to(JOBFLOW_HOME))
    git_ops.git_commit(message, [rel])
    try:
        update_claude_md_for_job(job_name)
    except Exception as e:
        logger.warning("CLAUDE.md 갱신 실패 (무시): %s", e)


# ── 공개 API ──────────────────────────────────────────────────────────────────

def task_add(
    job: str,
    title: str,
    tag: str | None = None,
    priority: str = "medium",
    checklist: list[str] | None = None,
) -> dict:
    """Job에 새 태스크 추가.

    Returns:
        { "task_id": str, "job_id": str }
    """
    job_obj  = load_job(job)
    now      = datetime.now(tz=KST)
    task_id  = _next_task_id(job_obj.tasks)

    cl_items = [ChecklistItem(text=t) for t in (checklist or [])]

    new_task = Task(
        id         = task_id,
        title      = title,
        status     = TaskStatus.TODO,
        tag        = tag,
        priority   = priority,
        checklist  = cl_items,
        updated_at = now,
    )

    job_obj.tasks.append(new_task)
    job_obj.version    += 1
    job_obj.updated_at  = now

    file_path = save_job(job_obj)
    _commit_and_update(
        job_obj.job_name,
        f"feat(jobflow): add {task_id} to {job_obj.job_id}",
        file_path,
    )

    fire_notify("task_added", {
        "job_id":     job_obj.job_id,
        "job_name":   job_obj.job_name,
        "task_id":    task_id,
        "task_title": title,
    })

    logger.info("태스크 추가: %s → %s", task_id, job_obj.job_id)
    return {"task_id": task_id, "job_id": job_obj.job_id}


def task_check(task_id: str, job: str | None = None) -> dict:
    """태스크를 다음 단계로 순차 이동 (Todo→InProgress→Done).

    Done에서 호출 시 에러 발생.

    Returns:
        { "task_id": str, "from": str, "to": str }
    """
    job_obj, task = _find_task(task_id, job)
    now   = datetime.now(tz=KST)
    from_ = task.status

    if task.status == TaskStatus.TODO:
        task.status     = TaskStatus.IN_PROGRESS
        task.started_at = now
    elif task.status == TaskStatus.IN_PROGRESS:
        task.status       = TaskStatus.DONE
        task.completed_at = now
    else:
        raise ValueError(f"{task_id}는 이미 Done 상태입니다. task_move로 되돌리세요.")

    task.updated_at  = now
    job_obj.version += 1
    job_obj.updated_at = now

    # Job 전체 status 자동 갱신
    _update_job_status(job_obj)

    file_path = save_job(job_obj)
    from_str = from_.value
    to_str   = task.status.value

    _commit_and_update(
        job_obj.job_name,
        f"chore(jobflow): {task_id} {from_str} → {to_str}",
        file_path,
    )

    event_type = "task_done" if to_str == "done" else "stage_changed"
    fire_notify(event_type, {
        "job_id":     job_obj.job_id,
        "job_name":   job_obj.job_name,
        "task_id":    task_id,
        "task_title": task.title,
        "from_stage": from_str,
        "to_stage":   to_str,
    })

    logger.info("%s: %s → %s", task_id, from_str, to_str)
    return {"task_id": task_id, "from": from_str, "to": to_str}


def task_move(task_id: str, to: str, job: str | None = None) -> dict:
    """태스크를 임의 단계로 이동 (되돌리기/건너뛰기).

    Args:
        task_id: 대상 태스크 ID
        to:      "todo" | "in_progress" | "done"

    Returns:
        { "task_id": str, "from": str, "to": str }
    """
    valid = {"todo", "in_progress", "done"}
    if to not in valid:
        raise ValueError(f"유효하지 않은 단계: {to}. 허용값: {valid}")

    job_obj, task = _find_task(task_id, job)
    now   = datetime.now(tz=KST)
    from_ = task.status.value

    target_status = TaskStatus(to)
    task.status   = target_status

    if target_status == TaskStatus.IN_PROGRESS:
        if task.started_at is None:
            task.started_at = now
    elif target_status == TaskStatus.DONE:
        task.completed_at = now
    elif target_status == TaskStatus.TODO:
        task.started_at   = None
        task.completed_at = None

    task.updated_at  = now
    job_obj.version += 1
    job_obj.updated_at = now

    _update_job_status(job_obj)

    file_path = save_job(job_obj)
    _commit_and_update(
        job_obj.job_name,
        f"chore(jobflow): {task_id} moved to {to}",
        file_path,
    )

    event_type = "task_done" if to == "done" else "stage_changed"
    fire_notify(event_type, {
        "job_id":     job_obj.job_id,
        "job_name":   job_obj.job_name,
        "task_id":    task_id,
        "task_title": task.title,
        "from_stage": from_,
        "to_stage":   to,
    })

    logger.info("%s 이동: %s → %s", task_id, from_, to)
    return {"task_id": task_id, "from": from_, "to": to}


# ── 내부 헬퍼 (로드 관련) ─────────────────────────────────────────────────────

def _find_task(task_id: str, job: str | None = None):
    """task_id 검색.

    Returns:
        (Job, Task) 튜플
    """
    from .job_manager import load_all_jobs

    if job is not None:
        job_obj = load_job(job)
        for task in job_obj.tasks:
            if task.id == task_id:
                return job_obj, task
        raise KeyError(f"해당 Job에서 태스크를 찾을 수 없습니다: {job} / {task_id}")

    matches = []
    for job_obj in load_all_jobs():
        for task in job_obj.tasks:
            if task.id == task_id:
                matches.append((job_obj, task))

    if not matches:
        raise KeyError(f"태스크를 찾을 수 없습니다: {task_id}")
    if len(matches) > 1:
        job_names = ", ".join(sorted(match[0].job_name for match in matches))
        raise ValueError(
            f"중복된 task_id입니다: {task_id}. job 인자를 함께 지정하세요. 후보 Job: {job_names}"
        )
    return matches[0]


def _update_job_status(job_obj) -> None:
    """태스크 상태 기반으로 Job 전체 status 자동 결정."""
    if not job_obj.tasks:
        return
    statuses = {t.status for t in job_obj.tasks}
    if all(t.status == TaskStatus.DONE for t in job_obj.tasks):
        job_obj.status = "done"
    elif TaskStatus.IN_PROGRESS in statuses or (
        TaskStatus.DONE in statuses and TaskStatus.TODO in statuses
    ):
        job_obj.status = "in_progress"
    else:
        job_obj.status = "todo"
