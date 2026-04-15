"""JobFlow MCP 서버 진입점.

Claude Code에서 MCP 도구로 등록되어 Job/Task 관리를 수행한다.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from .claude_md import update_all_claude_mds
from .config import get as get_config
from .job_manager import job_list, job_new, job_status
from .sync import job_pull, job_sync
from .task_manager import task_add, task_check, task_move

# ── 로깅 설정 ──────────────────────────────────────────────────────────────────
JOBFLOW_HOME = Path.home() / ".jobflow"
LOG_FILE     = JOBFLOW_HOME / "logs" / "jobflow.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── auto-pull 상태 ─────────────────────────────────────────────────────────────
_last_pull_at: datetime | None = None
_PULL_INTERVAL = timedelta(minutes=10)

app = Server("jobflow")


async def _auto_pull() -> None:
    """GitHub에서 최신 상태 가져옴. 실패해도 로컬 상태로 계속 진행."""
    global _last_pull_at
    has_repo = bool(get_config("github.repo"))
    has_token = bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    if not (has_repo and has_token):
        return
    try:
        await asyncio.to_thread(job_pull)
        _last_pull_at = datetime.now()
        await asyncio.to_thread(update_all_claude_mds)
        logger.info("auto-pull 완료")
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        logger.warning("auto-pull 실패, 로컬 상태로 계속 진행: %s", e)


async def _ensure_fresh() -> None:
    """마지막 pull 이후 10분 이상 경과 시 pull 재시도."""
    if _last_pull_at is None or (datetime.now() - _last_pull_at) > _PULL_INTERVAL:
        await _auto_pull()


# ── MCP 도구 등록 ──────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="job_new",
            description="새 Job(업무)를 생성합니다. 선택적으로 태스크 목록을 함께 등록할 수 있습니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "업무명 (영문 소문자/숫자/하이픈만 허용, 예: kbo-app)",
                    },
                    "goal": {
                        "type": "string",
                        "description": "자연어 업무 목표",
                    },
                    "tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "태스크 제목 목록 (선택 사항, Claude가 미리 분할한 경우 사용)",
                    },
                },
                "required": ["name", "goal"],
            },
        ),
        types.Tool(
            name="job_list",
            description="모든 Job의 요약 목록을 반환합니다.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="job_status",
            description="Job의 3컬럼 칸반 현황을 텍스트로 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "job_id 또는 job_name (생략 시 In Progress 전체)",
                    }
                },
            },
        ),
        types.Tool(
            name="task_add",
            description="Job에 새 태스크를 추가합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job": {
                        "type": "string",
                        "description": "job_id 또는 job_name",
                    },
                    "title": {"type": "string", "description": "태스크 제목"},
                    "tag": {
                        "type": "string",
                        "description": "#frontend | #backend | #infra | #docs",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "우선순위 (기본: medium)",
                    },
                    "checklist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "체크리스트 항목 목록",
                    },
                },
                "required": ["job", "title"],
            },
        ),
        types.Tool(
            name="task_check",
            description="태스크를 다음 단계로 순차 이동합니다 (Todo→InProgress→Done).",
            inputSchema={
                "type": "object",
                "properties": {
                    "job": {
                        "type": "string",
                        "description": "job_id 또는 job_name (중복 task_id 방지를 위해 권장)",
                    },
                    "task_id": {"type": "string", "description": "예: TASK-002"}
                },
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="task_move",
            description="태스크를 임의 단계로 이동합니다 (되돌리기/건너뛰기).",
            inputSchema={
                "type": "object",
                "properties": {
                    "job": {
                        "type": "string",
                        "description": "job_id 또는 job_name (중복 task_id 방지를 위해 권장)",
                    },
                    "task_id": {"type": "string"},
                    "to": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done"],
                    },
                },
                "required": ["task_id", "to"],
            },
        ),
        types.Tool(
            name="job_sync",
            description="로컬 변경사항을 GitHub에 암호화 업로드합니다 (AES-256-GCM).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="job_pull",
            description=(
                "GitHub에서 최신 상태를 내려받아 로컬 파일과 병합합니다. "
                "충돌 발생 시 conflicts를 반환하고, resolutions로 재호출하면 해결합니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "resolutions": {
                        "type": "object",
                        "description": '충돌 해결 방침 예: {"TASK-002": "local", "TASK-005": "remote"}',
                        "additionalProperties": {
                            "type": "string",
                            "enum": ["local", "remote"],
                        },
                    }
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    await _ensure_fresh()

    try:
        if name == "job_new":
            result = job_new(
                name=arguments["name"],
                goal=arguments["goal"],
                tasks=arguments.get("tasks"),
            )
            text = (
                f"✅ Job 생성 완료\n"
                f"  job_id: {result['job_id']}\n"
                f"  태스크: {result['tasks_added']}개\n"
                f"  파일: {result['file_path']}"
            )

        elif name == "job_list":
            jobs = job_list()
            if not jobs:
                text = "등록된 Job이 없습니다."
            else:
                rows = ["| Job ID | 업무명 | 상태 | 완료/전체 | 마지막 업데이트 |", "|--------|--------|------|-----------|----------------|"]
                for j in jobs:
                    rows.append(
                        f"| {j['job_id']} | {j['job_name']} | {j['status']} "
                        f"| {j['done_tasks']}/{j['total_tasks']} | {j['updated_at'] or '-'} |"
                    )
                text = "\n".join(rows)

        elif name == "job_status":
            text = job_status(arguments.get("target"))

        elif name == "task_add":
            result = task_add(
                job=arguments["job"],
                title=arguments["title"],
                tag=arguments.get("tag"),
                priority=arguments.get("priority", "medium"),
                checklist=arguments.get("checklist"),
            )
            text = f"✅ {result['task_id']} 추가됨 (Job: {result['job_id']})"

        elif name == "task_check":
            result = task_check(arguments["task_id"], arguments.get("job"))
            text = (
                f"✅ {result['task_id']}: {result['from']} → {result['to']}"
            )

        elif name == "task_move":
            result = task_move(arguments["task_id"], arguments["to"], arguments.get("job"))
            text = (
                f"✅ {result['task_id']} 이동: {result['from']} → {result['to']}"
            )

        elif name == "job_sync":
            text = await asyncio.to_thread(job_sync)

        elif name == "job_pull":
            raw = await asyncio.to_thread(job_pull, arguments.get("resolutions"))
            if isinstance(raw, dict) and raw.get("error") == "conflict":
                import json
                text = (
                    "⚠️  충돌이 감지되었습니다. resolutions 인자로 재호출하세요.\n\n"
                    + json.dumps(raw, ensure_ascii=False, indent=2)
                )
            else:
                text = str(raw)

        else:
            text = f"알 수 없는 도구: {name}"

    except (ValueError, KeyError, FileNotFoundError, FileExistsError) as e:
        text = f"❌ 오류: {e}"
    except Exception as e:
        logger.exception("도구 실행 중 예상치 못한 오류: %s", name)
        text = f"❌ 내부 오류: {e}"

    return [types.TextContent(type="text", text=text)]


# ── 진입점 ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info("JobFlow MCP 서버 시작")

    await _auto_pull()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
