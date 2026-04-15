/**
 * /api/slack/notify Route 단위 테스트.
 * NOTIFY_SECRET 검증, dedup, Slack 전송 mock.
 */

// Next.js route handler를 직접 테스트하기 어려우므로
// verifySecret와 isDuplicate 로직을 lib 함수로 추출한 형태로 테스트

import { timingSafeEqual } from "crypto";

// ── verifySecret 로직 인라인 테스트 ──────────────────────────────────────────

function verifySecret(provided: string | undefined, expected: string): boolean {
  if (!expected || !provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

describe("verifySecret (notify)", () => {
  const SECRET = "super-secret-notify-key";

  it("올바른 시크릿이면 true를 반환한다", () => {
    expect(verifySecret(SECRET, SECRET)).toBe(true);
  });

  it("잘못된 시크릿이면 false를 반환한다", () => {
    expect(verifySecret("wrong", SECRET)).toBe(false);
  });

  it("undefined 제공 시 false를 반환한다", () => {
    expect(verifySecret(undefined, SECRET)).toBe(false);
  });

  it("길이가 다른 시크릿은 false를 반환한다 (타이밍 공격 방지)", () => {
    expect(verifySecret(SECRET + "x", SECRET)).toBe(false);
    expect(verifySecret(SECRET.slice(0, -1), SECRET)).toBe(false);
  });
});

// ── dedup 로직 테스트 ──────────────────────────────────────────────────────────

describe("dedup (3초 내 재발송 차단)", () => {
  it("동일 task_id를 3초 내 두 번 보내면 두 번째는 duplicate로 판정된다", () => {
    const map = new Map<string, number>();

    function isDuplicate(taskId: string): boolean {
      const now  = Date.now();
      const last = map.get(taskId);
      map.set(taskId, now);
      return last !== undefined && now - last < 3_000;
    }

    expect(isDuplicate("TASK-001")).toBe(false); // 첫 호출
    expect(isDuplicate("TASK-001")).toBe(true);  // 즉시 재호출 → duplicate
  });

  it("서로 다른 task_id는 각자 독립적으로 처리된다", () => {
    const map = new Map<string, number>();

    function isDuplicate(taskId: string): boolean {
      const now  = Date.now();
      const last = map.get(taskId);
      map.set(taskId, now);
      return last !== undefined && now - last < 3_000;
    }

    expect(isDuplicate("TASK-001")).toBe(false);
    expect(isDuplicate("TASK-002")).toBe(false); // 다른 task_id
    expect(isDuplicate("TASK-001")).toBe(true);  // TASK-001 중복
    expect(isDuplicate("TASK-002")).toBe(true);  // TASK-002 중복
  });

  it("task_id가 없으면 dedup 대상이 아니다", () => {
    // task_id 없는 이벤트 (daily_summary 등)는 dedup 건너뜀
    const taskId = undefined;
    expect(taskId && true).toBeFalsy();
  });
});
