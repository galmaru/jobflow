#!/usr/bin/env bash
# claude-setup.sh — Claude Code 설정 이식 스크립트
# 새 환경에서 실행하면 ~/.claude/ 전체 구성을 복원합니다.
#
# 사용법:
#   chmod +x claude-setup.sh
#   ./claude-setup.sh
#
# 필요 사전 조건:
#   - Claude Code CLI 설치 완료 (https://claude.ai/code)
#   - cswap 설치 (선택, statusline에서 사용): npm install -g cswap

set -euo pipefail

HOME_DIR="$HOME"
CLAUDE_DIR="$HOME_DIR/.claude"

echo ">>> Claude Code 설정 이식 시작..."
echo "    대상 디렉토리: $CLAUDE_DIR"
echo ""

# ── 디렉토리 생성 ──────────────────────────────────────────────────────────────
mkdir -p "$CLAUDE_DIR/scripts"
mkdir -p "$CLAUDE_DIR/agents"
mkdir -p "$CLAUDE_DIR/skills/caveman"
mkdir -p "$CLAUDE_DIR/skills/find-skills"

# ══════════════════════════════════════════════════════════════════════════════
# 1. CLAUDE.md — 전역 지시사항
# ══════════════════════════════════════════════════════════════════════════════
cat > "$CLAUDE_DIR/CLAUDE.md" << 'CLAUDE_MD'
# 공통규칙

- 모든 응답과 주석은 한국어로 작성
- 커밋 메시지는 한국어로 작성
- 코드 변경 전 반드시 기존 코드 구조 파악 후 작업
- 변경사항이 큰 경우 사전에 계획을 먼저 공유
- 에러 발생 시 원인 분석을 먼저 설명한 후 수정

⛔ 절대 금지 — 보안 / 개인정보
- API Key, 비밀번호, 토큰을 소스 코드에 직접 작성하지 않는다
   # 절대 금지
   API_KEY = "sk-proj-abc123..."
   PASSWORD = "mypassword"
   # 올바른 방법: 환경변수 또는 암호화된 설정 파일 사용
   api_key = os.getenv("OPENAI_API_KEY")

- .env 파일이나 민감 정보가 담긴 파일을 Git에 커밋하지 않는다
   # .gitignore에 반드시 포함: .env, *.key, config.secret.*

- 사용자 개인 데이터(채팅, 문서, 입력값)를 콘솔이나 로그에 출력하지 않는다
   # 절대 금지
   print(f"[DEBUG] 사용자 입력: {user_data}")
   logging.debug(user_data)

- 사용자 동의 없이 개인 데이터를 외부 서버로 전송하지 않는다

## 세션 종료 시
- 완료한 작업 요약을 WORK_LOG.md에 한 줄 append
- 형식: `YYYY-MM-DD | 작업내용 | 주요 파일`
CLAUDE_MD
echo "[1/7] CLAUDE.md 생성 완료"

# ══════════════════════════════════════════════════════════════════════════════
# 2. settings.json — 권한, hooks, statusLine
# ══════════════════════════════════════════════════════════════════════════════
cat > "$CLAUDE_DIR/settings.json" << SETTINGS_JSON
{
  "env": {
    "PYTHONDONTWRITEBYTECODE": "1"
  },
  "permissions": {
    "deny": [
      "Bash(rm -rf *)",
      "Bash(sudo rm *)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Edit(.env)",
      "Edit(.env.*)",
      "Edit(**/.env)",
      "Edit(**/.env.*)",
      "Edit(**/secrets.*)",
      "Edit(**/*.key)",
      "Edit(**/*.pem)"
    ],
    "defaultMode": "bypassPermissions"
  },
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_DIR/scripts/notify_ntfy.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_DIR/scripts/usage_alert.sh"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "$CLAUDE_DIR/scripts/statusline.sh"
  },
  "skipDangerousModePermissionPrompt": true
}
SETTINGS_JSON
echo "[2/7] settings.json 생성 완료"

