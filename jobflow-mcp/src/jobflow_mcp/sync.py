"""암호화 및 GitHub 동기화 모듈.

AES-256-GCM으로 .md 파일을 암호화하여 GitHub에 업로드하고,
.jobflow-index.json을 통해 파일 목록을 관리한다.

이 모듈은 두 진입점을 제공한다:
  1. Python API (job_sync, job_pull) — MCP 서버에서 호출
  2. CLI (python -m jobflow_mcp.sync push) — pre-push 훅에서 호출
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from github import Github, GithubException, UnknownObjectException

logger = logging.getLogger(__name__)

JOBFLOW_HOME  = Path.home() / ".jobflow"
KEY_PATH      = JOBFLOW_HOME / ".key"
CONFIG_PATH   = JOBFLOW_HOME / "config.yaml"
JOBS_DIR      = JOBFLOW_HOME / "jobs"
LAST_SYNC_LOG = JOBFLOW_HOME / "logs" / "last_sync.json"

KST   = ZoneInfo("Asia/Seoul")
MAGIC = b"JFLOW1"

# 40개의 '0' — git에서 신규 push 시 remote sha
_ZEROS = "0" * 40


# ── 암호화 / 복호화 ────────────────────────────────────────────────────────────

def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-GCM 암호화.

    반환 형식: MAGIC(6) + nonce(12) + ciphertext + tag(16)
    """
    nonce      = os.urandom(12)
    aesgcm     = AESGCM(key)
    ct_and_tag = aesgcm.encrypt(nonce, plaintext, None)
    return MAGIC + nonce + ct_and_tag


def decrypt(data: bytes, key: bytes) -> bytes:
    """AES-256-GCM 복호화.

    magic 헤더 검증 실패 시 ValueError,
    GCM 태그 불일치 시 cryptography.exceptions.InvalidTag 발생.
    """
    if data[:6] != MAGIC:
        raise ValueError("유효하지 않은 JobFlow 암호화 파일입니다 (magic 헤더 불일치)")
    nonce      = data[6:18]
    ct_and_tag = data[18:]
    return AESGCM(key).decrypt(nonce, ct_and_tag, None)


def load_key() -> bytes:
    """~/.jobflow/.key 파일에서 AES-256 키 로드."""
    if not KEY_PATH.exists():
        raise FileNotFoundError(f".key 파일이 없습니다: {KEY_PATH}\n`jobflow init`을 먼저 실행하세요.")
    key = KEY_PATH.read_bytes()
    if len(key) != 32:
        raise ValueError(f".key 파일 크기가 잘못되었습니다 (예상 32 bytes, 실제 {len(key)} bytes)")
    return key


def key_to_b64(key: bytes) -> str:
    """키를 base64 문자열로 변환 (Vercel Secret 등록용)."""
    return base64.b64encode(key).decode()


def key_from_b64(b64_str: str) -> bytes:
    """base64 문자열을 키로 복원."""
    return base64.b64decode(b64_str)


