"""sync.py 단위 테스트 — 암호화/복호화, GitHub mock."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.exceptions import InvalidTag

from jobflow_mcp.sync import (
    MAGIC,
    decrypt,
    encrypt,
    job_sync,
    key_from_b64,
    key_to_b64,
    load_key,
    push_to_github,
    repo_slug_from_url,
)


# ── 암호화 / 복호화 ────────────────────────────────────────────────────────────

def _random_key() -> bytes:
    return os.urandom(32)


def test_encrypt_decrypt_roundtrip():
    """암호화 → 복호화 시 원본 복원."""
    key       = _random_key()
    plaintext = "안녕하세요, JobFlow! 테스트 데이터".encode("utf-8")
    enc       = encrypt(plaintext, key)
    dec       = decrypt(enc, key)
    assert dec == plaintext


def test_encrypt_produces_magic_header():
    """암호화 결과 앞 6바이트는 MAGIC이어야 한다."""
    key = _random_key()
    enc = encrypt(b"hello", key)
    assert enc[:6] == MAGIC


def test_encrypt_nonce_is_random():
    """동일 평문이라도 매번 다른 암호문 생성 (nonce 무작위성)."""
    key  = _random_key()
    enc1 = encrypt(b"same content", key)
    enc2 = encrypt(b"same content", key)
    assert enc1 != enc2


def test_decrypt_invalid_magic_raises():
    """magic 헤더가 없는 데이터 복호화 시 ValueError."""
    key      = _random_key()
    bad_data = b"BADHEADER" + os.urandom(50)
    with pytest.raises(ValueError, match="magic"):
        decrypt(bad_data, key)


def test_tamper_detection():
    """암호문 1바이트 변조 시 InvalidTag 발생."""
    key = _random_key()
    enc = bytearray(encrypt(b"tamper test", key))
    # 페이로드 중간 바이트 변조 (magic+nonce = 18 bytes 이후)
    enc[20] ^= 0xFF
    with pytest.raises(InvalidTag):
        decrypt(bytes(enc), key)


def test_wrong_key_raises():
    """다른 키로 복호화 시 InvalidTag."""
    key1 = _random_key()
    key2 = _random_key()
    enc  = encrypt(b"secret", key1)
    with pytest.raises(InvalidTag):
        decrypt(enc, key2)


def test_key_to_b64_roundtrip():
    """키 → base64 → 키 변환 일관성."""
    key = _random_key()
    assert key_from_b64(key_to_b64(key)) == key


def test_load_key_missing_raises(tmp_path, monkeypatch):
    """~/.key가 없으면 FileNotFoundError."""
    monkeypatch.setattr("jobflow_mcp.sync.KEY_PATH", tmp_path / ".key")
    with pytest.raises(FileNotFoundError):
        load_key()


def test_load_key_wrong_size_raises(tmp_path, monkeypatch):
    """키 크기가 32바이트 아니면 ValueError."""
    key_path = tmp_path / ".key"
    key_path.write_bytes(os.urandom(16))   # 16 bytes (잘못된 크기)
    monkeypatch.setattr("jobflow_mcp.sync.KEY_PATH", key_path)
    with pytest.raises(ValueError, match="크기"):
        load_key()


# ── GitHub 업로드 (PyGithub mock) ─────────────────────────────────────────────

def _make_fake_jobflow(tmp_path: Path):
    """테스트용 ~/.jobflow 구조 생성."""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    key_path = tmp_path / ".key"
    key_path.write_bytes(os.urandom(32))
    return tmp_path, jobs_dir, key_path


def _make_sample_md(jobs_dir: Path, name: str = "kbo-app") -> Path:
    content = f"""\
---
job_id: "job-20260414-001"
job_name: "{name}"
goal: "테스트"
created_at: "2026-04-14T09:00:00+09:00"
updated_at: "2026-04-14T10:00:00+09:00"
version: 1
status: "in_progress"
---

# {name}

> **목표:** 테스트

### 🔵 Todo

### 🟡 In Progress

