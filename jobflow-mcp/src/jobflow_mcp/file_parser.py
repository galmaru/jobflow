"""Markdown ↔ Python 객체 파싱 모듈.

todo-{name}.md 파일을 Job/Task 객체로 변환하거나
Job/Task 객체를 Markdown으로 직렬화한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import yaml
from dateutil import parser as dateutil_parser

# ── 상수 ──────────────────────────────────────────────────────────────────────

# 섹션 헤더 패턴 (3단계)
SECTION_TODO        = "### 🔵 Todo"
SECTION_IN_PROGRESS = "### 🟡 In Progress"
SECTION_DONE        = "### 🟢 Done"

SECTION_MARKERS = {
    SECTION_TODO:        "todo",
    SECTION_IN_PROGRESS: "in_progress",
    SECTION_DONE:        "done",
}

# HTML 주석 메타데이터 파싱 정규식
META_RE = re.compile(r"<!--\s*(\w+)\s*:\s*(.+?)\s*-->")

# 태스크 헤더 파싱 정규식
# 예: - [~] TASK-002 UI 컴포넌트 설계 #frontend !high
TASK_HEADER_RE = re.compile(
    r"^- \[(?P<status>[ ~x])\] (?P<id>TASK-\d+) (?P<title>[^#!]+?)"
    r"(?:\s+(?P<tags>(?:#\w+\s*)+))?(?:\s+(?P<priority>!\w+))?\s*$"
)

# 체크리스트 항목 파싱 정규식
CHECKLIST_RE = re.compile(r"^\s+- \[(?P<checked>[ x])\] (?P<text>.+)$")

# JOBFLOW 블록 구분자
JOBFLOW_START = "<!-- JOBFLOW:START -->"
JOBFLOW_END   = "<!-- JOBFLOW:END -->"


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

class TaskStatus(Enum):
    TODO        = "todo"
    IN_PROGRESS = "in_progress"
    DONE        = "done"


STATUS_SYMBOL: dict[TaskStatus, str] = {
    TaskStatus.TODO:        " ",
    TaskStatus.IN_PROGRESS: "~",
    TaskStatus.DONE:        "x",
}

SYMBOL_STATUS: dict[str, TaskStatus] = {v: k for k, v in STATUS_SYMBOL.items()}


@dataclass
class ChecklistItem:
    text: str
    checked: bool = False

    def to_markdown(self) -> str:
        mark = "x" if self.checked else " "
        return f"  - [{mark}] {self.text}"


@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    tag: Optional[str] = None
    priority: str = "medium"
    checklist: list[ChecklistItem] = field(default_factory=list)
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_markdown(self) -> str:
        """Task → Markdown 블록 직렬화."""
        symbol = STATUS_SYMBOL[self.status]
        tag_str = f" {self.tag}" if self.tag else ""
        priority_str = f" !{self.priority}" if self.priority else ""
        header = f"- [{symbol}] {self.id} {self.title}{tag_str}{priority_str}"

        lines = [header]
        for item in self.checklist:
            lines.append(item.to_markdown())

        # HTML 주석 메타데이터
        def _fmt(dt: Optional[datetime]) -> str:
            return dt.isoformat() if dt else "~"

        lines.append(f"  <!-- started_at: {_fmt(self.started_at)} -->")
        lines.append(f"  <!-- updated_at: {_fmt(self.updated_at)} -->")
        lines.append(f"  <!-- completed_at: {_fmt(self.completed_at)} -->")

        return "\n".join(lines)


@dataclass
class Job:
    job_id: str
    job_name: str
    goal: str
    created_at: datetime
    updated_at: datetime
    version: int
    status: str                              # todo | in_progress | done | archived
    tasks: list[Task] = field(default_factory=list)


# ── 파싱 헬퍼 ─────────────────────────────────────────────────────────────────

def parse_task_metadata(task_block: str) -> dict:
    """태스크 블록 내 HTML 주석에서 메타데이터 추출.
    값이 '~' 또는 빈 문자열이면 None 반환."""
    meta: dict = {}
    for key, val in META_RE.findall(task_block):
        meta[key] = None if val.strip() in ("~", "") else val.strip()
    return meta


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return dateutil_parser.isoparse(value)
    except (ValueError, TypeError):
        return None


def _parse_task_block(lines: list[str]) -> Optional[Task]:
    """태스크 블록(들여쓰기 포함) → Task 객체.
    lines[0]이 태스크 헤더 줄이어야 한다."""
    if not lines:
        return None

    header_match = TASK_HEADER_RE.match(lines[0])
    if not header_match:
        return None

    status_char = header_match.group("status")
    task_status = SYMBOL_STATUS.get(status_char, TaskStatus.TODO)

    task_id    = header_match.group("id")
    title      = header_match.group("title").strip()
    tags_raw   = (header_match.group("tags") or "").strip()
    priority_raw = header_match.group("priority")

    # 태그는 첫 번째만 사용 (단일 태그 정책)
    tag = tags_raw.split()[0] if tags_raw else None
    priority = priority_raw.lstrip("!") if priority_raw else "medium"

    checklist: list[ChecklistItem] = []
    block_text = "\n".join(lines)

    for line in lines[1:]:
        cl_match = CHECKLIST_RE.match(line)
        if cl_match:
            checklist.append(
                ChecklistItem(
                    text=cl_match.group("text"),
                    checked=(cl_match.group("checked") == "x"),
                )
            )

    meta = parse_task_metadata(block_text)

    return Task(
        id=task_id,
        title=title,
        status=task_status,
        tag=tag,
        priority=priority,
        checklist=checklist,
        started_at=_parse_datetime(meta.get("started_at")),
        updated_at=_parse_datetime(meta.get("updated_at")),
        completed_at=_parse_datetime(meta.get("completed_at")),
    )


def _split_task_blocks(lines: list[str]) -> list[list[str]]:
    """섹션 내 줄 목록을 태스크 블록 단위로 분할.
    태스크 헤더(- [ ] TASK-...)를 기준으로 분리한다."""
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if TASK_HEADER_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


# ── 공개 API ──────────────────────────────────────────────────────────────────

def parse_job_file(content: str) -> Job:
    """todo-{name}.md 파일 내용 → Job 객체."""
    # frontmatter 분리
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_raw = parts[1]
            body   = parts[2]
        else:
            raise ValueError("frontmatter 파싱 실패: '---' 구분자가 부족합니다.")
    else:
        raise ValueError("frontmatter가 없는 파일입니다.")

    fm = yaml.safe_load(fm_raw)

    job = Job(
        job_id     = fm["job_id"],
        job_name   = fm["job_name"],
        goal       = fm["goal"],
        created_at = _parse_datetime(str(fm["created_at"])),
        updated_at = _parse_datetime(str(fm["updated_at"])),
        version    = int(fm.get("version", 1)),
        status     = fm.get("status", "todo"),
    )

    # 섹션별 태스크 파싱
    current_section: Optional[str] = None
    section_lines: list[str] = []
    tasks: list[Task] = []

    for line in body.splitlines():
        stripped = line.rstrip()

        if stripped in SECTION_MARKERS:
            # 이전 섹션 처리
            if current_section is not None:
                for block in _split_task_blocks(section_lines):
                    task = _parse_task_block(block)
                    if task:
                        tasks.append(task)
            current_section = SECTION_MARKERS[stripped]
            section_lines = []
        elif current_section is not None:
            section_lines.append(stripped)

    # 마지막 섹션 처리
    if current_section is not None:
        for block in _split_task_blocks(section_lines):
            task = _parse_task_block(block)
            if task:
                tasks.append(task)

    job.tasks = tasks
    return job


def serialize_job(job: Job) -> str:
    """Job 객체 → todo-{name}.md 파일 내용."""
    # frontmatter
    fm = {
        "job_id":     job.job_id,
        "job_name":   job.job_name,
        "goal":       job.goal,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "version":    job.version,
        "status":     job.status,
    }
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # 섹션별 태스크 분류
    todo_tasks        = [t for t in job.tasks if t.status == TaskStatus.TODO]
    in_progress_tasks = [t for t in job.tasks if t.status == TaskStatus.IN_PROGRESS]
    done_tasks        = [t for t in job.tasks if t.status == TaskStatus.DONE]

    lines: list[str] = [
        f"---\n{fm_str}---\n",
        f"# {job.job_name}\n",
        f"> **목표:** {job.goal}\n",
    ]

    def _append_section(header: str, task_list: list[Task]) -> None:
        lines.append(f"\n{header}\n")
        for task in task_list:
            lines.append(task.to_markdown())
            lines.append("")  # 태스크 사이 빈 줄

    _append_section(SECTION_TODO,        todo_tasks)
    _append_section(SECTION_IN_PROGRESS, in_progress_tasks)
    _append_section(SECTION_DONE,        done_tasks)

    return "\n".join(lines)