# ── 설정 로드 ─────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.yaml이 없습니다. `jobflow init`을 먼저 실행하세요.")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _github_client() -> tuple[Github, str, str]:
    """(Github 인스턴스, repo 이름, tasks 경로) 반환.

    환경변수와 config.yaml을 조합해 GitHub API 대상 정보를 결정한다.
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GH_TOKEN 또는 GITHUB_TOKEN 환경변수가 설정되지 않았습니다.")

    cfg       = _load_config()
    gh_config = cfg.get("github", {})
    repo_name = (
        os.environ.get("GH_REPO")
        or os.environ.get("GITHUB_REPO")
        or gh_config.get("repo", "")
    )
    tasks_path = (
        os.environ.get("GH_TASKS_PATH")
        or os.environ.get("GITHUB_PATH")
        or gh_config.get("path", "tasks/")
    )

    if not repo_name:
        raise ValueError("GitHub repo가 설정되지 않았습니다. `jobflow config set github.repo owner/repo`")

    return Github(token), repo_name, tasks_path.rstrip("/")


# ── 인덱스 관리 ───────────────────────────────────────────────────────────────

def _build_index(jobs_meta: list[dict]) -> dict:
    return {
        "version":    "1.0",
        "updated_at": datetime.now(tz=KST).isoformat(),
        "jobs":       jobs_meta,
    }


def _upload_index(gh_repo, tasks_path: str, index: dict) -> None:
    """GitHub에 .jobflow-index.json 업로드 (생성 또는 갱신)."""
    content     = json.dumps(index, ensure_ascii=False, indent=2).encode()
    index_path  = f"{tasks_path}/.jobflow-index.json"
    commit_msg  = f"sync(jobflow): update index at {datetime.now(tz=KST).isoformat()}"

    try:
        existing = gh_repo.get_contents(index_path)
        gh_repo.update_file(index_path, commit_msg, content, existing.sha)
    except UnknownObjectException:
        gh_repo.create_file(index_path, commit_msg, content)


def _fetch_index(gh_repo, tasks_path: str) -> dict:
    """GitHub에서 .jobflow-index.json 조회."""
    index_path = f"{tasks_path}/.jobflow-index.json"
    try:
        file_content = gh_repo.get_contents(index_path)
        return json.loads(file_content.decoded_content)
    except UnknownObjectException:
        return {"version": "1.0", "jobs": []}


# ── 단일 파일 업로드 ──────────────────────────────────────────────────────────

def _upload_enc_file(
    gh_repo,
    tasks_path: str,
    enc_filename: str,
    enc_data: bytes,
    job_version: int,
) -> None:
    """암호화된 .enc 파일을 GitHub에 업로드."""
    file_path  = f"{tasks_path}/{enc_filename}"
    commit_msg = f"sync(jobflow): update {enc_filename} v{job_version}"

    try:
        existing = gh_repo.get_contents(file_path)
        gh_repo.update_file(file_path, commit_msg, enc_data, existing.sha)
        logger.info("파일 갱신: %s", enc_filename)
    except UnknownObjectException:
        gh_repo.create_file(file_path, commit_msg, enc_data)
        logger.info("파일 생성: %s", enc_filename)


# ── 변경 파일 목록 수집 ───────────────────────────────────────────────────────

def _changed_md_files(from_sha: str, to_sha: str) -> list[Path]:
    """두 커밋 사이에서 변경된 jobs/*.md 파일 목록 반환.

    from_sha가 zeros이면 전체 jobs/*.md 반환.
    """
    if from_sha.strip("0") == "":
        return sorted(JOBS_DIR.glob("*.md"))

    result = subprocess.run(
        ["git", "diff", f"{from_sha}..{to_sha}", "--name-only", "--", "jobs/"],
        cwd=JOBFLOW_HOME,
        capture_output=True,
        text=True,
    )
    paths = []
    for name in result.stdout.splitlines():
        p = JOBFLOW_HOME / name
        if p.exists() and p.suffix == ".md":
            paths.append(p)
    return paths


# ── push 흐름 (pre-push 훅에서 호출) ─────────────────────────────────────────

def push_to_github(from_sha: str, to_sha: str) -> dict:
    """변경된 .md 파일을 암호화하여 GitHub에 업로드.

    Returns:
        { "uploaded": [str, ...], "errors": [str, ...] }
    """
    key = load_key()
    gh, repo_name, tasks_path = _github_client()
    gh_repo = gh.get_repo(repo_name)

    changed = _changed_md_files(from_sha, to_sha)
    if not changed:
        logger.info("변경된 .md 파일 없음, 업로드 생략")
        result = {"uploaded": [], "errors": []}
        _write_sync_log(result)
        return result

    uploaded: list[str] = []
    errors:   list[str] = []
    jobs_meta: list[dict] = []

    # 기존 인덱스 로드 (있으면)
    try:
        existing_index = _fetch_index(gh_repo, tasks_path)
        jobs_meta = existing_index.get("jobs", [])
    except Exception:
        jobs_meta = []

    from .file_parser import parse_job_file

    for md_path in changed:
        try:
            content    = md_path.read_text(encoding="utf-8")
            job        = parse_job_file(content)
            enc_data   = encrypt(content.encode("utf-8"), key)
            enc_name   = md_path.name + ".enc"

            _upload_enc_file(gh_repo, tasks_path, enc_name, enc_data, job.version)
            uploaded.append(enc_name)

            # 인덱스 갱신 (기존 항목 교체 또는 추가)
            entry = {
                "file":       enc_name,
                "job_id":     job.job_id,
                "version":    job.version,
                "status":     job.status,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            }
            jobs_meta = [e for e in jobs_meta if e.get("file") != enc_name]
            jobs_meta.append(entry)

        except Exception as e:
            logger.error("업로드 실패 (%s): %s", md_path.name, e)
            errors.append(f"{md_path.name}: {e}")

    # 인덱스 업로드
    try:
        _upload_index(gh_repo, tasks_path, _build_index(jobs_meta))
    except Exception as e:
        errors.append(f"인덱스 업로드 실패: {e}")

    result = {"uploaded": uploaded, "errors": errors}
    _write_sync_log(result)
    logger.info("push 완료: %d개 업로드, %d개 오류", len(uploaded), len(errors))
    return result


def _write_sync_log(result: dict) -> None:
    LAST_SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    data = {**result, "synced_at": datetime.now(tz=KST).isoformat()}
    LAST_SYNC_LOG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_last_synced_local_head() -> str | None:
    """마지막 암호화 업로드 기준 로컬 commit SHA 반환."""
    if not LAST_SYNC_LOG.exists():
        return None
    try:
        data = json.loads(LAST_SYNC_LOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("local_head")
    return value if isinstance(value, str) and value else None


# ── MCP 도구: job_sync ────────────────────────────────────────────────────────

def job_sync() -> str:
    """미커밋 변경사항 커밋 → GitHub API로 .enc 업로드.

    Returns:
        동기화 결과 요약 문자열
    """
    from . import git_ops

    # 미커밋 변경사항 처리
    status = git_ops.git_status()
    if status.strip():
        git_ops.git_add_all_jobs()
        git_ops.git_commit(
            f"chore(jobflow): auto-sync at {datetime.now(tz=KST).isoformat()}",
            [],  # git_add_all_jobs()로 이미 스테이징됨
        )

    try:
        current_head = git_ops.git_rev_parse("HEAD")
        previous_head = _load_last_synced_local_head() or _ZEROS
        result = push_to_github(previous_head, current_head)
        result["local_head"] = current_head
        _write_sync_log(result)
    except Exception as e:
        return f"❌ 동기화 실패: {e}\nlogs/last_sync.json 확인"

    uploaded = result.get("uploaded", [])
    errors = result.get("errors", [])

    if errors:
        return f"⚠️  동기화 부분 실패: {len(uploaded)}개 업로드, {len(errors)}개 오류\n" + "\n".join(errors)

    names = ", ".join(uploaded) if uploaded else "없음"
    return f"✅ 동기화 완료: {len(uploaded)}개 업로드 ({names})"


# ── MCP 도구: job_pull ────────────────────────────────────────────────────────

def job_pull(resolutions: dict[str, str] | None = None) -> dict | str:
    """GitHub에서 최신 상태를 내려받아 로컬 파일과 병합.

    충돌 발생 시 dict 반환 ({"error": "conflict", "conflicts": {...}}).
    성공 시 문자열 반환.
    """
    from . import git_ops
    from .file_parser import parse_job_file
    from .merge import TaskConflict, merge_job
    from .job_manager import save_job

    key = load_key()
    gh, repo_name, tasks_path = _github_client()
    gh_repo = gh.get_repo(repo_name)

    index = _fetch_index(gh_repo, tasks_path)
    remote_jobs_meta = index.get("jobs", [])

    if not remote_jobs_meta:
        return "원격 저장소에 파일이 없습니다."

    updated_count  = 0
    resolved_count = 0
    all_conflicts: dict[str, dict] = {}

    for meta in remote_jobs_meta:
        enc_filename = meta["file"]
        file_path    = f"{tasks_path}/{enc_filename}"
        md_name      = enc_filename.removesuffix(".enc")
        local_path   = JOBS_DIR / md_name

        try:
            enc_file      = gh_repo.get_contents(file_path)
            enc_data      = enc_file.decoded_content
            remote_md     = decrypt(enc_data, key).decode("utf-8")
            remote_job    = parse_job_file(remote_md)
        except Exception as e:
            logger.error("원격 파일 처리 실패 (%s): %s", enc_filename, e)
            continue

        if not local_path.exists():
            # 로컬에 없으면 그냥 저장
            local_path.write_text(remote_md, encoding="utf-8")
            updated_count += 1
            continue

        local_job = parse_job_file(local_path.read_text(encoding="utf-8"))

        try:
            merged = merge_job(local_job, remote_job, resolutions)
            save_job(merged)
            updated_count += 1
            if resolutions:
                resolved_count += len([
                    tid for tid in resolutions
                    if any(t.id == tid for t in local_job.tasks)
                ])
        except TaskConflict as e:
            all_conflicts.update(e.conflicts)

    if all_conflicts:
        return {"error": "conflict", "conflicts": all_conflicts}

    # 로컬 변경사항 커밋
    if updated_count > 0:
        try:
            git_ops.git_add_all_jobs()
            git_ops.git_commit(
                f"chore(jobflow): pull merge at {datetime.now(tz=KST).isoformat()}",
                [],
            )
        except subprocess.CalledProcessError:
            pass  # 변경사항 없으면 커밋 실패 무시

    parts = [f"{updated_count}개 업데이트"]
    if resolved_count:
        parts.append(f"{resolved_count}개 충돌 해결")
    return f"✅ 풀 완료: {', '.join(parts)}"


# ── CLI 진입점 (pre-push 훅에서 호출) ────────────────────────────────────────

def _cli_push(from_sha: str, to_sha: str) -> None:
    """과거 pre-push 훅 호환용 진입점.

    평문 태스크 repo를 원격으로 push하는 경로는 더 이상 허용하지 않는다.
    """
    print(
        "[jobflow] 평문 태스크 repo push는 금지됩니다. `jobflow sync` 또는 MCP `job_sync`를 사용하세요.",
        flush=True,
    )


_REPO_URL_RE = re.compile(
    r"(?:git@github\.com:|https://github\.com/)(?P<repo>[^/]+/[^/.]+)(?:\.git)?$"
)


def repo_slug_from_url(url: str) -> str:
    """GitHub remote URL에서 owner/repo 추출."""
    match = _REPO_URL_RE.match(url.strip())
    if not match:
        raise ValueError(f"GitHub 저장소 URL 형식이 아닙니다: {url}")
    return match.group("repo")


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "push":
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--from-sha", required=True)
        parser.add_argument("--to-sha",   required=True)
        args = parser.parse_args(sys.argv[2:])
        _cli_push(args.from_sha, args.to_sha)
    else:
        print(f"사용법: python -m jobflow_mcp.sync push --from-sha SHA --to-sha SHA")
        sys.exit(1)
