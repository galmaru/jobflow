# JobFlow

Claude MCP 기반 개인 태스크 관리 도구.  
Markdown 파일로 태스크를 관리하고, GitHub에 암호화 동기화하며, Vercel 대시보드와 Slack 알림을 제공합니다.

---

## 구성

```
jobflow/
├── jobflow-mcp/          # Python MCP 서버 (Claude Code 연동)
└── jobflow-dashboard/    # Next.js 15 Vercel 대시보드
```

---

## 기능 요약

| Phase | 기능 |
|-------|------|
| 1 | MCP 서버 — Claude Code에서 태스크 CRUD |
| 2 | GitHub 암호화 동기화 (AES-256-GCM) |
| 3 | Vercel 대시보드 — 칸반 보드 + 이력 뷰어 |
| 4 | Slack 단방향 알림 (Block Kit) |

---

## 빠른 시작

### 1. MCP 서버 설치

```bash
cd jobflow-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 초기화 (~/.jobflow 디렉토리 + AES 키 + pre-push 훅 생성)
jobflow init

# GitHub 원격 저장소 연결
jobflow remote add --url https://github.com/<계정>/<저장소>.git

# 프로젝트 CLAUDE.md 연동
jobflow link --project /path/to/your/project
```

### 2. Claude Code MCP 등록

`~/.claude/claude_desktop_config.json` (또는 Claude Code 설정)에 추가:

```json
{
  "mcpServers": {
    "jobflow": {
      "command": "/path/to/jobflow-mcp/.venv/bin/python",
      "args": ["-m", "jobflow_mcp.server"]
    }
  }
}
```

### 3. 대시보드 배포 (Vercel)

```bash
cd jobflow-dashboard
npm install
```

Vercel 환경변수 설정:

| 변수 | 설명 |
|------|------|
| `DASHBOARD_TOKEN` | Bearer 토큰 (대시보드 인증) |
| `GITHUB_TOKEN` | 암호화 파일 조회용 PAT |
| `GITHUB_REPO` | `owner/repo` |
| `GITHUB_BRANCH` | 기본값 `main` |
| `GITHUB_PATH` | 기본값 `tasks/` |
| `ENCRYPTION_KEY` | AES-256 키 (base64, `~/.jobflow/.key`와 동일) |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `NOTIFY_SECRET` | MCP → 대시보드 알림 공유 시크릿 |
| `CRON_SECRET` | 일간 요약 Cron 인증 토큰 |

배포 후:

```bash
jobflow config set vercel.dashboard_url https://your-app.vercel.app
```

---

## MCP 도구

Claude Code 세션에서 아래 도구를 사용할 수 있습니다.

| 도구 | 설명 |
|------|------|
| `job_new` | 새 업무 파일 생성 |
| `job_list` | 전체 업무 목록 조회 |
| `job_status` | 칸반 현황 출력 |
| `task_add` | 태스크 추가 |
| `task_check` | 태스크 상태 순차 이동 (Todo → In Progress → Done) |
| `task_move` | 태스크 임의 이동 |
| `job_sync` | GitHub 암호화 동기화 (push) |
| `job_pull` | GitHub에서 pull + 충돌 해결 |

---

## 태스크 파일 형식

`~/.jobflow/jobs/todo-{업무명}.md`

```markdown
---
job_id: "job-20260414-001"
job_name: "KBO 스케줄 웹앱"
goal: "2026 KBO 시즌 실시간 스케줄 조회 앱 완성"
status: "in_progress"
---

### 🔵 Todo
- [ ] TASK-002 API 연동 #backend !high

### 🟡 In Progress
- [~] TASK-001 UI 레이아웃 #frontend !medium
  <!-- started_at: 2026-04-14T09:00:00+09:00 -->

### 🟢 Done
- [x] TASK-003 기획 완료 #docs !low
  <!-- completed_at: 2026-04-14T08:00:00+09:00 -->
```

---

## 데이터 보안

- 태스크 파일은 GitHub 업로드 전 **AES-256-GCM**으로 암호화
- 암호화 키(`~/.jobflow/.key`)는 로컬에만 보관 — Git 커밋 불가 (`.gitignore` 적용)
- 대시보드 API는 **Bearer Token + timingSafeEqual** 검증
- Slack Webhook URL은 Vercel Secret으로만 관리

---

## 개발

### MCP 서버 테스트

```bash
cd jobflow-mcp
source .venv/bin/activate
pytest
```

### 대시보드 테스트

```bash
cd jobflow-dashboard
npm test
```

---

## 라이선스

MIT
