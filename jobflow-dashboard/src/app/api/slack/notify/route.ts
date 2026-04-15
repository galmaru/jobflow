import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";
import { buildSlackMessage, sendSlackMessage } from "@/lib/slack";
import type { NotifyPayload } from "@/lib/slack";

/** NOTIFY_SECRET 검증 (타이밍 공격 방지). */
function verifySecret(provided: string | undefined): boolean {
  const expected = process.env.NOTIFY_SECRET;
  if (!expected || !provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * 동일 task_id 3초 내 재발송 차단 (in-memory dedup).
 * Vercel Function은 인스턴스가 재사용될 수 있으므로 단순 Map으로 충분.
 */
const recentNotifications = new Map<string, number>();

function isDuplicate(taskId: string): boolean {
  const now  = Date.now();
  const last = recentNotifications.get(taskId);
  recentNotifications.set(taskId, now);
  // 3초 후 자동 삭제하여 Map 누수 방지
  setTimeout(() => recentNotifications.delete(taskId), 3_000);
  return last !== undefined && now - last < 3_000;
}

export async function POST(req: NextRequest) {
  let payload: NotifyPayload;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // 1. 시크릿 검증
  if (!verifySecret(payload.secret)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. 중복 발송 방지
  if (payload.task_id && isDuplicate(payload.task_id)) {
    return NextResponse.json({ ok: true, skipped: "duplicate" });
  }

  // 3. Block Kit 메시지 생성
  const message = buildSlackMessage(payload);

  // 4. Slack Webhook 전송
  try {
    await sendSlackMessage(message);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "알 수 없는 오류";
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  return NextResponse.json({ ok: true });
}
