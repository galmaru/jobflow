"""JobFlow CLI 명령어 모듈.

jobflow init       — ~/.jobflow 디렉토리, git 저장소, .key 초기화
jobflow remote add — GitHub remote 연결
jobflow sync       — GitHub API로 암호화 업로드
jobflow link       — 프로젝트 CLAUDE.md 연결
jobflow config set — config.yaml 값 설정
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
import yaml

from .sync import repo_slug_from_url

JOBFLOW_HOME = Path.home() / ".jobflow"
CONFIG_PATH  = JOBFLOW_HOME / "config.yaml"
KEY_PATH     = JOBFLOW_HOME / ".key"
GITIGNORE    = JOBFLOW_HOME / ".gitignore"


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _run_git(*args: str, cwd: Path = JOBFLOW_HOME) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"git 오류: {result.stderr.strip()}", err=True)
        sys.exit(1)


def _write_initial_config() -> None:
    config = {
        "version": "1.0",
        "github": {
            "repo":   "",
            "branch": "main",
            "path":   "tasks/",
        },
        "slack": {
            "notify_events": [
                "task_done",
                "stage_changed",
                "task_added",
                "daily_summary",
            ],
        },
        "vercel": {
            "dashboard_url": "",
        },
        "linked_projects": [],
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _write_gitignore() -> None:
    GITIGNORE.write_text(
        "# JobFlow 자동 생성\n.key\nlogs/\n*.pyc\n__pycache__/\n",
        encoding="utf-8",
    )


def _install_pre_push_hook() -> None:
    """~/.jobflow/.git/hooks/pre-push 훅 설치.

    평문 태스크 repo가 원격으로 push되지 않도록 항상 차단한다.
    """
    hooks_dir = JOBFLOW_HOME / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"

    hook_content = (
        "#!/usr/bin/env bash\n"
        "# JobFlow pre-push: 평문 태스크 repo push 차단\n"
        "set -e\n\n"
        "echo '[jobflow] 평문 태스크 repo는 push할 수 없습니다. jobflow sync 또는 MCP job_sync를 사용하세요.' >&2\n"
        "exit 1\n"
    )

    hook_path.write_text(hook_content, encoding="utf-8")
    hook_path.chmod(0o755)
    click.echo("🪝 pre-push 훅 설치 완료")


# ── CLI 그룹 ──────────────────────────────────────────────────────────────────

@click.group()
def main() -> None:
    """JobFlow — Claude MCP 기반 개인 태스크 관리 도구."""


@main.command()
def init() -> None:
    """~/.jobflow 디렉토리를 초기화합니다."""
    if JOBFLOW_HOME.exists() and (JOBFLOW_HOME / ".git").exists():
        click.echo("이미 초기화된 디렉토리입니다: ~/.jobflow")
        sys.exit(0)

    # 디렉토리 생성
    (JOBFLOW_HOME / "jobs").mkdir(parents=True, exist_ok=True)
    (JOBFLOW_HOME / "logs").mkdir(parents=True, exist_ok=True)

    # AES-256 키 생성
    if not KEY_PATH.exists():
        KEY_PATH.write_bytes(os.urandom(32))
        KEY_PATH.chmod(0o600)
        click.echo("🔑 .key 생성 완료 (절대 삭제하지 마세요 — 복구 불가)")
    else:
        click.echo("🔑 .key 이미 존재, 재사용합니다.")

    _write_gitignore()
    _write_initial_config()

    # git 초기화
    _run_git("init", cwd=JOBFLOW_HOME)
    _run_git("add", ".")
    _run_git("commit", "-m", "chore(jobflow): initial setup")

    # pre-push 훅 설치
    _install_pre_push_hook()

    click.echo("✅ ~/.jobflow 초기화 완료")
    click.echo("")
    click.echo("다음 단계:")
    click.echo("  1. GitHub에 비공개 저장소를 생성하세요.")
    click.echo("  2. jobflow remote add --url git@github.com:owner/repo.git")
    click.echo("  3. GITHUB_TOKEN 또는 GH_TOKEN 환경변수를 설정하세요.")
    click.echo("  4. jobflow link --project /path/to/your/project")
    click.echo("")
    click.echo("⚠️  .key 파일은 백업해 두세요. 분실 시 암호화 파일 복구 불가.")


@main.group()
def remote() -> None:
    """원격 저장소 관리."""


@remote.command("add")
@click.option("--url", required=True, help="GitHub SSH URL (git@github.com:owner/repo.git)")
def remote_add(url: str) -> None:
    """GitHub API 동기화 대상을 설정합니다.

    주의: ~/.jobflow 평문 repo는 원격으로 push하지 않습니다.
    """
    if not CONFIG_PATH.exists():
        click.echo("오류: ~/.jobflow가 초기화되지 않았습니다. `jobflow init` 먼저 실행하세요.", err=True)
        sys.exit(1)

    repo_slug = repo_slug_from_url(url)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    cfg.setdefault("github", {})
    cfg["github"]["repo"] = repo_slug
    cfg["github"].setdefault("branch", "main")
    cfg["github"].setdefault("path", "tasks/")

    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    _install_pre_push_hook()
    click.echo(f"✅ GitHub 동기화 대상 설정 완료: {repo_slug}")
    click.echo("ℹ️  ~/.jobflow 평문 repo는 원격 push되지 않습니다. 암호화 업로드는 `jobflow sync` 또는 MCP `job_sync`를 사용하세요.")


@main.command()
@click.option("--project", required=True, type=click.Path(exists=True), help="코드 프로젝트 경로")
def link(project: str) -> None:
    """프로젝트를 JobFlow에 연결하고 CLAUDE.md에 블록을 삽입합니다."""
    project_path = Path(project).resolve()

    # config.yaml에 프로젝트 등록
    if not CONFIG_PATH.exists():
        click.echo("오류: ~/.jobflow가 초기화되지 않았습니다. `jobflow init` 먼저 실행하세요.", err=True)
        sys.exit(1)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    linked = config.setdefault("linked_projects", [])
    str_path = str(project_path)

    if str_path not in linked:
        linked.append(str_path)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        click.echo(f"✅ 프로젝트 등록: {str_path}")
    else:
        click.echo(f"이미 등록된 프로젝트: {str_path}")

    # CLAUDE.md 블록 삽입
    from .claude_md import JOBFLOW_END, JOBFLOW_START, inject_jobflow_block

    claude_md = project_path / "CLAUDE.md"
    placeholder_block = (
        f"{JOBFLOW_START}\n"
        "## 현재 진행 중인 태스크\n\n"
        "(JobFlow 서버 시작 시 자동으로 갱신됩니다)\n\n"
        f"{JOBFLOW_END}"
    )
    inject_jobflow_block(claude_md, placeholder_block)
    click.echo(f"✅ CLAUDE.md JobFlow 블록 삽입 완료: {claude_md}")


@main.command("sync")
def sync_command() -> None:
    """GitHub API로 암호화 동기화를 수행합니다."""
    from .sync import job_sync

    click.echo(job_sync())


@main.group()
def config() -> None:
    """config.yaml 설정 관리."""


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """config.yaml의 키를 설정합니다.

    예: jobflow config set vercel.dashboard_url https://...
    """
    if not CONFIG_PATH.exists():
        click.echo("오류: ~/.jobflow가 초기화되지 않았습니다.", err=True)
        sys.exit(1)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 점 표기법으로 중첩 키 설정 (예: github.repo)
    keys = key.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value

    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    click.echo(f"✅ {key} = {value}")


@config.command("show")
def config_show() -> None:
    """현재 config.yaml 내용을 출력합니다."""
    if not CONFIG_PATH.exists():
        click.echo("config.yaml이 없습니다. `jobflow init`을 먼저 실행하세요.")
        return
    click.echo(CONFIG_PATH.read_text(encoding="utf-8"))