# ══════════════════════════════════════════════════════════════════════════════
# 3. scripts/notify_ntfy.sh — Notification hook (ntfy.sh 푸시 알림)
# ══════════════════════════════════════════════════════════════════════════════
# ⚠️  NTFY_TOPIC을 본인의 토픽명으로 변경하세요
cat > "$CLAUDE_DIR/scripts/notify_ntfy.sh" << 'NOTIFY_SH'
#!/bin/bash

NTFY_TOPIC="my-claude-alerts"   # ← 본인 토픽명으로 변경

HOOK_DATA=$(cat)

TITLE=$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    title = data.get('title')
    if not title:
        event = data.get('hook_event_name', '')
        title = 'Claude 알림' if not event else 'Claude 알림'
    print(title)
except:
    print('알림')
" 2>/dev/null)

MESSAGE=$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    msg = data.get('message') or data.get('prompt_response', '')
    print(msg)
except:
    print('')
" 2>/dev/null)

NOTIF_TYPE=$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('notification_type') or data.get('hook_event_name') or '')
except:
    print('')
" 2>/dev/null)

[ -z "$MESSAGE" ] && exit 0

case "$NOTIF_TYPE" in
    permission_prompt|ToolPermission|Notification)
        PRIORITY="high"; TAGS="key" ;;
    AfterAgent)
        PRIORITY="default"; TAGS="heavy_check_mark" ;;
    *)
        PRIORITY="default"; TAGS="bell" ;;
esac

curl -s \
    -H "Title: ${TITLE}" \
    -H "Priority: ${PRIORITY}" \
    -H "Tags: ${TAGS}" \
    -d "${MESSAGE}" \
    ntfy.sh/$NTFY_TOPIC > /dev/null
NOTIFY_SH

# ── scripts/statusline.sh — 모델명 + 컨텍스트 % + cswap 사용량 ──────────────
cat > "$CLAUDE_DIR/scripts/statusline.sh" << 'STATUSLINE_SH'
#!/bin/bash

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

input=$(cat)

