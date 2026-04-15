# JobFlow 설계 리뷰

> DESIGN.md 기반 | 작성일: 2026-04-15

---

## 목차

- [Phase 1 — MCP 서버 + 파일 구조](#phase-1)
- [Phase 2 — GitHub 암호화 동기화](#phase-2)
- [Phase 3 — Vercel 대시보드](#phase-3)
- [Phase 4 — Slack 단방향 알림](#phase-4)
- [크로스컷팅 이슈](#cross-cutting)
- [수정 우선순위 요약](#summary)

---

## Phase 1 — MCP 서버 + 파일 구조 {#phase-1}

### 버그/불명확

**1. MCP 도구 명명 방식 혼동**

설계서에 `/job new`, `/task add` 처럼 슬래시 커맨드로 표기했는데, MCP 도구는 실제로 함수명으로 등록됩니다. Claude가 `job_new`, `task_add`로 호출하는 형태입니다. 슬래시는 Claude Code CLI 커맨드와 혼동 소지가 있어 명확히 구분 필요.

---

**2. `/job new`의 "Claude에게 태스크 분할 요청" 로직이 불가능**

```
처리:
  3. Claude에게 goal 기반 태스크 분할 요청 (tool_use 응답)  ← 문제
```

MCP 서버는 Claude가 호출하는 도구 서버입니다. 서버가 역으로 Claude에게 요청하는 구조는 표준 MCP 흐름이 아닙니다. 올바른 흐름:

- Claude가 대화 중 태스크 목록 제안 → 사용자 확인 → `job_new(tasks=[...])` 호출
- 또는 `job_new`가 goal만 받고 태스크 없이 파일 생성 → Claude가 이후 `task_add`를 연속 호출

---

**3. `~/.jobflow/`가 git repo인지 불명확**

Phase 1에서 `git commit`을 수행하는데, `~/.jobflow/`가 별도 git repo로 초기화되어야 합니다. `jobflow init` 시 `git init ~/.jobflow/` + remote 설정 플로우가 빠져 있습니다.

---

**4. `subprocess` vs `pygit2` 혼용**

1.6절에 둘 다 언급됩니다. 의존성 추가 없이 `subprocess`로 통일하는 게 더 단순합니다.

---

**5. `started_at` / `completed_at` 저장 파싱 규칙 모호**

```markdown
- [~] TASK-002 제목
  - 체크리스트 항목
  > started_at: 2026-04-14T09:00:00+09:00   ← '>'로 구분하는 규칙
```

파서가 `>` 블록쿼트와 시간 메타데이터를 어떻게 구분하는지 규칙 명시 필요. Blockquote가 일반 Markdown 렌더링에서 눈에 띄게 표시되어 파일 가독성을 해칩니다.

**대안:** HTML 주석 방식 `<!-- started_at: ... -->` 또는 인덴트된 코드 블록 고려.

---

**6. `/task check`의 단계 이동 로직 모호성**

```
In Progress → Review: (자동 or 명시적)  ← 모호
```

명확한 정책 필요:
- `/task check` → 항상 다음 순서 단계로 이동
- `/task move to=done` → 임의 단계로 이동

두 도구의 역할을 명확히 분리해야 합니다.

---

**7. `jobflow link --project`가 무엇을 하는지 불명확**

이 명령이 `config.yaml`에 project 경로를 저장하는 건지, CLAUDE.md에 블록을 삽입하는 건지, 현재 프로젝트를 어떻게 "감지"하는지 미명시.

---

## Phase 2 — GitHub 암호화 동기화 {#phase-2}

### 버그/불명확

**1. pre-push 훅의 대상 repo 불명확**

```bash
# .git/hooks/pre-push  ← 어느 repo?
```

코드 프로젝트 repo의 훅인지, `~/.jobflow/` repo의 훅인지 모호합니다. `~/.jobflow/.git/hooks/pre-push`가 맞습니다. 명시 필요.

---

**2. GitHub Actions 대안의 `paths` 조건 작동 안 함**

```yaml
on:
  push:
    paths: ['~/.jobflow/**']  ← 로컬 경로, GitHub Actions에서 불가
```

GitHub Actions는 remote repo의 파일 변경을 감지합니다. `~/.jobflow/`는 로컬 경로라 이 트리거는 절대 작동하지 않습니다. 별도 jobs 전용 GitHub repo를 remote로 두고, 해당 repo의 Actions로 설명해야 합니다.

---

**3. `assert` 사용이 위험**

```python
assert data[:6] == MAGIC, "Invalid JobFlow encrypted file"
```

Python `-O` 플래그 실행 시 assert가 비활성화됩니다. 보안 검증은 아래 패턴으로 교체 필요:

```python
if data[:6] != MAGIC:
    raise ValueError("Invalid JobFlow encrypted file")
```

---

**4. `/job pull` 충돌 해결 UX 미정의**

"경고 후 사용자 확인"이라고만 되어 있는데, MCP 도구에서 사용자 입력을 받는 방식이 구체적이지 않습니다. `/job pull --force` 플래그나 별도 `job_pull_confirm` 도구 추가 방안 명시 필요.

---

**5. `.jobflow-index.json`에 날짜 기반 job_id 노출**

```json
{ "job_id": "job-20260414-001" }  ← 날짜 정보 public repo에 공개
```

public repo라면 작업 시작일이 노출됩니다. 민감도가 낮다면 허용 가능하나 의식적 결정으로 명시 필요.

---

## Phase 3 — Vercel 대시보드 {#phase-3}

### 버그/불명확

**1. `decrypt.ts` 주석과 구현 불일치**

```
lib/decrypt.ts 주석 — "Web Crypto API 복호화"
실제 코드       — import { createDecipheriv } from "crypto"  (Node.js crypto)
```

서버 사이드이므로 Node.js crypto가 맞지만, 주석을 수정해야 합니다.

---

**2. `/api/jobs`가 인증 없이 완전한 복호화 데이터 반환**

```
보안: URL 비공개 관리 + 복호화 키 Vercel Secret 보관
```

URL 비공개만으로 보호하는 건 Security through obscurity입니다. Vercel 환경 변수 하나(`DASHBOARD_TOKEN`)를 추가하고 `Authorization: Bearer` 헤더 검증을 API Route에 추가하면 코드 5줄로 실질적 보안이 확보됩니다. MVP라도 이 정도는 필요합니다.

---

**3. 히스토리 diff 계산의 타임아웃 위험**

```json
{ "maxDuration": 10 }  // vercel.json
```

커밋별로 `.enc` 파일을 GitHub API로 가져오고 복호화하면: API 호출 × 커밋 수. 커밋이 20개면 20번 GitHub API 요청 → 10초 타임아웃 초과 가능.

**대안:** diff 뷰어를 lazy load 구조로 변경 — 클릭 시 단일 커밋 비교만 요청.

---

**4. `next-pwa`와 Next.js 14 App Router 호환성 문제**

`next-pwa` 공식 패키지는 App Router 완전 지원이 불안정합니다.

**대안:** `@ducanh2912/next-pwa` (커뮤니티 포크) 또는 Serwist 직접 사용 권장.

---

**5. `diff2html` 번들 크기**

히스토리 뷰어 진입 시 `diff2html`이 메인 번들에 포함되면 초기 로딩에 영향.

```tsx
// 코드 스플리팅 적용 필요
const HistoryViewer = dynamic(() => import('@/components/HistoryViewer'), { ssr: false })
```

---

**6. SWR + `no-store` 캐시 충돌**

API가 `no-store`를 반환해도 SWR은 자체 in-memory 캐시를 유지합니다. 데이터 최신성 보장을 위해 SWR 옵션 명시 필요:

```ts
useSWR('/api/jobs', fetcher, {
  revalidateOnFocus: true,
  refreshInterval: 30000,
})
```

---

**7. 모바일 4탭이 너무 좁음**

```
│ Todo│InProg│Review│Done │
```

320px 화면에서 4탭은 각 탭이 약 70px. "In Progress" 텍스트가 잘립니다. 탭 레이블 단축 또는 아이콘 병행 사용 규칙 정의 필요.

---

## Phase 4 — Slack 단방향 알림 {#phase-4}

### 버그/불명확

**1. 시크릿 비교에 타이밍 공격 취약점**

```typescript
// 취약한 코드
if (payload.secret !== process.env.NOTIFY_SECRET) { ... }
```

문자열 `!==` 비교는 타이밍 공격에 노출됩니다.

```typescript
// 수정
import { timingSafeEqual } from "crypto"
const a = Buffer.from(payload.secret ?? "")
const b = Buffer.from(process.env.NOTIFY_SECRET!)
if (a.length !== b.length || !timingSafeEqual(a, b)) {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
}
```

---

**2. `config.yaml`의 `vercel.dashboard_url`이 Phase 4 설치 전에는 비어 있음**

Phase 1 설치 시 Vercel 배포 전이므로 이 값이 비어 있습니다. MCP 서버의 `notify_event()`가 URL 미설정 시 graceful하게 스킵하는 분기 필요.

```python
async def notify_event(event_type: str, payload: dict):
    notify_url = config.get("vercel.dashboard_url")
    if not notify_url:
        logger.debug("vercel.dashboard_url 미설정, 알림 스킵")
        return
    ...
```

`jobflow config set vercel.dashboard_url=https://...` 명령도 추가 필요.

---

**3. `daily_summary` 알림 — 활동 없는 날 노이즈**

완료 태스크가 0개인 날도 Cron이 실행되어 "오늘 완료: 0개" 메시지가 발송됩니다.

```typescript
if (summary.done_today === 0 && summary.in_progress === 0) return NextResponse.json({ ok: true, skipped: true })
```

---

**4. 알림 중복 발송 위험**

`/task check`를 빠르게 연속 호출하면 동일 태스크에 대해 알림이 중복 발송될 수 있습니다.

**대안:** 동일 `task_id`에 대해 마지막 알림 이후 3초 내 재발송 차단 (간단한 in-memory dict로 구현 가능).

---

**5. Slack 메시지에 대시보드 URL 노출**

```json
{ "url": "{VERCEL_DASHBOARD_URL}/jobs/{job_id}" }
```

대시보드 URL을 "비공개 관리"로 보호하는데, Slack 메시지에 URL이 평문으로 노출됩니다. Slack 채널 멤버 범위와 URL 공개 범위를 일치시켜야 합니다.

---

## 크로스컷팅 이슈 {#cross-cutting}

### 1. 두 git repo 관계가 전체 설계에서 가장 큰 혼선 포인트

```
코드 프로젝트 repo  ← 코드 커밋, CLAUDE.md 포함
~/.jobflow/ repo   ← 태스크 파일 커밋, .enc 파일 GitHub 동기화
```

두 repo의 관계, pre-push 훅이 어느 repo의 훅인지, `jobflow link`가 이 두 repo를 어떻게 연결하는지를 아키텍처 다이어그램으로 한 번 정리하면 설계서 전체 흐름이 명확해집니다.

---

### 2. `Review` 단계의 실제 필요성

1인 도구에서 Review 단계는 "타인의 승인"이 필요한 경우에만 의미가 있습니다. PRD에서 "1인 도구"로 명시된 만큼 MVP에서는 `Todo → In Progress → Done` 3단계로 단순화하고, Review는 향후 확장 항목으로 빼는 방안을 검토할 만합니다.

---

### 3. `version` 증가 전략의 충돌 위험

멀티 디바이스 사용 시 기기 A에서 version=3, 기기 B에서도 version=3에서 각각 수정 후 sync하면 충돌이 발생합니다. 현재 설계의 "로컬 version > 원격: 경고" 방식으로는 이 케이스가 처리되지 않습니다. `last_write_wins` 또는 timestamp 기반의 명확한 충돌 정책 필요.

---

### 4. 에러 처리 전략 통합

각 Phase에 흩어진 에러 처리를 한 곳에 정리하면 구현 시 일관성이 생깁니다.

| 레이어 | 에러 | 처리 |
|--------|------|------|
| MCP 도구 | 파일 I/O 실패 | 사용자에게 한국어 에러 메시지 반환 |
| git 커밋 | 커밋 실패 | 파일 변경은 유지, 경고만 출력 |
| GitHub 동기화 | API rate limit / 네트워크 | 재시도 없이 실패 메시지, 수동 `/job sync` 유도 |
| Vercel API | 복호화 실패 | 500 반환, 클라이언트에 "키 불일치" 표시 |
| Slack 알림 | Webhook 실패 | 로그만, 태스크 작업에 영향 없음 |

---

## 수정 우선순위 요약 {#summary}

| 우선순위 | 항목 | Phase |
|----------|------|-------|
| **즉시 수정** | `/job new`의 MCP 역방향 호출 구조 재설계 | P1 |
| **즉시 수정** | `~/.jobflow/` git repo 초기화를 설계에 명시 | P1 |
| **즉시 수정** | GitHub Actions `paths: ['~/.jobflow/**']` 오류 수정 | P2 |
| **즉시 수정** | `/api/jobs` Bearer Token 인증 추가 | P3 |
| **즉시 수정** | 시크릿 비교 `timingSafeEqual` 교체 | P4 |
| **권장** | `assert` → `raise ValueError` 교체 | P2 |
| **권장** | 히스토리 diff lazy load 구조 변경 | P3 |
| **권장** | `next-pwa` → Serwist 교체 검토 | P3 |
| **권장** | `daily_summary` 무활동 스킵 조건 추가 | P4 |
| **논의** | Review 단계 MVP 제거 여부 | P1/P3 |
| **논의** | 멀티 디바이스 충돌 정책 | P2 |
