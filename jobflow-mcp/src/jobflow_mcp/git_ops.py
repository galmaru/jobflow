"""subprocess 기반 git 조작 모듈.

~/.jobflow/ 디렉토리 내에서만 git 명령을 실행한다.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

JOBFLOW_HOME = Path.home() / ".jobflow"


def _run(args: list[str], cwd: Path = JOBFLOW_HOME) -> subprocess.CompletedProcess:
    """git 명령 실행. 실패 시 CalledProcessError 발생."""
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("git 명령 실패: %s\nstderr: %s", " ".join(args), result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, args, result.stdout, result.stderr
        )
    return result


def git_init(path: Path = JOBFLOW_HOME) -> None:
    """git 저장소 초기화."""
    _run(["git", "init", str(path)], cwd=path.parent)
    logger.info("git init 완료: %s", path)


def git_commit(message: str, files: list[str]) -> None:
    """지정 파일 스테이징 후 커밋.

    Args:
        message: 커밋 메시지
        files:   JOBFLOW_HOME 기준 상대 경로 목록
    """
    for f in files:
        _run(["git", "add", f])
    _run(["git", "commit", "-m", message])
    logger.info("커밋 완료: %s", message)


def git_pull() -> None:
    """원격 저장소에서 rebase 방식으로 pull."""
    _run(["git", "pull", "--rebase"])
    logger.info("git pull --rebase 완료")


def git_push() -> None:
    """원격 저장소로 push."""
    _run(["git", "push"])
    logger.info("git push 완료")


def git_remote_add(url: str) -> None:
    """origin 리모트 추가 후 초기 push."""
    _run(["git", "remote", "add", "origin", url])
    _run(["git", "push", "-u", "origin", "main"])
    logger.info("리모트 연결 완료: %s", url)


def has_remote() -> bool:
    """origin 리모트가 설정되어 있는지 확인."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=JOBFLOW_HOME,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def git_add_all_jobs() -> None:
    """jobs/ 디렉토리 전체 스테이징."""
    _run(["git", "add", "jobs/"])


def git_status() -> str:
    """git status --short 출력 반환."""
    result = _run(["git", "status", "--short"])
    return result.stdout


def git_log(n: int = 10) -> str:
    """최근 n개 커밋 로그 반환."""
    result = _run(["git", "log", f"-{n}", "--oneline"])
    return result.stdout