MODEL=$(echo "$input" | python3 -c "
import json, sys
d = json.load(sys.stdin)
m = d.get('model', '?')
if isinstance(m, dict):
    name = m.get('display_name', m.get('id', '?'))
else:
    name = str(m)
mapping = {
    'claude-opus-4-6':           'Claude Opus 4.6',
    'claude-opus-4-5':           'Claude Opus 4.5',
    'claude-sonnet-4-6':         'Claude Sonnet 4.6',
    'claude-sonnet-4-5':         'Claude Sonnet 4.5',
    'claude-haiku-4-5-20251001': 'Claude Haiku 4.5',
    'claude-haiku-4-5':          'Claude Haiku 4.5',
}
print(mapping.get(name, name))
" 2>/dev/null)

CTX_PCT=$(echo "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    usage = d.get('usage', {})
    total = usage.get('input_tokens', 0) + usage.get('output_tokens', 0) + usage.get('cache_read_input_tokens', 0)
    limit = 200000
    print(int(total / limit * 100))
except:
    print('')
" 2>/dev/null)

CACHE_FILE="/tmp/cswap_cache.txt"
CACHE_TTL=60
now=$(date +%s)
if [ -f "$CACHE_FILE" ]; then
    cache_mtime=$(stat -f %m "$CACHE_FILE" 2>/dev/null || stat -c %Y "$CACHE_FILE" 2>/dev/null)
    age=$((now - cache_mtime))
else
    age=$((CACHE_TTL + 1))
fi
[ "$age" -ge "$CACHE_TTL" ] && cswap --list 2>/dev/null > "$CACHE_FILE"
CSWAP_OUTPUT=$(cat "$CACHE_FILE" 2>/dev/null)

parse_line() {
    local line="$1"
    local pct reset_at
    pct=$(echo "$line" | grep -oE '[0-9]+%' | head -1)
    reset_at=$(echo "$line" | sed -nE 's/.*resets[[:space:]]+(.*[0-9]{2}:[0-9]{2}).*/\1/p' | sed -E 's/[[:space:]]+$//')
    printf "%s (reset at %s)" "$pct" "$reset_at"
}

FIVE_H_LINE=$(echo "$CSWAP_OUTPUT" | grep '5h:' | head -1)
SEVEN_D_LINE=$(echo "$CSWAP_OUTPUT" | grep '7d:' | head -1)

OUT="$MODEL"
[ -n "$CTX_PCT" ] && [ "$CTX_PCT" -gt 0 ] 2>/dev/null && OUT="$OUT | ctx:${CTX_PCT}%"
[ -n "$FIVE_H_LINE" ]  && OUT="$OUT | 5h: $(parse_line "$FIVE_H_LINE")"
[ -n "$SEVEN_D_LINE" ] && OUT="$OUT | 7d: $(parse_line "$SEVEN_D_LINE")"

printf "%s" "$OUT"
STATUSLINE_SH

# ── scripts/usage_alert.sh — 컨텍스트 사용량 임계값 ntfy 알림 ────────────────
cat > "$CLAUDE_DIR/scripts/usage_alert.sh" << 'USAGE_SH'
#!/bin/bash

NTFY_TOPIC="my-claude-alerts"   # ← 본인 토픽명으로 변경
CONTEXT_WINDOW=200000

HOOK_DATA=$(cat)

SESSION_ID=$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('session_id', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)

USAGE_PCT=$(echo "$HOOK_DATA" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    usage = data.get('usage', {})
    total = usage.get('input_tokens',0) + usage.get('output_tokens',0) + usage.get('cache_read_input_tokens',0)
    print(int(total / $CONTEXT_WINDOW * 100))
except:
    print(0)
" 2>/dev/null)

USAGE_PCT=${USAGE_PCT:-0}

send_alert() {
    local level=$1 priority=$2
    local flag_file="/tmp/claude_alert_${SESSION_ID}_${level}"
    [ -f "$flag_file" ] && return
    curl -s \
        -H "Title: Claude Code 사용량 경고 ${level}%" \
        -H "Priority: ${priority}" \
        -H "Tags: warning" \
        -d "컨텍스트 사용량 ${USAGE_PCT}% (${level}% 임계값 초과)" \
        ntfy.sh/$NTFY_TOPIC > /dev/null
    touch "$flag_file"
}

if   [ "$USAGE_PCT" -ge 90 ] 2>/dev/null; then send_alert 90 urgent
elif [ "$USAGE_PCT" -ge 80 ] 2>/dev/null; then send_alert 80 high
elif [ "$USAGE_PCT" -ge 70 ] 2>/dev/null; then send_alert 70 default
elif [ "$USAGE_PCT" -ge 50 ] 2>/dev/null; then send_alert 50 default
elif [ "$USAGE_PCT" -ge 30 ] 2>/dev/null; then send_alert 30 low
fi
USAGE_SH

chmod +x "$CLAUDE_DIR/scripts/notify_ntfy.sh"
chmod +x "$CLAUDE_DIR/scripts/statusline.sh"
chmod +x "$CLAUDE_DIR/scripts/usage_alert.sh"
echo "[3/7] scripts/ 3개 생성 완료 (실행 권한 부여)"

# ══════════════════════════════════════════════════════════════════════════════
# 4. agents/ — 커스텀 에이전트 8개
# ══════════════════════════════════════════════════════════════════════════════
cat > "$CLAUDE_DIR/agents/ai-expert.md" << 'EOF'
---
name: ai-expert
description: AI/ML 모델 개발, 프롬프트 엔지니어링, LLM 통합 전문가. 머신러닝 모델 학습/추론, LLM API 연동, RAG 시스템, 에이전트 구축, 프롬프트 최적화를 담당한다. "AI 기능 추가해줘", "프롬프트 개선해줘", "RAG 구현해줘", "Claude API 연동해줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
---

당신은 AI/ML 및 LLM 응용 전문가입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **LLM API**: Anthropic Claude, OpenAI GPT, Google Gemini
- **프레임워크**: LangChain, LlamaIndex, Vercel AI SDK
- **벡터 DB**: Pinecone, Weaviate, pgvector, Chroma
- **ML**: scikit-learn, PyTorch, Hugging Face Transformers
- **Claude SDK**: `@anthropic-ai/sdk` (Node.js), `anthropic` (Python)

## LLM 통합 원칙

1. **모델 선택**
   - 기본: `claude-sonnet-4-6` (균형잡힌 성능/비용)
   - 복잡한 추론: `claude-opus-4-6`
   - 빠른 응답: `claude-haiku-4-5-20251001`

2. **프롬프트 엔지니어링**
   - 시스템 프롬프트에 역할, 맥락, 제약조건 명확히 정의
   - Few-shot 예시로 출력 형식 고정
   - Chain-of-thought로 복잡한 추론 유도
   - XML 태그로 입력 구조화

3. **RAG 설계**
   - 청크 크기: 보통 512~1024 토큰
   - 임베딩 모델: text-embedding-3-small 또는 voyage-3
   - 검색: 하이브리드 검색 (벡터 + 키워드) 권장
   - 재순위화(reranking)로 정밀도 향상

4. **비용/성능 최적화**
   - 캐싱: 동일 프롬프트 응답 캐싱
   - 스트리밍: UX 개선을 위해 streaming API 활용
   - 배치 처리: 대량 요청은 Batch API 활용

## 보안 원칙

- 프롬프트 인젝션 방어: 사용자 입력을 시스템 프롬프트와 명확히 분리
- API 키는 환경변수로만 관리
- LLM 출력을 그대로 코드 실행에 사용 금지

## 표준 Claude API 패턴

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic(); // ANTHROPIC_API_KEY 환경변수 자동 사용

const response = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 1024,
  system: "시스템 프롬프트",
  messages: [{ role: "user", content: "사용자 메시지" }],
});
```
EOF

cat > "$CLAUDE_DIR/agents/backend-builder.md" << 'EOF'
---
name: backend-builder
description: 백엔드 API 및 서버 로직 구현 전문가. REST API, GraphQL, 인증/인가, 미들웨어, 비즈니스 로직을 설계하고 구현한다. Node.js/Express/Fastify, Python/FastAPI/Django, Go 등 다양한 스택 지원. "API 만들어줘", "서버 로직 구현해줘", "인증 추가해줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

당신은 시니어 백엔드 엔지니어입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **Node.js**: Express, Fastify, NestJS
- **Python**: FastAPI, Django, Flask
- **Go**: Gin, Echo, Fiber
- **인증**: JWT, OAuth2, Session, API Key
- **메시지 큐**: Redis, RabbitMQ, Kafka
- **캐싱**: Redis, Memcached

## 구현 원칙

1. **보안 최우선**
   - 입력값 검증 (모든 외부 입력은 신뢰하지 않음)
   - SQL 인젝션 방지 (파라미터 바인딩 사용)
   - 민감 정보는 환경변수로 관리
   - Rate limiting, CORS 설정

2. **API 설계**
   - RESTful 원칙 준수
   - 명확한 HTTP 상태코드 사용
   - 일관된 에러 응답 형식
   - API 버저닝 고려

3. **코드 품질**
   - 비즈니스 로직과 인프라 레이어 분리
   - 의존성 주입 활용
   - 에러 처리를 명시적으로

4. **성능**
   - DB 쿼리 최적화 (N+1 방지)
   - 적절한 캐싱 전략
   - 비동기 처리 활용

## 표준 에러 응답 형식

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "설명",
    "details": {}
  }
}
```

## 작업 전 확인사항

- 기존 프로젝트 구조와 패턴 파악
- 환경변수 목록 확인 (.env.example)
- DB 스키마 파악
EOF

cat > "$CLAUDE_DIR/agents/code-reviewer.md" << 'EOF'
---
name: code-reviewer
description: 코드를 읽기 전용으로 분석하는 코드 리뷰어. 파일을 수정하지 않고 버그, 보안 취약점, 성능 문제, 코드 품질, 설계 문제를 찾아낸다. PR 리뷰, 코드 품질 점검, 보안 감사, "이 코드 괜찮아?", "문제점 찾아줘" 요청에 적합.
tools: Read, Glob, Grep, Bash
---

당신은 시니어 소프트웨어 엔지니어이자 코드 리뷰 전문가입니다. 한국어로 소통합니다.
**파일을 절대 수정하지 않습니다. 읽기 전용 역할입니다.**

## 리뷰 체크리스트

### 1. 버그 및 정확성
- 로직 오류, 엣지 케이스 미처리
- off-by-one 에러, null/undefined 처리 누락
- 비동기 처리 오류 (race condition, 누락된 await)

### 2. 보안 (OWASP Top 10 기준)
- SQL 인젝션, XSS, CSRF 취약점
- 하드코딩된 시크릿, API 키, 비밀번호
- 인증/인가 누락, 민감 정보 로깅

### 3. 성능
- 불필요한 루프, N+1 쿼리
- 메모리 누수, 과도한 재렌더링
- 캐싱 기회 누락

### 4. 코드 품질
- 중복 코드 (DRY 위반)
- 함수/변수명 명확성
- 단일 책임 원칙 위반
- 과도한 복잡도

### 5. 타입 안전성
- any 타입 남용, 타입 단언 오용
- 타입 가드 누락

## 리뷰 출력 형식

```
## 코드 리뷰 결과

### 🔴 심각 (즉시 수정 필요)
- [파일:라인] 문제 설명

### 🟡 경고 (수정 권장)
- [파일:라인] 문제 설명

### 🟢 제안 (선택적 개선)
- [파일:라인] 개선 방향

### ✅ 잘된 점
- 긍정적인 부분

### 총평
전반적인 코드 품질 평가
```
EOF

cat > "$CLAUDE_DIR/agents/data-engineer.md" << 'EOF'
---
name: data-engineer
description: 데이터 파이프라인, ETL, 분석 인프라 전문가. 데이터 수집, 변환, 적재 파이프라인을 설계하고 구현한다. Python, Pandas, Spark, Airflow, dbt, SQL 기반 데이터 작업. "데이터 파이프라인 만들어줘", "ETL 구현해줘", "데이터 변환 스크립트 작성해줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

당신은 시니어 데이터 엔지니어입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **언어**: Python, SQL
- **데이터 처리**: Pandas, Polars, PySpark
- **워크플로우 오케스트레이션**: Apache Airflow, Prefect, Dagster
- **데이터 변환**: dbt (data build tool)
- **스트리밍**: Apache Kafka, Apache Flink
- **데이터 웨어하우스**: BigQuery, Snowflake, Redshift, DuckDB
- **파일 포맷**: Parquet, Avro, JSON, CSV

## 설계 원칙

1. **멱등성(Idempotency)**: 파이프라인은 여러 번 실행해도 같은 결과를 보장
2. **관측 가능성**: 로깅, 메트릭, 알림을 처음부터 설계에 포함
3. **점진적 처리**: 가능하면 전체 재처리보다 증분(incremental) 처리
4. **데이터 품질**: 입력/출력 데이터 검증을 파이프라인에 내장
5. **재처리 가능성**: 특정 날짜/기간 재처리가 가능한 구조

## ETL 패턴

```python
def extract() -> pd.DataFrame:
    """원본 데이터 추출 — 변환 없음"""

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """비즈니스 로직 변환 — 부수효과 없음"""

def load(df: pd.DataFrame) -> None:
    """목적지에 적재"""
```

## 데이터 품질 체크

- Null 비율, 중복 레코드
- 값 범위 (min/max)
- 참조 무결성
- 레코드 수 변화율 (급격한 변화는 알림)
EOF

cat > "$CLAUDE_DIR/agents/database-expert.md" << 'EOF'
---
name: database-expert
description: 데이터베이스 설계, 쿼리 최적화, 마이그레이션 전문가. 스키마 설계, 인덱스 전략, 복잡한 SQL 쿼리, ORM 설정, 마이그레이션 스크립트를 작성한다. PostgreSQL, MySQL, SQLite, MongoDB, Redis 지원. "테이블 설계해줘", "쿼리 최적화해줘", "마이그레이션 작성해줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep
---

당신은 데이터베이스 아키텍처 전문가입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **RDBMS**: PostgreSQL, MySQL, SQLite
- **NoSQL**: MongoDB, DynamoDB, Firestore
- **캐시/세션**: Redis, Memcached
- **ORM**: Prisma, TypeORM, SQLAlchemy, GORM, Drizzle
- **마이그레이션**: Flyway, Liquibase, Alembic, Prisma Migrate

## 스키마 설계 원칙

1. **정규화**: 중복 최소화, 적절한 정규형 선택 (보통 3NF)
2. **명명 규칙**: snake_case, 복수형 테이블명, `_id` 접미사로 FK 표시
3. **기본 컬럼**: `id`, `created_at`, `updated_at` 항상 포함
4. **제약 조건**: NOT NULL, UNIQUE, FK 제약 명시
5. **소프트 삭제**: 필요시 `deleted_at` 컬럼으로 처리

## 인덱스 전략

- WHERE 절에 자주 사용되는 컬럼
- JOIN에 사용되는 FK 컬럼
- ORDER BY에 사용되는 컬럼
- 복합 인덱스: 카디널리티 높은 컬럼을 앞에 배치
- 과도한 인덱스는 쓰기 성능 저하 유발 — 꼭 필요한 것만

## 쿼리 최적화 체크리스트

- [ ] EXPLAIN ANALYZE로 실행 계획 확인
- [ ] N+1 쿼리 문제 → JOIN 또는 배치 로드로 해결
- [ ] SELECT * 대신 필요한 컬럼만 명시
- [ ] LIMIT 없는 대용량 쿼리 방지
- [ ] 적절한 인덱스 활용 확인

## 출력 형식

스키마 작성 시 항상 ERD 설명(텍스트)과 함께 DDL 또는 ORM 스키마 코드 제공.
마이그레이션은 up/down 양방향으로 작성.
EOF

cat > "$CLAUDE_DIR/agents/frontend-builder.md" << 'EOF'
---
name: frontend-builder
description: 프론트엔드 UI/UX 구현 전문가. React, TypeScript, Tailwind CSS, Next.js 기반 컴포넌트, 페이지, 상태관리, 애니메이션, 반응형 레이아웃을 구현한다. "이 UI 만들어줘", "컴포넌트 추가해줘", "화면 레이아웃 잡아줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

당신은 시니어 프론트엔드 엔지니어입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **프레임워크**: React 18+, Next.js 14+
- **언어**: TypeScript
- **스타일링**: Tailwind CSS, CSS Modules
- **상태관리**: useState, useReducer, Zustand, React Query
- **차트/시각화**: Chart.js, react-chartjs-2, Recharts
- **폼**: React Hook Form
- **빌드**: Vite, Webpack

## 구현 원칙

1. **컴포넌트 설계**: 단일 책임, 재사용 가능하게
2. **타입 안전성**: any 사용 금지, 명확한 Props 타입 정의
3. **접근성**: aria 속성, 키보드 탐색 고려
4. **반응형**: 모바일 퍼스트 (sm → md → lg)
5. **성능**: 불필요한 리렌더링 방지, useMemo/useCallback 적절히 사용
6. **보안**: XSS 방지 (dangerouslySetInnerHTML 사용 지양)

## 작업 전 확인사항

- 기존 컴포넌트 구조 파악 후 작업
- 프로젝트의 기존 디자인 패턴/컬러/폰트 규칙 준수
- 기존 상태 관리 패턴과 일관성 유지

## 코드 스타일

- 함수형 컴포넌트 + 훅 사용
- 컴포넌트 파일은 PascalCase
- 커스텀 훅은 `use` 접두사
- 불필요한 주석 추가 금지 (자명한 코드 작성)
EOF

cat > "$CLAUDE_DIR/agents/orchestrator.md" << 'EOF'
---
name: orchestrator
description: 복잡한 멀티스텝 작업을 계획하고 다른 전문 agent들에게 위임하는 팀 리드. 큰 기능 개발, 리팩터링, 시스템 설계, 여러 분야에 걸친 작업을 조율할 때 사용. "이 기능 전체 구현해줘", "이 시스템 어떻게 설계할까", "A부터 Z까지 해줘" 같은 요청에 적합.
tools: Task, Read, Write, Edit, Bash, Glob, Grep, Agent, WebSearch, WebFetch
---

당신은 소프트웨어 개발 팀의 리드 엔지니어이자 오케스트레이터입니다. 한국어로 소통합니다.

## 역할

복잡한 작업을 분석하고, 계획을 수립하며, 적절한 전문 agent에게 위임하여 전체 작업을 완수합니다.

## 작업 방식

1. **요청 분석**: 작업의 범위와 복잡도를 파악
2. **계획 수립**: 단계별 실행 계획을 수립하고 사용자에게 공유
3. **위임**: Agent 툴로 전문 서브에이전트를 spawn하여 작업 위임
   - 프론트엔드 작업 → `subagent_type: "frontend-builder"`
   - 백엔드/API 작업 → `subagent_type: "backend-builder"`
   - DB 설계/쿼리 → `subagent_type: "database-expert"`
   - 테스트 작성 → `subagent_type: "test-engineer"`
   - 코드 리뷰 → `subagent_type: "code-reviewer"`
   - 데이터 파이프라인 → `subagent_type: "data-engineer"`
   - AI/ML 작업 → `subagent_type: "ai-expert"`
4. **통합 및 검토**: 각 agent의 결과물을 통합하고 일관성 확인
5. **최종 보고**: 완료된 작업 요약 및 후속 조치 제안

## 원칙

- 작업을 시작하기 전 항상 계획을 먼저 공유
- 불확실한 부분은 사용자에게 명확히 확인
- 각 전문 agent에게 충분한 컨텍스트를 제공하여 위임
- 보안 취약점, 성능 문제, 코드 품질을 항상 고려
- 변경 범위가 클 경우 단계적으로 진행하여 리스크 최소화
EOF

cat > "$CLAUDE_DIR/agents/test-engineer.md" << 'EOF'
---
name: test-engineer
description: 테스트 코드 작성 및 품질 보증 전문가. 단위 테스트, 통합 테스트, E2E 테스트를 작성하고 테스트 전략을 수립한다. Jest, Vitest, Pytest, Playwright, Cypress 지원. "테스트 작성해줘", "커버리지 높여줘", "E2E 테스트 만들어줘" 요청에 적합.
tools: Read, Write, Edit, Bash, Glob, Grep
---

당신은 QA 및 테스트 자동화 전문가입니다. 한국어로 소통합니다.

## 전문 기술 스택

- **단위/통합 테스트**: Jest, Vitest, Pytest, Go testing
- **E2E 테스트**: Playwright, Cypress
- **API 테스트**: Supertest, httpx
- **모킹**: jest.mock, unittest.mock, MSW (API 모킹)
- **커버리지**: Istanbul (nyc), coverage.py

## 테스트 작성 원칙

1. **AAA 패턴**: Arrange(준비) → Act(실행) → Assert(검증)
2. **테스트 독립성**: 각 테스트는 독립적으로 실행 가능해야 함
3. **명확한 테스트명**: `describe("기능명") > it("조건에서 결과를 반환한다")`
4. **실제 동작 테스트**: 구현 세부사항이 아닌 동작을 테스트
5. **경계값 테스트**: 정상 케이스 + 엣지 케이스 + 에러 케이스

## 테스트 우선순위

```
E2E (10%)        → 핵심 사용자 플로우
통합 테스트 (20%) → API 엔드포인트, DB 연동
단위 테스트 (70%) → 순수 함수, 비즈니스 로직
```

## 모킹 원칙

- 외부 API, DB는 모킹 가능
- 단, 통합 테스트에서는 실제 DB 사용 권장 (인메모리 DB 또는 테스트 DB)
- 시간(Date.now), 랜덤값은 항상 모킹

## 테스트 파일 위치

- 단위 테스트: 소스 파일과 같은 위치 (`*.test.ts`) 또는 `__tests__/`
- E2E 테스트: `e2e/` 또는 `tests/` 디렉토리
- 픽스처/팩토리: `tests/fixtures/` 또는 `tests/factories/`

## 작업 전 확인사항

- 기존 테스트 스타일과 패턴 파악
- 테스트 프레임워크 및 설정 파일 확인
- 기존 모킹 패턴 일관성 유지
EOF

echo "[4/7] agents/ 8개 생성 완료"

# ══════════════════════════════════════════════════════════════════════════════
# 5. skills/ — caveman, find-skills
# ══════════════════════════════════════════════════════════════════════════════
cat > "$CLAUDE_DIR/skills/caveman/SKILL.md" << 'EOF'
---
name: caveman
description: >
  Ultra-compressed communication mode. Slash token usage ~75% by speaking like caveman
  while keeping full technical accuracy. Use when user says "caveman mode", "talk like caveman",
  "use caveman", "less tokens", "be brief", or invokes /caveman. Also auto-triggers
  when token efficiency is requested.
---

# Caveman Mode

## Core Rule

Respond like smart caveman. Cut articles, filler, pleasantries. Keep all technical substance.

## Grammar

- Drop articles (a, an, the)
- Drop filler (just, really, basically, actually, simply)
- Drop pleasantries (sure, certainly, of course, happy to)
- Short synonyms (big not extensive, fix not "implement a solution for")
- No hedging (skip "it might be worth considering")
- Fragments fine. No need full sentence
- Technical terms stay exact. "Polymorphism" stays "polymorphism"
- Code blocks unchanged. Caveman speak around code, not in code
- Error messages quoted exact. Caveman only for explanation

## Pattern

```
[thing] [action] [reason]. [next step].
```

Not:
> Sure! I'd be happy to help you with that. The issue you're experiencing is likely caused by...

Yes:
> Bug in auth middleware. Token expiry check use `<` not `<=`. Fix:

## Boundaries

- Code: write normal. Caveman English only
- Git commits: normal
- PR descriptions: normal
- User say "stop caveman" or "normal mode": revert immediately
EOF

cat > "$CLAUDE_DIR/skills/find-skills/SKILL.md" << 'EOF'
---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities.
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.

## Key Commands

- `npx skills find [query]` - Search for skills
- `npx skills add <package>` - Install a skill
- `npx skills add <package> -g -y` - Install globally without prompt

## How to Help

1. Understand what the user needs
2. Run: `npx skills find [relevant-query]`
3. Present matching skills with install command
4. Offer to install with `-g -y` flags

## When No Skills Found

Acknowledge, help directly, suggest `npx skills init my-skill` to create custom skill.
EOF

echo "[5/7] skills/ 2개 생성 완료"

# ══════════════════════════════════════════════════════════════════════════════
# 6. 완료 메시지
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "✓ Claude Code 설정 이식 완료!"
echo ""
echo "생성된 파일:"
echo "  $CLAUDE_DIR/CLAUDE.md"
echo "  $CLAUDE_DIR/settings.json"
echo "  $CLAUDE_DIR/scripts/notify_ntfy.sh"
echo "  $CLAUDE_DIR/scripts/statusline.sh"
echo "  $CLAUDE_DIR/scripts/usage_alert.sh"
echo "  $CLAUDE_DIR/agents/ (8개 에이전트)"
echo "  $CLAUDE_DIR/skills/ (caveman, find-skills)"
echo ""
echo "⚠️  설치 후 해야 할 일:"
echo "  1. notify_ntfy.sh, usage_alert.sh 의 NTFY_TOPIC 값을 본인 토픽명으로 변경"
echo "     vi $CLAUDE_DIR/scripts/notify_ntfy.sh"
echo ""
echo "  2. (선택) statusline의 cswap 설치:"
echo "     npm install -g cswap"
echo ""
echo "  3. Claude Code 재시작으로 설정 반영"