### 🟢 Done
"""
    path = jobs_dir / f"todo-{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture()
def fake_jobflow_sync(tmp_path, monkeypatch):
    home, jobs_dir, key_path = _make_fake_jobflow(tmp_path)
    monkeypatch.setattr("jobflow_mcp.sync.JOBFLOW_HOME",  home)
    monkeypatch.setattr("jobflow_mcp.sync.JOBS_DIR",      jobs_dir)
    monkeypatch.setattr("jobflow_mcp.sync.KEY_PATH",      key_path)
    monkeypatch.setattr("jobflow_mcp.sync.LAST_SYNC_LOG", home / "logs" / "last_sync.json")
    (home / "logs").mkdir()
    return home, jobs_dir, key_path


def _mock_github(monkeypatch, fake_home):
    """Github, get_repo, get_contents mock 설정."""
    mock_repo = MagicMock()
    # get_contents: UnknownObjectException → 신규 파일로 처리
    from github import UnknownObjectException
    mock_repo.get_contents.side_effect = UnknownObjectException(404, {}, {})
    mock_repo.create_file.return_value = {"commit": MagicMock()}

    mock_gh = MagicMock()
    mock_gh.get_repo.return_value = mock_repo

    monkeypatch.setattr("jobflow_mcp.sync._github_client", lambda: (mock_gh, "owner/repo", "tasks"))
    return mock_repo


def test_github_upload_new_file(fake_jobflow_sync, monkeypatch):
    """신규 .enc 파일 생성 시 create_file 호출."""
    home, jobs_dir, _ = fake_jobflow_sync
    _make_sample_md(jobs_dir, "kbo-app")
    mock_repo = _mock_github(monkeypatch, home)

    result = push_to_github("0" * 40, "abc123")

    assert "todo-kbo-app.md.enc" in result["uploaded"]
    assert result["errors"] == []
    mock_repo.create_file.assert_called()


def test_github_upload_no_changes(fake_jobflow_sync, monkeypatch):
    """변경 파일 없으면 업로드 0개."""
    home, jobs_dir, _ = fake_jobflow_sync
    mock_repo = _mock_github(monkeypatch, home)

    # from_sha가 zeros가 아니고 jobs/에 변경 없음
    monkeypatch.setattr(
        "jobflow_mcp.sync._changed_md_files",
        lambda from_sha, to_sha: [],
    )

    result = push_to_github("abc111", "abc222")
    assert result["uploaded"] == []
    mock_repo.create_file.assert_not_called()


def test_sync_log_written(fake_jobflow_sync, monkeypatch):
    """push 후 last_sync.json 기록 확인."""
    home, jobs_dir, _ = fake_jobflow_sync
    _make_sample_md(jobs_dir)
    _mock_github(monkeypatch, home)

    push_to_github("0" * 40, "abc123")

    log_path = home / "logs" / "last_sync.json"
    assert log_path.exists()
    data = json.loads(log_path.read_text())
    assert "uploaded" in data
    assert "synced_at" in data


def test_repo_slug_from_url_supports_ssh_and_https():
    assert repo_slug_from_url("git@github.com:owner/repo.git") == "owner/repo"
    assert repo_slug_from_url("https://github.com/owner/repo.git") == "owner/repo"


def test_job_sync_uses_local_commit_range(fake_jobflow_sync, monkeypatch):
    home, jobs_dir, _ = fake_jobflow_sync
    _make_sample_md(jobs_dir)

    monkeypatch.setattr("jobflow_mcp.sync._load_last_synced_local_head", lambda: "prevsha")
    monkeypatch.setattr("jobflow_mcp.sync.push_to_github", lambda a, b: {"uploaded": ["todo-kbo-app.md.enc"], "errors": []})
    monkeypatch.setattr("jobflow_mcp.git_ops.git_status", lambda: "")
    monkeypatch.setattr("jobflow_mcp.git_ops.git_rev_parse", lambda target: "headsha")

    result = job_sync()

    assert "1개 업로드" in result

    log_path = home / "logs" / "last_sync.json"
    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert data["local_head"] == "headsha"
