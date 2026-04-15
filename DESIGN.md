# JobFlow — 상세 설계서

> PRD v1.0 기반 | 작성일: 2026-04-14 | 최종 개정: 2026-04-15 (DESIGN_REVIEW 반영)

---

## 개정 요약 (2026-04-15)

결정사항 11건 및 DESIGN_REVIEW.md의 즉시 수정/권장 항목 반영.

- 태스크 상태: **3단계** (`Todo → In Progress → Done`) — Review 제거
- `/job new` 시그니처: `tasks` 선택적 인자 (하이브리드)
- 태스크 메타데이터: **HTML 주석** `<!-- key: value -->` 포맷
- 멀티 디바이스: **작업 시작 시 자동 pull + Task 단위 충돌 감지**
- git 조작: **subprocess**로 통일 (pygit2 제거)
- PWA: **제외**, 반응형 웹만 제공
- `/job pull` 충돌 해결: **단일 도구 + `resolutions` 인자 재호출**
- 대시보드 인증: **Bearer Token** 필수
- Slack 채널: **개인 DM 전용** (정책 문서화)
- 모바일 탭: **영문 3탭** (`Todo | In Progress | Done`)
- `.jobflow-index.json` 날짜 노출: 의식적으로 허용

---

## 목차

- [공통: 데이터 모델 & 스키마](#data-model)
- [Phase 1 — MCP 서버 + 파일 구조](#phase-1)
- [Phase 2 — GitHub 암호화 동기화](#phase-2)
- [Phase 3 — Vercel 대시보드](#phase-3)
- [Phase 4 — Slack 단방향 알림](#phase-4)
- [크로스컷팅 정책](#cross-cutting)

---

## 공통: 데이터 모델 & 스키마 {#data-model}

### todo-{업무명}.md frontmatter 스키마

```yaml
---
job_id: "job-20260414-001"        # YYYY MM DD-{3자리 순번}
job_name: "KBO 스케줄 웹앱"
goal: "2026 KBO 시즌 실시간 스케줄 조회 앱 완성"
created_at: "2026-04-14T09:00:00+09:00"
updated_at: "2026-04-14T10:30:00+09:00"
version: 3                         # 태스크 변경마다 증가
status: "in_progress"              # todo | in_progress | done | archived
---
```

### 태스크 항목 스키마

태스크 시간 메타데이터는 **HTML 주석**으로 기록합니다 (렌더링 시 숨김, 파싱 규칙 명확).

```markdown
- [상태] TASK-{NNN} {제목} #{tag} !{priority}
  - 체크리스트 항목 1
  - 체크리스트 항목 2
  <!-- started_at: 2026-04-14T09:00:00+09:00 -->
  <!-- updated_at: 2026-04-14T10:30:00+09:00 -->
  <!-- completed_at: ~ -->
```

| 상태 기호 | 의미 |
|-----------|------|
| `[ ]` | Todo |
| `[~]` | In Progress |
| `[x]` | Done |

> **Review 단계 제거 사유**: PRD에서 1인 도구로 명시됨. Review는 "타인의 검토"가 필요한 경우에만 의미가 있어 MVP에서 제거. 필요 시 Phase 5+에서 재도입.

**태그 목록:** `#frontend` `#backend` `#infra` `#docs`
**우선순위:** `!high` `!medium` `!low`

### 메타데이터 파싱 규칙

```python
import re

META_RE = re.compile(r"<!--\s*(\w+)\s*:\s*(.+?)\s*-->")

def parse_task_metadata(task_block: str) -> dict:
    """태스크 블록 내 HTML 주석에서 메타데이터 추출.
    값이 '~' 또는 빈 문자열이면 None 반환."""
    meta = {}
    for key, val in META_RE.findall(task_block):
        meta[key] = None if val.strip() in ("~", "") else val.strip()
    return meta
```

### config.yaml 스키마

```yaml
version: "1.0"
github:
  repo: "owner/repo"
  branch: "main"
  path: "tasks/"
slack:
  # 주의: 개인 DM 채널 전용 Webhook 사용 권장
  # 팀 채널 사용 시 대시보드 URL이 채널 멤버 전원에게 노출됨
  # webhook_url은 Vercel Secret(SLACK_WEBHOOK_URL)으로만 관리 — 여기에 저장 금지
  notify_events:            # fire_notify()가 이 목록에 없는 이벤트는 전송 생략
    - task_done
    - stage_changed
    - task_added
    - daily_summary
vercel:
  dashboard_url: ""         # Phase 3 배포 후 `jobflow config set`으로 설정
  # daily_summary 발송 시각은 vercel.json cron 스케줄로 관리 (UTC 기준)
```

---

## Phase 1 — MCP 서버 + 파일 구조 {#phase-1}

> 기간: 1~2주 | 결과물: 동작하는 MCP 서버 + 로컬 파일 관리 완성

### 1.1 디렉토리 레이아웃

```
~/.jobflow/                 # 별도 git repo (jobflow init 시 `git init`)
├── .git/                   # git repo (GitHub remote 연결)
├── .gitignore              # .key, logs/ 제외
├── jobs/
│   ├── todo-kbo-app.md
│   └── todo-srt-app.md
├── .key                    # AES-256 키 (32 bytes) — .gitignore 필수
├── config.yaml
└── logs/
    └── jobflow.log         # MCP 서버 디버그 로그
```

**코드 저장소 루트 (각 프로젝트)** — 별개의 git repo
```
프로젝트 루트/
└── CLAUDE.md              # 세션 시작 시 현재 In Progress 태스크 자동 주입
```

> **두 repo의 관계**: `~/.jobflow/`는 **태스크 파일 전용 repo** (GitHub에 `.enc`로 동기화). 코드 프로젝트 repo와는 완전히 분리됨. `jobflow link --project <path>`는 두 repo를 연결하지 않고, 단지 해당 프로젝트의 `CLAUDE.md`에 JobFlow 블록을 주입할 뿐임.

### 1.2 CLAUDE.md 자동 주입 형식

MCP 서버가 세션 시작 시 CLAUDE.md의 `<!-- JOBFLOW:START -->` ~ `<!-- JOBFLOW:END -->` 블록을 갱신합니다.

```markdown
<!-- JOBFLOW:START -->
## 현재 진행 중인 태스크

**Job:** KBO 스케줄 웹앱 (`job-20260414-001`)
**In Progress:**
- [~] TASK-002 UI 컴포넌트 설계 #frontend

**Next Todo:**
- [ ] TASK-003 API 연동 테스트 #backend

_마지막 동기화: 2026-04-14 10:30 KST_
<!-- JOBFLOW:END -->
```

### 1.3 MCP 서버 구조

```
jobflow-mcp/
├── pyproject.toml
├── src/
│   └── jobflow_mcp/
│       ├── __init__.py
│       ├── server.py          # MCP 진입점, 도구 등록, 시작 시 auto-pull 훅
│       ├── job_manager.py     # Job CRUD, 파일 I/O
│       ├── task_manager.py    # Task CRUD, 단계 이동
│       ├── file_parser.py     # Markdown ↔ Python 객체 파싱
│       ├── git_ops.py         # subprocess 기반 git 조작 (구 git_hooks.py)
│       ├── sync.py            # .enc 암호화 및 GitHub 동기화
│       ├── merge.py           # Task 단위 충돌 감지 & 병합
│       ├── notify.py          # Vercel Notify API 호출
│       └── claude_md.py       # CLAUDE.md 블록 갱신
├── tests/
│   ├── test_job_manager.py
│   ├── test_task_manager.py
│   ├── test_file_parser.py
│   └── test_merge.py
└── README.md
```

### 1.4 MCP 도구 명세

> **MCP 도구 명명 규약**: Claude는 `job_new`, `task_add` 같은 스네이크 케이스 함수명으로 호출함. 본 설계서 내 `/job new` 표기는 개념적 명칭이며, 실제 등록 이름은 `job_new` 등임.

#### `job_new` (하이브리드 방식)

```
입력:
  name: str                  # 업무명 (영문/숫자/-만 허용)
  goal: str                  # 자연어 업무 목표
  tasks: list[str] | None    # 선택적: Claude가 미리 분할한 태스크 제목 목록
                             # tag/priority/checklist는 모두 기본값 적용
                             # (tag=None, priority="medium", checklist=[])

흐름:
  [권장 패턴] Claude가 대화로 먼저 태스크 분할 → 사용자 확정
             → tasks 포함하여 단일 호출
  [대안 패턴] tasks=None으로 빈 Job 생성 → 이후 task_add 반복 호출

처리:
  1. job_id 생성 (job-YYYYMMDD-NNN, 당일 순번)
  2. ~/.jobflow/jobs/todo-{name}.md 생성 (frontmatter + 섹션 헤더)
  3. tasks가 있으면 Todo 섹션에 일괄 삽입
  4. git add + git commit "feat(jobflow): create job {job_id}"
  5. CLAUDE.md 파일 수정 (git commit은 하지 않음 — 코드 프로젝트 repo이므로
     사용자가 별도로 커밋하거나 Claude가 작업 후 함께 커밋)

출력:
  { "job_id": "...", "tasks_added": N, "file_path": "..." }
```

#### `job_list`

```
처리: ~/.jobflow/jobs/ 내 모든 .md 파싱 → status별 그룹핑

출력: | Job ID | 업무명 | 상태 | 태스크 수 (완료/전체) | 마지막 업데이트 |
```

#### `job_status`

```
입력: target: str | None  # job_id 또는 job_name (생략 시 In Progress 전체)

출력: 3컬럼 칸반 텍스트 렌더링
  [Todo: 3] [In Progress: 1] [Done: 5]
```

#### `task_add`

```
입력:
  job: str           # job_id 또는 job_name
  title: str
  tag: str | None
  priority: str      # high | medium | low (기본: medium)
  checklist: list[str] | None

처리:
  1. TASK-NNN 자동 부여
  2. Todo 섹션 맨 아래에 추가
  3. version 증가, updated_at 갱신
  4. git commit "feat(jobflow): add {task_id} to {job_id}"
```

#### `task_check`

```
입력: task_id: str

처리:
  1. 현재 상태 → 다음 상태로 **항상 순차 이동**
     Todo → In Progress (started_at 기록)
     In Progress → Done (completed_at 기록)
     Done 상태에서 호출 시 에러
  2. 파일 업데이트, version 증가
  3. git commit "chore(jobflow): TASK-{NNN} {from} → {to}"
  4. CLAUDE.md 갱신
  5. fire_notify() 호출 (비동기 fire-and-forget, 실패 허용)
```

#### `task_move`

```
입력:
  task_id: str
  to: "todo" | "in_progress" | "done"

처리:
  1. 지정 단계로 이동
     to="in_progress": started_at 기록 (기존 값 없을 때만)
     to="done": completed_at 기록
     to="todo": started_at, completed_at 초기화
  2. 파일 업데이트, version 증가
  3. git commit "chore(jobflow): TASK-{NNN} moved to {to}"
  4. CLAUDE.md 갱신
  5. fire_notify() 호출 (비동기 fire-and-forget, 실패 허용)
```

> **`task_check` vs `task_move` 역할 분리**: `task_check`는 "다음 단계로" 단순 진행, `task_move`는 되돌리기나 건너뛰기 같은 비표준 이동 전용.

#### `jobflow_link` (CLI 명령, MCP 도구 아님)

```bash
jobflow link --project /path/to/project
```

처리:
1. 현재 프로젝트 경로를 `~/.jobflow/config.yaml`의 `linked_projects`에 등록
2. 해당 프로젝트의 `CLAUDE.md`에 `<!-- JOBFLOW:START --> ... <!-- JOBFLOW:END -->` 블록 주입 (기존 파일 있으면 append, 블록이 이미 있으면 교체)
3. 이후 세션 시작 시 MCP 서버가 자동으로 블록 갱신

### 1.5 파일 파서 상세

#### Markdown → Python 파싱 규칙

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

@dataclass
class ChecklistItem:
    text: str
    checked: bool

@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    tag: str | None
    priority: str
    checklist: list["ChecklistItem"]
    started_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None

@dataclass
class Job:
    job_id: str
    job_name: str
    goal: str
    created_at: datetime
    updated_at: datetime
    version: int
    status: str
    tasks: list[Task]
```

#### 섹션 감지 규칙 (3단계)

```
### 🔵 Todo        → TaskStatus.TODO
### 🟡 In Progress → TaskStatus.IN_PROGRESS
### 🟢 Done        → TaskStatus.DONE
```

### 1.6 git 자동 커밋 전략

- **`subprocess`로 통일** (pygit2 의존성 제거, 사용자 git 설정 자동 적용)
- `~/.jobflow/` 내부에서 git 명령 실행 (`cwd` 지정)
- 커밋 범위: `~/.jobflow/jobs/` 내 변경 파일만 스테이징

```python
# git_ops.py 예시
import subprocess
from pathlib import Path

JOBFLOW_HOME = Path.home() / ".jobflow"

def git_commit(message: str, files: list[str]) -> None:
    for f in files:
        subprocess.run(["git", "add", f], cwd=JOBFLOW_HOME, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=JOBFLOW_HOME, check=True)

def git_pull() -> None:
    subprocess.run(["git", "pull", "--rebase"], cwd=JOBFLOW_HOME, check=True)

def git_push() -> None:
    subprocess.run(["git", "push"], cwd=JOBFLOW_HOME, check=True)
```

| 이벤트 | 커밋 메시지 |
|--------|------------|
| Job 생성 | `feat(jobflow): create job {job_id} — {job_name}` |
| Task 추가 | `feat(jobflow): add {task_id} to {job_id}` |
| 단계 순차 이동 (`task_check`) | `chore(jobflow): {task_id} {from} → {to}` |
| 단계 임의 이동 (`task_move`) | `chore(jobflow): {task_id} moved to {to}` |

### 1.7 설치 및 설정 흐름

```bash
# 1. 패키지 설치
pip install jobflow-mcp

# 2. 초기화 — 디렉토리 + git repo + 키 생성을 한 번에
jobflow init
#   내부 동작:
#   - mkdir -p ~/.jobflow/{jobs,logs}
#   - git init ~/.jobflow
#   - .key 생성 (os.urandom(32))
#   - .gitignore 작성 (.key, logs/)
#   - config.yaml 템플릿 생성
#   - 첫 커밋

# 3. GitHub remote 연결
jobflow remote add --url git@github.com:owner/jobflow-tasks.git
#   내부: git remote add origin <url>; git push -u origin main

# 4. Claude Code settings.json에 MCP 서버 등록
# ~/.claude/settings.json
{
  "mcpServers": {
    "jobflow": {
      "command": "python",
      "args": ["-m", "jobflow_mcp.server"],
      "env": {
        "JOBFLOW_HOME": "~/.jobflow",
        "NOTIFY_SECRET": "<Phase 3 배포 후 설정>"
      }
    }
  }
}

# 5. 프로젝트 CLAUDE.md 연결
jobflow link --project /path/to/project

# 6. Phase 3 배포 후
jobflow config set vercel.dashboard_url https://jobflow-xxx.vercel.app
```

### 1.8 서버 시작 시 auto-pull 훅

```python
# server.py 핵심 흐름
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_last_pull_at: datetime | None = None

def time_since_last_pull() -> timedelta:
    if _last_pull_at is None:
        return timedelta(hours=999)  # 한 번도 pull 안 한 경우
    return datetime.now() - _last_pull_at

async def on_server_start():
    """MCP 서버 시작 시 GitHub에서 최신 상태 가져옴."""
    global _last_pull_at
    try:
        git_ops.git_pull()
        _last_pull_at = datetime.now()
    except subprocess.CalledProcessError as e:
        logger.warning(f"auto-pull 실패, 로컬 상태로 계속 진행: {e}")

async def on_first_tool_call():
    """첫 MCP 도구 호출 전에도 pull 시도 (서버 장시간 실행 대비)."""
    if time_since_last_pull() > timedelta(minutes=10):
        await on_server_start()
```

### 1.9 테스트 계획 (Phase 1)

| 테스트 | 검증 항목 |
|--------|----------|
| `test_job_new` | job_id 순번 중복 없음, md 파일 생성 정상, tasks 포함/미포함 모두 |
| `test_task_add` | TASK-NNN 자동 증가, 섹션 위치 정확 |
| `test_task_check` | 3단계 순차 이동, Done에서 호출 시 에러 |
| `test_file_roundtrip` | md → Python → md 변환 시 데이터 손실 없음 (HTML 주석 메타데이터 포함) |
| `test_claude_md_inject` | START/END 블록 정확히 교체 |
| `test_git_init` | `jobflow init` 후 git repo 정상 초기화 |
| `test_git_commit` | 커밋 생성, 메시지 형식 검증 |

---

## Phase 2 — GitHub 암호화 동기화 {#phase-2}

> 기간: 1주 | 결과물: push 시 자동 암호화 업로드, 복호화 유틸리티

### 2.1 암호화 설계

#### AES-256-GCM 포맷

```
.enc 파일 바이너리 레이아웃:
┌─────────────────────────────────────────┐
│  magic: b"JFLOW1"  (6 bytes)            │
│  nonce: 12 bytes (random, per file)     │
│  ciphertext: variable                   │
│  tag: 16 bytes (GCM auth tag)           │
└─────────────────────────────────────────┘
```

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

MAGIC = b"JFLOW1"

def encrypt(plaintext: bytes, key: bytes) -> bytes:
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct_and_tag = aesgcm.encrypt(nonce, plaintext, None)
    return MAGIC + nonce + ct_and_tag

def decrypt(data: bytes, key: bytes) -> bytes:
    # assert는 `python -O` 실행 시 무시되어 보안 검증이 사라지므로 사용 금지
    if data[:6] != MAGIC:
        raise ValueError("Invalid JobFlow encrypted file")
    nonce = data[6:18]
    ct_and_tag = data[18:]
    return AESGCM(key).decrypt(nonce, ct_and_tag, None)
```

#### 키 생성 및 관리

```bash
# ~/.jobflow/.key 생성 (jobflow init 시 자동 실행)
python -c "import os; open('.key','wb').write(os.urandom(32))"

# Vercel Secret에 등록 (base64 인코딩)
vercel env add JOBFLOW_KEY_B64 production  # base64(key) 값 입력
```

### 2.2 Git Push 훅 구조

> **훅 대상 repo**: `~/.jobflow/.git/hooks/pre-push` (JobFlow 태스크 repo). 코드 프로젝트 repo와는 무관.

#### pre-push 훅 (`~/.jobflow/.git/hooks/pre-push`)

```bash
#!/usr/bin/env bash
# JobFlow: ~/.jobflow/jobs/*.md → .enc 암호화 후 GitHub 업로드
set -e

# pre-push 훅은 stdin에서 push 범위를 받음
# 형식: <local-ref> <local-sha1> <remote-ref> <remote-sha1>
while read local_ref local_sha remote_ref remote_sha; do
    python -m jobflow_mcp.sync push \
        --from-sha "${remote_sha}" \
        --to-sha   "${local_sha}"
done
```

#### `sync.py` push 흐름

```
입력:
  --from-sha: remote의 마지막 커밋 SHA (신규 push면 "0000...0000")
  --to-sha:   로컬의 최신 커밋 SHA

처리:
1. git diff {from_sha}..{to_sha} --name-only -- jobs/ 로 변경 파일 목록 수집
   (from_sha가 zeros이면 전체 jobs/*.md 처리)
2. 각 파일 AES-256-GCM 암호화 → {name}.md.enc (메모리에서만 처리)
3. PyGithub로 {config.github.repo}/{config.github.path}/{name}.md.enc PUT
   - 파일 존재 시: update (sha 포함)
   - 신규 파일: create
   - GitHub API commit_message: "sync(jobflow): update {name}.md.enc v{version}"
4. .jobflow-index.json 갱신 (GitHub API PUT)
5. 결과를 ~/.jobflow/logs/last_sync.json 에 기록 (job_sync 도구가 읽어 반환)
```

> **GitHub Actions 백업 방식은 제거**. 원안의 `paths: ['~/.jobflow/**']` 조건은 로컬 경로를 사용해 GitHub Actions에서 절대 트리거되지 않음. 별도 jobs 전용 repo + Actions 조합으로 재설계하려면 상당한 추가 작업이 필요하므로 MVP에서는 pre-push 훅으로 통일.

### 2.3 동기화 MCP 도구

#### `job_sync`

```
입력: (없음)

처리:
  1. git add/commit (미커밋 변경사항 보장)
  2. git push
     → pre-push 훅이 트리거되어 .md → .enc 암호화 후 GitHub API PUT
     → 훅이 결과를 ~/.jobflow/logs/last_sync.json 에 기록
  3. last_sync.json 읽어 결과 요약 반환
     예: "동기화 완료: 2개 업로드 (kbo-app.md.enc, srt-app.md.enc)"
     실패 시: "push 실패 또는 암호화 업로드 실패 — logs/last_sync.json 확인"

주의: 직접 GitHub API PUT을 수행하지 않음.
      암호화 업로드는 pre-push 훅이 단일 책임을 가짐.
```

#### `job_pull` (Task 단위 충돌 감지, 단일 도구 + resolutions)

```
입력:
  resolutions: dict[str, "local" | "remote"] | None
    # 예: { "TASK-002": "local", "TASK-005": "remote" }

처리:
  1. GitHub API로 .jobflow-index.json 조회 → 파일 목록 파악
  2. ~/.jobflow/.key 로드 → 각 .enc 파일 다운로드 → 복호화 → 로컬 파일과 task 단위 비교
  3. 각 task에 대해:
     - 한쪽만 수정 → 자동 반영
     - 양쪽 모두 수정 (updated_at 다름) → 충돌
  4. 충돌이 있고 resolutions가 없으면:
     → 에러 반환 (conflicts 상세 포함)
  5. 충돌이 있고 resolutions가 있으면:
     → 각 task_id별 지정된 쪽으로 병합
  6. 충돌이 없거나 모두 해결되면:
     → 로컬 파일 덮어쓰기, git commit

1차 출력 (충돌 발생 시):
{
  "error": "conflict",
  "conflicts": {
    "TASK-002": {
      "local": { "title": "...", "updated_at": "...", "status": "..." },
      "remote": { "title": "...", "updated_at": "...", "status": "..." }
    }
  }
}

2차 호출 (Claude가 사용자 상의 후):
  job_pull(resolutions={"TASK-002": "local"})

최종 출력: "풀 완료: 2개 업데이트, 1개 충돌 해결"
```

#### Task 단위 병합 의사코드

```python
# merge.py
from dataclasses import asdict, replace
from datetime import datetime
from zoneinfo import ZoneInfo

class TaskConflict(Exception):
    def __init__(self, conflicts: dict):
        self.conflicts = conflicts

def _task_summary(t: Task) -> dict:
    """Task → JSON 직렬화 가능한 요약 dict.
    Enum과 datetime을 문자열로 변환 (asdict()는 이들을 변환하지 않음)."""
    return {
        "title": t.title,
        "status": t.status.value,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }

def merge_job(local: Job, remote: Job, resolutions: dict | None = None) -> Job:
    resolutions = resolutions or {}
    all_ids = set(t.id for t in local.tasks) | set(t.id for t in remote.tasks)
    merged, conflicts = [], {}

    for tid in sorted(all_ids):
        l = next((t for t in local.tasks if t.id == tid), None)
        r = next((t for t in remote.tasks if t.id == tid), None)

        if l and not r:                        merged.append(l)
        elif r and not l:                      merged.append(r)
        elif l == r:                           merged.append(l)
        elif l.updated_at == r.updated_at:     merged.append(l)
        elif tid in resolutions:
            merged.append(l if resolutions[tid] == "local" else r)
        else:
            conflicts[tid] = {"local": _task_summary(l), "remote": _task_summary(r)}

    if conflicts:
        raise TaskConflict(conflicts)

    # local Job 메타데이터 기반으로 tasks와 updated_at만 교체
    return replace(
        local,
        tasks=merged,
        updated_at=datetime.now(tz=ZoneInfo("Asia/Seoul")),
    )
```

### 2.4 파일 경로 구조 (GitHub repo)

```
{github.repo}/
└── {github.path}/          # 예: "tasks/"
    ├── todo-kbo-app.md.enc
    ├── todo-srt-app.md.enc
    └── .jobflow-index.json  # 평문 (암호화된 파일 메타 인덱스)
```

#### `.jobflow-index.json` 형식

```json
{
  "version": "1.0",
  "updated_at": "2026-04-14T10:30:00+09:00",
  "jobs": [
    {
      "file": "todo-kbo-app.md.enc",
      "job_id": "job-20260414-001",
      "version": 3,
      "status": "in_progress",
      "updated_at": "2026-04-14T10:30:00+09:00"
    }
  ]
}
```

> **공개 범위 의식적 결정**: `.jobflow-index.json`은 평문이며 `job_id`에 날짜가 포함됨. public repo 사용 시 **작업 시작일/개수/빈도**가 노출됨. 민감도가 낮다고 판단하여 허용. 민감한 프로젝트는 사용자가 private repo를 선택해야 함 (이 판단은 `jobflow init` 시 README로 안내).

### 2.5 보안 체크리스트

| 항목 | 처리 방법 |
|------|----------|
| `.key` 파일 노출 방지 | `~/.jobflow/.gitignore`에 `.key` 추가, `jobflow init`이 자동 처리 |
| `config.yaml` 내 webhook_url | `$SLACK_WEBHOOK` 환경변수 참조 방식, 직접 값 저장 금지 |
| `assert` 사용 금지 | 보안 검증은 `raise ValueError` 사용 (`-O` 플래그 대비) |
| GitHub repo 공개 여부 | public도 허용 (암호화되지만 인덱스의 날짜/개수는 노출) |
| 키 분실 복구 | 복구 불가 — `jobflow init`시 키 백업 경고 출력 |
| GCM 태그 검증 실패 | `InvalidTag` 예외 → "파일 손상 또는 키 불일치" 메시지 |

### 2.6 테스트 계획 (Phase 2)

| 테스트 | 검증 항목 |
|--------|----------|
| `test_encrypt_decrypt` | 암호화 → 복호화 동일 내용 보장 |
| `test_magic_header` | 잘못된 파일 감지 (`raise ValueError`) |
| `test_tamper_detection` | ct 1바이트 변조 시 InvalidTag 발생 |
| `test_github_upload` | PyGithub mock으로 PUT 호출 검증 |
| `test_merge_no_conflict` | 서로 다른 task 수정 시 자동 병합 |
| `test_merge_conflict_raises` | 동일 task 양쪽 수정 시 TaskConflict 발생 |
| `test_merge_with_resolutions` | resolutions 지정 시 해당 쪽으로 병합 |
| `test_index_json` | 인덱스 파일 정확히 갱신 |

---

## Phase 3 — Vercel 대시보드 {#phase-3}

> 기간: 1~2주 | 결과물: 칸반 UI (3컬럼), 히스토리 뷰어, Bearer Token 인증, 반응형 웹

### 3.1 프로젝트 구조

```
jobflow-dashboard/
├── package.json
├── next.config.ts
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # 대시보드 메인 (칸반)
│   │   ├── login/
│   │   │   └── page.tsx            # Bearer Token 입력 화면
│   │   ├── jobs/
│   │   │   └── [jobId]/
│   │   │       ├── page.tsx        # Job 상세
│   │   │       └── history/
│   │   │           └── page.tsx    # diff 뷰어 (lazy)
│   │   └── api/
│   │       ├── jobs/route.ts           # GET: 전체 job 목록 (태스크 상세 포함)
│   │       ├── slack/
│   │       │   ├── notify/route.ts     # POST: MCP → Slack 알림
│   │       │   └── daily-summary/route.ts  # GET: Vercel Cron
│   │       └── history/[jobId]/route.ts
│   ├── components/
│   │   ├── KanbanBoard.tsx         # 3컬럼 칸반
│   │   ├── TaskCard.tsx
│   │   ├── TaskSlideOver.tsx
│   │   ├── HistoryViewer.tsx       # dynamic import
│   │   ├── MobileTabFilter.tsx     # 3탭
│   │   └── JobSelector.tsx
│   ├── lib/
│   │   ├── decrypt.ts              # Node.js crypto (서버 전용)
│   │   ├── auth.ts                 # Bearer Token 검증
│   │   ├── github.ts
│   │   └── types.ts
│   ├── middleware.ts               # /api/* 토큰 검증
│   └── hooks/
│       └── useJobs.ts              # SWR (revalidateOnFocus, refreshInterval)
├── .env.local
└── vercel.json
```

> **PWA 제거**: `public/manifest.json`, `sw.js`, `next-pwa` 의존성 전부 제외. 모바일 알림은 Phase 4 Slack이 담당. 반응형 웹으로만 구성.

### 3.2 인증 레이어 (Bearer Token)

#### `src/lib/auth.ts`

```typescript
import { timingSafeEqual } from "crypto";

export function verifyBearer(authHeader: string | null): boolean {
  const expected = process.env.DASHBOARD_TOKEN;
  if (!expected || !authHeader?.startsWith("Bearer ")) return false;

  const provided = authHeader.slice("Bearer ".length);
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
```

#### `src/middleware.ts`

```typescript
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifyBearer } from "@/lib/auth";

export function middleware(req: NextRequest) {
  // /api/slack/* 는 자체 인증 로직 (NOTIFY_SECRET, CRON_SECRET) 사용
  if (req.nextUrl.pathname.startsWith("/api/slack/")) {
    return NextResponse.next();
  }
  if (req.nextUrl.pathname.startsWith("/api/")) {
    if (!verifyBearer(req.headers.get("authorization"))) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }
  return NextResponse.next();
}

export const config = { matcher: "/api/:path*" };
```

#### 프론트엔드 플로우

1. 최초 접속 시 `/login` 리다이렉트 → 토큰 입력 폼
2. localStorage에 저장 (`jobflow_token`)
3. SWR fetcher에서 자동으로 `Authorization: Bearer <token>` 헤더 첨부
4. 401 응답 시 localStorage 삭제 + `/login` 재유도

### 3.3 API Route 명세

#### `GET /api/jobs`

```
처리:
  1. Bearer Token 검증 (middleware)
  2. Vercel Secret에서 JOBFLOW_KEY_B64 로드
  3. GitHub: .jobflow-index.json 조회
  4. 각 .enc 파일 병렬 다운로드 (Promise.all)
  5. 서버 메모리 복호화 (AES-256-GCM, Node.js crypto)
  6. Markdown 파싱 → Job 객체 배열

캐싱: Cache-Control: private, no-store

응답 형식:
{
  "jobs": [{
    "job_id": "...",
    "job_name": "...",
    "status": "in_progress",
    "version": 3,
    "updated_at": "...",
    "tasks": {
      "todo": [...],
      "in_progress": [...],
      "done": [...]
    }
  }]
}
```

#### `GET /api/history/[jobId]?sha=<sha>` — **lazy load 구조**

```
처리:
  - sha 미지정: 커밋 목록만 반환 (GitHub commits API)
  - sha 지정:   해당 커밋의 .enc 단일 조회 + 복호화 + 이전 커밋과 diff

이유: 전체 커밋 일괄 복호화는 10초 타임아웃 초과 위험. 사용자가 특정 커밋 클릭 시만 복호화.

응답 (커밋 목록):
{
  "commits": [
    { "sha": "abc123", "message": "...", "date": "...", "version": 3 }
  ]
}

응답 (단일 커밋):
{
  "sha": "abc123",
  "content": "...",          // 평문 Markdown
  "parent_content": "..."    // 이전 커밋 평문 (diff 계산용)
}
```

### 3.4 복호화 (TypeScript — 서버 사이드)

```typescript
// src/lib/decrypt.ts
// Node.js crypto 모듈 사용 (서버 사이드 전용)
import { createDecipheriv } from "crypto";

const MAGIC = Buffer.from("JFLOW1");

export function decrypt(encData: Buffer, keyB64: string): string {
  const key = Buffer.from(keyB64, "base64");

  if (!encData.subarray(0, 6).equals(MAGIC)) {
    throw new Error("Invalid JobFlow file format");
  }

  const nonce = encData.subarray(6, 18);
  const tag = encData.subarray(encData.length - 16);
  const ciphertext = encData.subarray(18, encData.length - 16);

  const decipher = createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAuthTag(tag);

  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf-8");
}
```

### 3.5 UI 컴포넌트 설계

#### KanbanBoard (PC, 3컬럼)

```
┌──────────────────────────────────────────────────────────────┐
│  JobFlow Dashboard    [Job 선택 ▼]              🔄 새로고침  │
├──────────────────┬──────────────────┬────────────────────────┤
│  🔵 Todo (3)    │ 🟡 In Progress(1)│   🟢 Done (5)          │
├──────────────────┼──────────────────┼────────────────────────┤
│ ┌──────────┐     │ ┌──────────┐     │ ┌─────────────┐        │
│ │TASK-003  │     │ │TASK-002  │     │ │TASK-001 ✓   │        │
│ │API 연동  │     │ │UI 설계   │     │ │프로젝트 세팅│        │
│ │#backend  │     │ │#frontend │     │ │#infra       │        │
│ │!high     │     │ │started 2h│     │ └─────────────┘        │
│ └──────────┘     │ └──────────┘     │                        │
└──────────────────┴──────────────────┴────────────────────────┘
```

#### 모바일 레이아웃 (3탭)

```
┌────────────────────┐
│  JobFlow      ≡   │
│  KBO 스케줄 앱 ▼   │
├────────────────────┤
│ Todo │ In Progress │ Done │   ← 3탭 (각 ~107px, 여유로움)
├────────────────────┤
│ TASK-002           │
│ UI 컴포넌트 설계   │
│ #frontend  🟡     │
└────────────────────┘
```

카드 탭 → 풀스크린 상세 화면 전환.

### 3.6 히스토리 뷰어 (lazy load)

```tsx
// src/app/jobs/[jobId]/history/page.tsx
import dynamic from "next/dynamic";

const HistoryViewer = dynamic(() => import("@/components/HistoryViewer"), {
  ssr: false,
  loading: () => <div>히스토리 로딩 중…</div>,
});
```

동작:
- 초기: 커밋 목록만 표시 (`/api/history/[jobId]`)
- 커밋 클릭 시: `/api/history/[jobId]?sha=<sha>` 호출 → diff 렌더링
- `diff2html`은 `HistoryViewer` 내부 import → 메인 번들에서 분리

### 3.7 SWR 설정

```ts
// src/hooks/useJobs.ts
import useSWR from "swr";

const fetcher = (url: string) =>
  fetch(url, {
    headers: { Authorization: `Bearer ${localStorage.getItem("jobflow_token")}` },
  }).then((r) => {
    if (r.status === 401) {
      localStorage.removeItem("jobflow_token");
      window.location.href = "/login";
    }
    return r.json();
  });

export function useJobs() {
  return useSWR("/api/jobs", fetcher, {
    revalidateOnFocus: true,
    refreshInterval: 30_000,   // API no-store 대응: SWR in-memory 캐시 갱신
  });
}
```

### 3.8 환경 변수

| 변수명 | 위치 | 설명 |
|--------|------|------|
| `JOBFLOW_KEY_B64` | Vercel Secret | AES-256 키 (base64) |
| `DASHBOARD_TOKEN` | Vercel Secret | 대시보드 Bearer Token (`openssl rand -hex 32`) |
| `GH_TOKEN` | Vercel Secret | GitHub PAT (repo:read) |
| `GH_REPO` | Vercel Env | `owner/repo` |
| `GH_TASKS_PATH` | Vercel Env | `tasks/` |

> `DASHBOARD_TOKEN`과 Phase 4의 `NOTIFY_SECRET`은 **반드시 별도 값**을 사용.

### 3.9 `vercel.json`

```json
{
  "functions": {
    "src/app/api/**": {
      "memory": 256,
      "maxDuration": 10
    }
  },
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "private, no-store" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ]
}
```

### 3.10 테스트 계획 (Phase 3)

| 테스트 | 검증 항목 |
|--------|----------|
| `decrypt.test.ts` | Python 암호화 파일 → TS 복호화 동일 내용 |
| `auth.test.ts` | 올바른 토큰 200, 잘못된 토큰 401, 누락 시 401 |
| `api/jobs.test.ts` | 인증 middleware 통과 후 응답 구조 |
| `api/history.test.ts` | sha 유/무에 따른 응답 분기 |
| `KanbanBoard.test.tsx` | 3컬럼 렌더링, 빈 컬럼 처리 |
| `TaskSlideOver.test.tsx` | 열기/닫기, 체크리스트 표시 |
| `HistoryViewer.dynamic.test.tsx` | 번들 스플릿 확인 |
| E2E (Playwright) | 로그인 → 목록 → 카드 클릭 → 상세 → 히스토리 |

---

## Phase 4 — Slack 단방향 알림 {#phase-4}

> 기간: 3~5일 | 결과물: 이벤트 기반 Slack 알림 완성

### 4.1 알림 아키텍처

```
MCP 서버 (Python)
  └─ 이벤트 발행 (HTTP POST, fire-and-forget)
        ↓
Vercel Functions /api/slack/notify
  └─ timingSafeEqual로 secret 검증 → 이벤트 유형별 메시지 포맷
        ↓
Slack Incoming Webhook → 개인 DM 채널
```

> **채널 정책**: Slack Incoming Webhook은 **개인 DM 채널 전용**으로 구성. 팀 채널 사용 시 대시보드 URL이 멤버 전원에게 노출됨. `config.yaml`과 README에 경고 명시.

### 4.2 이벤트 페이로드 스키마

```typescript
interface NotifyPayload {
  event: "task_done" | "stage_changed" | "task_added" | "daily_summary";
  job_id: string;
  job_name: string;
  task_id?: string;
  task_title?: string;
  from_stage?: string;   // "todo" | "in_progress" | "done"
  to_stage?: string;
  summary?: DailySummary;
  timestamp: string;     // ISO 8601
  secret: string;        // NOTIFY_SECRET
}

interface DailySummary {
  total: number;
  done_today: number;
  in_progress: number;
  todo: number;
  completed_tasks: string[];
}
```

### 4.3 Vercel Function 구현 (timingSafeEqual)

```typescript
// src/app/api/slack/notify/route.ts
import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";

function verifySecret(provided: string | undefined): boolean {
  const expected = process.env.NOTIFY_SECRET;
  if (!expected || !provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(req: NextRequest) {
  const payload: NotifyPayload = await req.json();

  // 1. 시크릿 검증 (타이밍 공격 방지)
  if (!verifySecret(payload.secret)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. 중복 발송 방지 (동일 task_id 3초 내 재발송 차단)
  if (payload.task_id && isDuplicate(payload.task_id)) {
    return NextResponse.json({ ok: true, skipped: "duplicate" });
  }

  // 3. 이벤트별 메시지 생성
  const message = buildSlackMessage(payload);

  // 4. Slack Incoming Webhook 전송
  const res = await fetch(process.env.SLACK_WEBHOOK_URL!, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message),
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Slack send failed" }, { status: 502 });
  }
  return NextResponse.json({ ok: true });
}

// 간단한 in-memory dedup (Vercel Function은 인스턴스 재사용될 수 있음)
const recentNotifications = new Map<string, number>();
function isDuplicate(taskId: string): boolean {
  const now = Date.now();
  const last = recentNotifications.get(taskId);
  recentNotifications.set(taskId, now);
  // 3초 후 자동 삭제하여 Map 누수 방지
  setTimeout(() => recentNotifications.delete(taskId), 3000);
  return last !== undefined && now - last < 3000;
}
```

### 4.4 메시지 포맷 (Slack Block Kit)

#### task_done

```
✅ 태스크 완료
━━━━━━━━━━━━━━━━━━━━━━━
📋 Job: KBO 스케줄 웹앱
🎯 TASK-002 UI 컴포넌트 설계
⏰ 완료: 2026-04-14 10:30 KST
🔗 [대시보드 보기]
```

```json
{
  "blocks": [
    { "type": "header",
      "text": { "type": "plain_text", "text": "✅ 태스크 완료" } },
    { "type": "section",
      "fields": [
        { "type": "mrkdwn", "text": "*Job*\nKBO 스케줄 웹앱" },
        { "type": "mrkdwn", "text": "*태스크*\nTASK-002 UI 컴포넌트 설계" }
      ] },
    { "type": "actions",
      "elements": [
        { "type": "button",
          "text": { "type": "plain_text", "text": "대시보드 보기" },
          "url": "{VERCEL_DASHBOARD_URL}/jobs/{job_id}" }
      ] }
  ]
}
```

#### stage_changed

```
🔄 태스크 단계 변경
TASK-003 API 연동 테스트
Todo → 🟡 In Progress
Job: KBO 스케줄 웹앱
```

#### task_added

```
➕ 새 태스크 추가
TASK-004 배포 환경 설정 #infra
Job: KBO 스케줄 웹앱 (총 7개 태스크)
```

#### daily_summary

```
📊 일일 진행 요약 — 2026-04-14
━━━━━━━━━━━━━━━━━━━━━━━
✅ 오늘 완료: 2개
🟡 진행 중: 1개
🔵 남은 Todo: 3개

오늘 완료한 태스크:
• TASK-001 프로젝트 초기 세팅
• TASK-002 UI 컴포넌트 설계
```

### 4.5 MCP 서버 → Notify 연동 (graceful skip)

```python
# notify.py
import httpx, os, logging
from datetime import datetime
from zoneinfo import ZoneInfo
from jobflow_mcp.config import config  # 전역 config 싱글톤 (config.yaml 로드)

logger = logging.getLogger(__name__)

async def notify_event(event_type: str, payload: dict):
    """fire-and-forget 본체 — 실패해도 태스크 작업에 영향 없음."""
    notify_url = config.get("vercel.dashboard_url")

    # Phase 3 배포 전 또는 미설정 시 조용히 스킵
    if not notify_url:
        logger.debug("vercel.dashboard_url 미설정, 알림 스킵")
        return

    secret = os.environ.get("NOTIFY_SECRET")
    if not secret:
        logger.warning("NOTIFY_SECRET 미설정, 알림 스킵")
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{notify_url}/api/slack/notify", json={
                "event": event_type,
                "secret": secret,
                **payload,
                "timestamp": datetime.now(tz=ZoneInfo("Asia/Seoul")).isoformat()
            })
    except Exception as e:
        logger.debug(f"알림 실패 (무시): {e}")

def fire_notify(event_type: str, payload: dict) -> None:
    """MCP 도구에서 호출하는 진입점 — asyncio.create_task로 블로킹 없이 실행.
    config.yaml의 slack.notify_events 목록에 없는 이벤트는 전송 생략."""
    import asyncio
    allowed = config.get("slack.notify_events") or []
    if allowed and event_type not in allowed:
        logger.debug(f"notify_events 목록에 없음, 스킵: {event_type}")
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_event(event_type, payload))
    except RuntimeError:
        # 이벤트 루프가 없는 컨텍스트 (테스트 등): 동기 실행
        asyncio.run(notify_event(event_type, payload))
```

**`jobflow config set` 명령 추가**
```bash
jobflow config set vercel.dashboard_url https://jobflow-xxx.vercel.app
jobflow config set github.repo owner/jobflow-tasks
```

### 4.6 daily_summary 스케줄 (Vercel Cron, 무활동 스킵)

```json
// vercel.json
{
  "crons": [
    { "path": "/api/slack/daily-summary", "schedule": "0 0 * * *" }
  ]
}
```

```typescript
// src/app/api/slack/daily-summary/route.ts
import { timingSafeEqual } from "crypto";

function verifyCron(header: string | null): boolean {
  const expected = process.env.CRON_SECRET;
  if (!expected || !header) return false;
  const provided = header.startsWith("Bearer ") ? header.slice(7) : "";
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function GET(req: NextRequest) {
  if (!verifyCron(req.headers.get("authorization"))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const summary = await buildDailySummary();

  // 활동 없는 날 노이즈 방지: 완료 0 + 진행중 0이면 스킵
  if (summary.done_today === 0 && summary.in_progress === 0) {
    return NextResponse.json({ ok: true, skipped: "no_activity" });
  }

  await sendSlackMessage(buildDailySummaryBlock(summary));
  return NextResponse.json({ ok: true });
}
```

### 4.7 환경 변수 추가

| 변수명 | 위치 | 설명 |
|--------|------|------|
| `SLACK_WEBHOOK_URL` | Vercel Secret | 개인 DM 채널용 Webhook |
| `NOTIFY_SECRET` | Vercel Secret + MCP 환경변수 | MCP→Vercel 인증 (DASHBOARD_TOKEN과 별개) |
| `CRON_SECRET` | Vercel Secret (자동 생성) | Vercel Cron 인증 |

> `buildDailySummary()`는 `/api/jobs`와 동일하게 GitHub에서 `.enc` 파일을 복호화해야 함.
> 따라서 **3.8절의 `JOBFLOW_KEY_B64`, `GH_TOKEN`, `GH_REPO`, `GH_TASKS_PATH`도 동일하게 필요**.

### 4.8 테스트 계획 (Phase 4)

| 테스트 | 검증 항목 |
|--------|----------|
| `notify.test.ts` | 시크릿 불일치 시 401, `timingSafeEqual` 사용 검증 |
| `buildSlackMessage.test.ts` | 각 이벤트 타입별 Block Kit 형식 |
| `dedup.test.ts` | 동일 task_id 3초 내 재발송 차단 |
| `daily_summary.test.ts` | 무활동 시 스킵, 활동 있을 때 집계 정확성 |
| `notify_event.test.py` | vercel.dashboard_url 미설정 시 graceful skip |
| 수동 E2E | 실제 Slack DM 채널 메시지 수신 확인 |

---

## 크로스컷팅 정책 {#cross-cutting}

### 두 git repo 관계

```
[ 코드 프로젝트 repo ]          [ ~/.jobflow/ repo ]
  - 소스 코드                     - 태스크 Markdown 파일
  - CLAUDE.md (JOBFLOW 블록)      - config.yaml, .key(gitignore)
  - 원격: 프로젝트 저장소          - 원격: jobflow-tasks repo
                                  - pre-push 훅: .md → .enc 암호화 업로드

연결 지점:
  `jobflow link --project <path>` 
  → 코드 프로젝트의 CLAUDE.md에 JOBFLOW 블록 주입
  → ~/.jobflow/config.yaml의 linked_projects에 경로 기록
  (파일 공유 없음, git 관계도 없음)
```

### 멀티 디바이스 동기화 정책

- **작업 시작 시 자동 pull**: MCP 서버 시작 또는 10분 이상 idle 후 첫 호출 시 `git pull --rebase`
- **Task 단위 충돌 감지**: Job 단위가 아닌 task_id 기준 비교
  - 한쪽만 수정 → 자동 병합
  - 양쪽 수정 (`updated_at` 다름) → `TaskConflict` 발생
- **충돌 해결 UX**: `job_pull(resolutions={task_id: "local" | "remote"})` 재호출
- **version 필드**: Job 전체의 변경 카운터로만 사용, 충돌 판정에는 task별 `updated_at` 사용

### 에러 처리 전략

| 레이어 | 에러 | 처리 |
|--------|------|------|
| MCP 도구 | 파일 I/O 실패 | 한국어 에러 메시지 반환 |
| git 커밋 | 커밋 실패 | 파일 변경 유지, 경고 출력, 다음 작업에 영향 없음 |
| GitHub 동기화 | API rate limit / 네트워크 | 재시도 없이 실패 메시지, 수동 `job_sync` 유도 |
| 대시보드 API | 인증 실패 | 401 반환, 클라이언트가 localStorage 삭제 후 `/login` |
| 대시보드 API | 복호화 실패 | 500 반환, "키 불일치 또는 파일 손상" 메시지 |
| Slack 알림 | Webhook 실패 | 로그만, 태스크 작업에 영향 없음 (fire-and-forget) |
| Slack 중복 | 동일 task_id 3초 내 | 스킵 (dedup dict) |

---

## 전체 의존성 및 배포 흐름

```
Phase 1 (MCP + 파일)
    ↓ 완료 후
Phase 2 (암호화 동기화)
    ↓ 완료 후
Phase 3 (Vercel 대시보드, Bearer Token)  ← Phase 2의 .enc 파일 필요
    ↓ 병행 가능
Phase 4 (Slack 알림)                     ← Phase 3의 Vercel URL 필요
```

### 추천 개발 순서

| 순서 | 작업 | 의존성 |
|------|------|--------|
| 1 | Phase 1 MCP 기본 도구 (`job_new`, `task_add`, `task_check`) | 없음 |
| 2 | Phase 1 `jobflow init` (git init 포함) + git 자동 커밋 + CLAUDE.md 연동 | 1 |
| 3 | Phase 2 암호화 구현 + `job_sync` + `job_pull` (Task 단위 머지) | 1,2 |
| 4 | Phase 3 API Routes (복호화 + GitHub) + Bearer Token middleware | 3 |
| 5 | Phase 3 Kanban UI (3컬럼, 반응형) | 4 |
| 6 | Phase 4 Slack 알림 | 5 (Vercel URL 필요) |
| 7 | Phase 3 히스토리 뷰어 (lazy load, `diff2html` dynamic import) | 5 |
| 8 | Phase 4 daily_summary Cron (무활동 스킵) | 6 |
