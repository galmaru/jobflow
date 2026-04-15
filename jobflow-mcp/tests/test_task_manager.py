"""task_manager.py 단위 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def fake_jobflow_with_job(tmp_path, monkeypatch):
    """테스트용 Job이 있는 가짜 ~/.jobflow."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBFLOW_HOME",  tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBS_DIR",      jobs_dir)
    monkeypatch.setattr("jobflow_mcp.task_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.git_ops.JOBFLOW_HOME",      tmp_path)

    # git / CLAUDE.md 조작 무시
    monkeypatch.setattr("jobflow_mcp.job_manager.git_ops.git_commit",  lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.git_ops.git_commit", lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.update_claude_md_for_job", lambda *a, **kw: None)

    from jobflow_mcp.job_manager import job_new
    job_new(name="task-test-job", goal="태스크 테스트", tasks=["초기 태스크"])

    return tmp_path


def test_task_add(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_add
    from jobflow_mcp.job_manager import load_job

    result = task_add(job="task-test-job", title="새 태스크", tag="#backend")
    assert result["task_id"] == "TASK-002"

    job = load_job("task-test-job")
    assert len(job.tasks) == 2
    assert job.tasks[-1].title == "새 태스크"
    assert job.tasks[-1].tag   == "#backend"


def test_task_add_auto_increment(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_add

    r1 = task_add(job="task-test-job", title="두 번째")
    r2 = task_add(job="task-test-job", title="세 번째")

    assert r1["task_id"] == "TASK-002"
    assert r2["task_id"] == "TASK-003"


def test_task_check_todo_to_in_progress(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_check
    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import load_job

    result = task_check("TASK-001")
    assert result["from"] == "todo"
    assert result["to"]   == "in_progress"

    job  = load_job("task-test-job")
    task = next(t for t in job.tasks if t.id == "TASK-001")
    assert task.status     == TaskStatus.IN_PROGRESS
    assert task.started_at is not None


def test_task_check_in_progress_to_done(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_check
    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import load_job

    task_check("TASK-001")  # todo → in_progress
    result = task_check("TASK-001")  # in_progress → done

    assert result["from"] == "in_progress"
    assert result["to"]   == "done"

    job  = load_job("task-test-job")
    task = next(t for t in job.tasks if t.id == "TASK-001")
    assert task.status       == TaskStatus.DONE
    assert task.completed_at is not None


def test_task_check_done_raises(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_check

    task_check("TASK-001")  # todo → in_progress
    task_check("TASK-001")  # in_progress → done

    with pytest.raises(ValueError, match="Done"):
        task_check("TASK-001")  # done → 에러


def test_task_move_to_done(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_move
    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import load_job

    result = task_move("TASK-001", "done")
    assert result["to"] == "done"

    job  = load_job("task-test-job")
    task = next(t for t in job.tasks if t.id == "TASK-001")
    assert task.status       == TaskStatus.DONE
    assert task.completed_at is not None


def test_task_move_back_to_todo(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_check, task_move
    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import load_job

    task_check("TASK-001")  # todo → in_progress
    result = task_move("TASK-001", "todo")
    assert result["to"] == "todo"

    job  = load_job("task-test-job")
    task = next(t for t in job.tasks if t.id == "TASK-001")
    assert task.status      == TaskStatus.TODO
    assert task.started_at  is None
    assert task.completed_at is None


def test_task_move_invalid_target(fake_jobflow_with_job):
    from jobflow_mcp.task_manager import task_move

    with pytest.raises(ValueError, match="유효하지 않은"):
        task_move("TASK-001", "review")


def test_task_check_updates_job_status(fake_jobflow_with_job):
    """모든 태스크가 Done이면 Job status도 done으로 변경."""
    from jobflow_mcp.task_manager import task_check
    from jobflow_mcp.job_manager import load_job

    task_check("TASK-001")  # → in_progress
    task_check("TASK-001")  # → done

    job = load_job("task-test-job")
    assert job.status == "done"


def test_task_check_with_job_disambiguates_duplicate_task_ids(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBS_DIR", jobs_dir)
    monkeypatch.setattr("jobflow_mcp.task_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.git_ops.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.git_ops.git_commit", lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.git_ops.git_commit", lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.update_claude_md_for_job", lambda *a, **kw: None)

    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import job_new, load_job
    from jobflow_mcp.task_manager import task_check

    job_new(name="alpha-job", goal="A", tasks=["공통 번호"])
    job_new(name="beta-job", goal="B", tasks=["공통 번호"])

    with pytest.raises(ValueError, match="중복된 task_id"):
        task_check("TASK-001")

    result = task_check("TASK-001", job="beta-job")
    assert result["to"] == "in_progress"

    alpha = load_job("alpha-job")
    beta = load_job("beta-job")

    assert next(t for t in alpha.tasks if t.id == "TASK-001").status == TaskStatus.TODO
    assert next(t for t in beta.tasks if t.id == "TASK-001").status == TaskStatus.IN_PROGRESS


def test_task_move_with_job_disambiguates_duplicate_task_ids(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.JOBS_DIR", jobs_dir)
    monkeypatch.setattr("jobflow_mcp.task_manager.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.git_ops.JOBFLOW_HOME", tmp_path)
    monkeypatch.setattr("jobflow_mcp.job_manager.git_ops.git_commit", lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.git_ops.git_commit", lambda *a, **kw: None)
    monkeypatch.setattr("jobflow_mcp.task_manager.update_claude_md_for_job", lambda *a, **kw: None)

    from jobflow_mcp.file_parser import TaskStatus
    from jobflow_mcp.job_manager import job_new, load_job
    from jobflow_mcp.task_manager import task_move

    job_new(name="move-alpha", goal="A", tasks=["공통 번호"])
    job_new(name="move-beta", goal="B", tasks=["공통 번호"])

    with pytest.raises(ValueError, match="중복된 task_id"):
        task_move("TASK-001", "done")

    result = task_move("TASK-001", "done", job="move-alpha")
    assert result["to"] == "done"

    alpha = load_job("move-alpha")
    beta = load_job("move-beta")

    assert next(t for t in alpha.tasks if t.id == "TASK-001").status == TaskStatus.DONE
    assert next(t for t in beta.tasks if t.id == "TASK-001").status == TaskStatus.TODO
