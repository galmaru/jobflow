"""CLAUDE.md 파일의 JobFlow 블록 자동 갱신 모듈.

<!-- JOBFLOW:START --> ... <!-- JOBFLOW:END --> 블록을
현재 In Progress 태스크 기준으로 교체한다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .file_parser import JOBFLOW_END, JOBFLOW_START, Job, TaskStatus

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
JOBFLOW_HOME = Path.home() / ".jobflow"
CONFIG_PATH  = JOBFLOW_HOME / "config.yaml"


def _load_linked_projects() -> list[str]:
    """config.yaml에서 linked_projects 목록 반환."""
    if not CONFIG_PATH.exists():
        return []
    with CONFIG_PATH.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config.get("linked_projects", [])


def _build_jobflow_block(job: Job) -> str:
    """Job 객체 → CLAUDE.md 삽입 블록 문자열 생성."""
    wip   = [t for t in job.tasks if t.status == TaskStatus.IN_PROGRESS]
    todo  = [t for t in job.tasks if t.status == TaskStatus.TODO]

    now_str = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")

    lines = [
        JOBFLOW_START,
        "## 현재 진행 중인 태스크",
        "",
        f"**Job:** {job.job_name} (`{job.job_id}`)",
        "**In Progress:**",
    ]

    if wip:
        for t in wip:
            tag_str = f" {t.tag}" if t.tag else ""
            lines.append(f"- [~] {t.id} {t.title}{tag_str}")
    else:
        lines.append("- (없음)")

    lines.append("")
    lines.append("**Next Todo:**")

    if todo:
        next_task = todo[0]
        tag_str = f" {next_task.tag}" if next_task.tag else ""
        lines.append(f"- [ ] {next_task.id} {next_task.title}{tag_str}")
    else:
        lines.append("- (없음)")

    lines.append("")
    lines.append(f"_마지막 동기화: {now_str}_")
    lines.append(JOBFLOW_END)

    return "\n".join(lines)


def inject_jobflow_block(claude_md_path: Path, block: str) -> None:
    """CLAUDE.md에 JobFlow 블록 삽입 또는 교체.

    - 블록이 이미 있으면 교체
    - 없으면 파일 끝에 추가
    """
    if claude_md_path.exists():
        content = claude_md_path.read_text(encoding="utf-8")
    else:
        content = ""

    if JOBFLOW_START in content and JOBFLOW_END in content:
        # 기존 블록 교체
        start_idx = content.index(JOBFLOW_START)
        end_idx   = content.index(JOBFLOW_END) + len(JOBFLOW_END)
        new_content = content[:start_idx] + block + content[end_idx:]
    else:
        # 파일 끝에 추가 (빈 줄 구분)
        separator = "\n\n" if content and not content.endswith("\n\n") else "\n"
        new_content = content + separator + block + "\n"

    claude_md_path.write_text(new_content, encoding="utf-8")
    logger.info("CLAUDE.md 블록 갱신 완료: %s", claude_md_path)


def update_claude_md_for_job(job_name: str) -> None:
    """특정 Job의 상태를 기준으로 연결된 CLAUDE.md 갱신.

    linked_projects 목록을 config.yaml에서 읽어 각 프로젝트의
    CLAUDE.md에 블록을 삽입한다.
    """
    from .job_manager import load_job

    try:
        job = load_job(job_name)
    except Exception as e:
        logger.warning("Job 로드 실패 (%s): %s", job_name, e)
        return

    block = _build_jobflow_block(job)
    projects = _load_linked_projects()

    for project_path in projects:
        claude_md = Path(project_path) / "CLAUDE.md"
        try:
            inject_jobflow_block(claude_md, block)
        except Exception as e:
            logger.warning("CLAUDE.md 갱신 실패 (%s): %s", project_path, e)


def update_all_claude_mds() -> None:
    """In Progress 상태의 모든 Job으로 연결된 CLAUDE.md 갱신.

    MCP 서버 시작 시 또는 pull 이후 호출한다.
    """
    from .job_manager import load_all_jobs
    from .file_parser import TaskStatus

    in_progress_jobs = [j for j in load_all_jobs() if j.status == "in_progress"]

    if not in_progress_jobs:
        return

    # 가장 최근 업데이트된 Job 하나로 블록 생성
    latest_job = max(in_progress_jobs, key=lambda j: j.updated_at or j.created_at)
    block      = _build_jobflow_block(latest_job)
    projects   = _load_linked_projects()

    for project_path in projects:
        claude_md = Path(project_path) / "CLAUDE.md"
        try:
            inject_jobflow_block(claude_md, block)
        except Exception as e:
            logger.warning("CLAUDE.md 갱신 실패 (%s): %s", project_path, e)
