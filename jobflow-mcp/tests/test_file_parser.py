"""file_parser.py 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jobflow_mcp.file_parser import (
    ChecklistItem,
    Job,
    Task,
    TaskStatus,
    parse_job_file,
    parse_task_metadata,
    serialize_job,
)

KST = ZoneInfo("Asia/Seoul")

SAMPLE_MD = """\
---
job_id: "job-20260414-001"
job_name: "kbo-app"
goal: "2026 KBO 시즌 실시간 스케줄 조회 앱 완성"
created_at: "2026-04-14T09:00:00+09:00"
updated_at: "2026-04-14T10:30:00+09:00"
version: 3
status: "in_progress"
---

# kbo-app

> **목표:** 2026 KBO 시즌 실시간 스케줄 조회 앱 완성


### 🔵 Todo

- [ ] TASK-003 API 연동 테스트 #backend !high
  - [ ] 엔드포인트 목록 정리
  <!-- started_at: ~ -->
  <!-- updated_at: 2026-04-14T09:30:00+09:00 -->
  <!-- completed_at: ~ -->

### 🟡 In Progress

- [~] TASK-002 UI 컴포넌트 설계 #frontend !medium
  <!-- started_at: 2026-04-14T09:00:00+09:00 -->
  <!-- updated_at: 2026-04-14T10:00:00+09:00 -->
  <!-- completed_at: ~ -->

### 🟢 Done

- [x] TASK-001 프로젝트 초기 세팅 #infra !low
  <!-- started_at: 2026-04-14T08:00:00+09:00 -->
  <!-- updated_at: 2026-04-14T08:30:00+09:00 -->
  <!-- completed_at: 2026-04-14T08:30:00+09:00 -->
"""


def test_parse_job_file_frontmatter():
    """frontmatter 파싱 정상 동작."""
    job = parse_job_file(SAMPLE_MD)
    assert job.job_id   == "job-20260414-001"
    assert job.job_name == "kbo-app"
    assert job.version  == 3
    assert job.status   == "in_progress"


def test_parse_job_file_task_count():
    """섹션별 태스크 수 검증."""
    job = parse_job_file(SAMPLE_MD)
    assert len(job.tasks) == 3


def test_parse_task_status():
    """각 태스크의 상태 정확성."""
    job    = parse_job_file(SAMPLE_MD)
    by_id  = {t.id: t for t in job.tasks}

    assert by_id["TASK-001"].status == TaskStatus.DONE
    assert by_id["TASK-002"].status == TaskStatus.IN_PROGRESS
    assert by_id["TASK-003"].status == TaskStatus.TODO


def test_parse_task_tag_and_priority():
    """태그 및 우선순위 파싱."""
    job   = parse_job_file(SAMPLE_MD)
    by_id = {t.id: t for t in job.tasks}

    assert by_id["TASK-003"].tag      == "#backend"
    assert by_id["TASK-003"].priority == "high"
    assert by_id["TASK-002"].tag      == "#frontend"
    assert by_id["TASK-002"].priority == "medium"


def test_parse_task_metadata_dates():
    """HTML 주석 메타데이터 날짜 파싱."""
    job   = parse_job_file(SAMPLE_MD)
    by_id = {t.id: t for t in job.tasks}

    assert by_id["TASK-001"].completed_at is not None
    assert by_id["TASK-002"].started_at   is not None
    assert by_id["TASK-003"].started_at   is None   # ~ → None


def test_parse_task_checklist():
    """체크리스트 항목 파싱."""
    job   = parse_job_file(SAMPLE_MD)
    by_id = {t.id: t for t in job.tasks}

    assert len(by_id["TASK-003"].checklist) == 1
    assert by_id["TASK-003"].checklist[0].text    == "엔드포인트 목록 정리"
    assert by_id["TASK-003"].checklist[0].checked is False


def test_parse_task_metadata_helper():
    """parse_task_metadata 함수 단위 테스트."""
    block = "<!-- started_at: 2026-04-14T09:00:00+09:00 -->\n<!-- completed_at: ~ -->"
    meta  = parse_task_metadata(block)
    assert meta["started_at"]   == "2026-04-14T09:00:00+09:00"
    assert meta["completed_at"] is None


def test_file_roundtrip():
    """md → Python → md 변환 시 태스크 손실 없음."""
    job       = parse_job_file(SAMPLE_MD)
    serialized = serialize_job(job)
    job2      = parse_job_file(serialized)

    assert job.job_id   == job2.job_id
    assert job.version  == job2.version
    assert len(job.tasks) == len(job2.tasks)

    by_id  = {t.id: t for t in job.tasks}
    by_id2 = {t.id: t for t in job2.tasks}

    for tid in by_id:
        assert by_id[tid].status   == by_id2[tid].status
        assert by_id[tid].title    == by_id2[tid].title
        assert by_id[tid].tag      == by_id2[tid].tag
        assert by_id[tid].priority == by_id2[tid].priority


def test_serialize_sections():
    """직렬화 후 섹션 헤더 존재 확인."""
    job        = parse_job_file(SAMPLE_MD)
    serialized = serialize_job(job)

    assert "### 🔵 Todo"        in serialized
    assert "### 🟡 In Progress" in serialized
    assert "### 🟢 Done"        in serialized


def test_html_comment_preserved():
    """직렬화 후 HTML 주석 메타데이터 보존."""
    job        = parse_job_file(SAMPLE_MD)
    serialized = serialize_job(job)

    assert "<!-- started_at:" in serialized
    assert "<!-- completed_at:" in serialized


def test_no_frontmatter_raises():
    """frontmatter 없는 파일 파싱 시 ValueError."""
    with pytest.raises(ValueError, match="frontmatter"):
        parse_job_file("# 제목\n본문만 있는 파일")
