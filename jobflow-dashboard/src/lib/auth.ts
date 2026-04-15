/** Bearer Token 검증 (서버 사이드 전용). timingSafeEqual 사용으로 타이밍 공격 방지. */
import { timingSafeEqual } from "crypto";

export function verifyBearer(authHeader: string | null): boolean {
  const expected = process.env.DASHBOARD_TOKEN;
  if (!expected || !authHeader?.startsWith("Bearer ")) return false;

  const provided = authHeader.slice("Bearer ".length);
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);

  // 길이가 다르면 즉시 false (timingSafeEqual은 동일 길이 요구)
  return a.length === b.length && timingSafeEqual(a, b);
}
