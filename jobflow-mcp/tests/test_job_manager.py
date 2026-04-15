"""job_manager.py 단위 테스트."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _make_jobs_dir(tmp_path: Path) -> Path:
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    return jobs_dir


@pytest.fixture()
def fake_jobflow(tmp_path, monkeypatch):
    """~/.jobflow를 tmp_path로 대체하는 픽스처."""
    jobs_dir = _make_jobs_dir(tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBS_DIR", jobs_dir)
    monkeypatch.setattr("jobflow_mcp.git_ops.JOBFLOW_HOME", tmp_path)
    # git 조작 무시
    monkeypatch.setattr("jobflow_mcp.job_manager.git_ops.git_commit", lambda *a, **kw: None)
    return tmp_path


def test_job_new_creates_file(fake_jobflow):
    from jobflow_mcp.job_manager import job_new, JOBS_DIR

    result = job_new(name="test-job", goal="테스트용 업무")
    assert result["tasks_added"] == 0
    assert "job_id" in result
    assert result["job_id"].startswith("job-")

    md_file = JOBS_DIR / "todo-test-job.md"
    assert md_file.exists()


def test_job_new_with_tasks(fake_jobflow):
    from jobflow_mcp.job_manager import job_new, JOBS_DIR
    from jobflow_mcp.file_parser import parse_job_file

    result = job_new(
        name="with-tasks",
        goal="태스크 포함 생성 테스트",
        tasks=["프론트엔드 설계", "백엔드 API 구현"],
    )
    assert result["tasks_added"] == 2

    content = (JOBS_DIR / "todo-with-tasks.md").read_text(encoding="utf-8")
    job     = parse_job_file(content)
    assert len(job.tasks) == 2
    assert job.tasks[0].id    == "TASK-001"
    assert job.tasks[0].title == "프론트엔드 설계"


def test_job_new_duplicate_raises(fake_jobflow):
    from jobflow_mcp.job_manager import job_new

    job_new(name="duplicate", goal="첫 번째")
    with pytest.raises(FileExistsError):
        job_new(name="duplicate", goal="두 번째")


def test_job_new_invalid_name(fake_jobflow):
    from jobflow_mcp.job_manager import job_new

    with pytest.raises(ValueError, match="영문"):
        job_new(name="한글이름", goal="이름 검증 테스트")

    with pytest.raises(ValueError):
        job_new(name="has space", goal="공백 포함")


def test_job_id_sequence(fake_jobflow):
    from jobflow_mcp.job_manager import job_new

    r1 = job_new(name="first-job",  goal="첫 번째")
    r2 = job_new(name="second-job", goal="두 번째")

    # 순번이 연속적이어야 함
    assert r1["job_id"] != r2["job_id"]
    num1 = int(r1["job_id"].split("-")[-1])
    num2 = int(r2["job_id"].split("-")[-1])
    assert num2 == num1 + 1


def test_job_list(fake_jobflow):
    from jobflow_mcp.job_manager import job_new, job_list

    job_new(name="list-job-a", goal="A")
    job_new(name="list-job-b", goal="B")

    jobs = job_list()
    assert len(jobs) == 2
    names = {j["job_name"] for j in jobs}
    assert names == {"list-job-a", "list-job-b"}


def test_job_status_output(fake_jobflow):
    from jobflow_mcp.job_manager import job_new, job_status

    job_new(name="status-job", goal="상태 테스트", tasks=["태스크1", "태스크2"])
    output = job_status(target="status-job")

    assert "status-job" in output
    assert "Todo" in output
