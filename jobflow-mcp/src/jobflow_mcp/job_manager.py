"""Job CRUD 관리 모듈.

~/.jobflow/jobs/ 디렉토리 내 todo-{name}.md 파일을 생성/조회/수정한다.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import git_ops
from .file_parser import (
    ChecklistItem,
    Job,
    Task,
    TaskStatus,
    parse_job_file,
    serialize_job,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
JOBFLOW_HOME = Path.home() / ".jobflow"
JOBS_DIR     = JOBFLOW_HOME / "jobs"

# job_name 허용 패턴: 영문, 숫자, 하이픈만
JOB_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _next_job_id() -> str:
    """당일 순번 기반 job_id 생성 (job-YYYYMMDD-NNN)."""
    today = datetime.now(tz=KST).strftime("%Y%m%d")
    prefix = f"job-{today}-"
    existing = [
        f.stem.split("job-")[-1]
        for f in JOBS_DIR.glob("*.md")
    ]
    existing_nums = []
    for job in load_all_jobs():
        if job.job_id.startswith(prefix):
            try:
                existing_nums.append(int(job.job_id[len(prefix):]))
            except ValueError:
                pass
    next_num = max(existing_nums, default=0) + 1
    return f"{prefix}{next_num:03d}"


def _job_file_path(job_name: str) -> Path:
    return JOBS_DIR / f"todo-{job_name}.md"


def _find_job_file(target: str) -> Path:
    """job_id 또는 job_name으로 파일 경로 검색."""
    # job_name 직접 매칭
    direct = _job_file_path(target)
    if direct.exists():
        return direct

    # job_id 로 전체 검색
    for path in JOBS_DIR.glob("*.md"):
        try:
            job = parse_job_file(path.read_text(encoding="utf-8"))
            if job.job_id == target or job.job_name == target:
                return path
        except Exception:
            continue
    raise FileNotFoundError(f"Job을 찾을 수 없습니다: {target}")


# ── 공개 API ──────────────────────────────────────────────────────────────────

def load_all_jobs() -> list[Job]:
    """jobs/ 내 모든 .md 파일 파싱 후 반환."""
    jobs = []
    for path in sorted(JOBS_DIR.glob("*.md")):
        try:
            jobs.append(parse_job_file(path.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning("파일 파싱 실패 (%s): %s", path.name, e)
    return jobs


def load_job(target: str) -> Job:
    """job_id 또는 job_name으로 Job 로드."""
    path = _find_job_file(target)
    return parse_job_file(path.read_text(encoding="utf-8"))


def save_job(job: Job) -> Path:
    """Job 객체를 파일로 저장 (기존 파일 덮어쓰기)."""
    path = _job_file_path(job.job_name)
    path.write_text(serialize_job(job), encoding="utf-8")
    return path


def job_new(
    name: str,
    goal: str,
    tasks: list[str] | None = None,
) -> dict:
    """새 Job 생성.

    Args:
        name:   업무명 (영문/숫자/-만 허용)
        goal:   자연어 업무 목표
        tasks:  선택적 태스크 제목 목록 (Claude가 미리 분할)

    Returns:
        { "job_id": str, "tasks_added": int, "file_path": str }
    """
    if not JOB_NAME_RE.match(name):
        raise ValueError(f"job_name은 영문 소문자/숫자/하이픈만 허용됩니다: {name}")

    path = _job_file_path(name)
    if path.exists():
        raise FileExistsError(f"이미 존재하는 Job입니다: {name}")

    now    = datetime.now(tz=KST)
    job_id = _next_job_id()

    task_objects: list[Task] = []
    if tasks:
        for i, title in enumerate(tasks, start=1):
            task_objects.append(
                Task(
                    id=f"TASK-{i:03d}",
                    title=title,
                    status=TaskStatus.TODO,
                    updated_at=now,
                )
            )

    job = Job(
        job_id     = job_id,
        job_name   = name,
        goal       = goal,
        created_at = now,
        updated_at = now,
        version    = 1,
        status     = "todo",
        tasks      = task_objects,
    )

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    save_job(job)

    rel_path = str(path.relative_to(JOBFLOW_HOME))
    git_ops.git_commit(
        f"feat(jobflow): create job {job_id} — {name}",
        [rel_path],
    )

    logger.info("Job 생성 완료: %s (%s)", job_id, name)
    return {
        "job_id":      job_id,
        "tasks_added": len(task_objects),
        "file_path":   str(path),
    }


def job_list() -> list[dict]:
    """모든 Job 요약 목록 반환.

    Returns:
        [{ job_id, job_name, status, done_tasks, total_tasks, updated_at }]
    """
    result = []
    for job in load_all_jobs():
        done  = sum(1 for t in job.tasks if t.status == TaskStatus.DONE)
        total = len(job.tasks)
        result.append({
            "job_id":      job.job_id,
            "job_name":    job.job_name,
            "status":      job.status,
            "done_tasks":  done,
            "total_tasks": total,
            "updated_at":  job.updated_at.isoformat() if job.updated_at else None,
        })
    return result


def job_status(target: str | None = None) -> str:
    """3컬럼 칸반 텍스트 렌더링.

    Args:
        target: job_id 또는 job_name (None이면 In Progress 전체)
    """
    if target:
        jobs = [load_job(target)]
    else:
        jobs = [j for j in load_all_jobs() if j.status == "in_progress"]

    if not jobs:
        return "진행 중인 Job이 없습니다."

    lines = []
    for job in jobs:
        todo  = [t for t in job.tasks if t.status == TaskStatus.TODO]
        wip   = [t for t in job.tasks if t.status == TaskStatus.IN_PROGRESS]
        done  = [t for t in job.tasks if t.status == TaskStatus.DONE]

        lines.append(f"\n📋 {job.job_name} ({job.job_id})")
        lines.append(f"   [🔵 Todo: {len(todo)}]  [🟡 In Progress: {len(wip)}]  [🟢 Done: {len(done)}]")
        lines.append("")

        col_width = 30
        header = f"  {'🔵 Todo':<{col_width}}  {'🟡 In Progress':<{col_width}}  {'🟢 Done'}"
        lines.append(header)
        lines.append("  " + "-" * (col_width * 3 + 8))

        max_rows = max(len(todo), len(wip), len(done), 1)
        for i in range(max_rows):
            t_cell = f"{todo[i].id} {todo[i].title[:20]}"  if i < len(todo)  else ""
            w_cell = f"{wip[i].id} {wip[i].title[:20]}"    if i < len(wip)   else ""
            d_cell = f"{done[i].id} {done[i].title[:20]}"  if i < len(done)  else ""
            lines.append(f"  {t_cell:<{col_width}}  {w_cell:<{col_width}}  {d_cell}")

    return "\n".join(lines)
