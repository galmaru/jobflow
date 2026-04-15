import { NextRequest, NextResponse } from "next/server";
import { timingSafeEqual } from "crypto";
import { buildSlackMessage, sendSlackMessage } from "@/lib/slack";
import type { DailySummary } from "@/lib/slack";
import { decrypt } from "@/lib/decrypt";
import { fetchEncFile, fetchIndex } from "@/lib/github";
import { parseJobMarkdown } from "@/lib/parseMarkdown";
import type { Task } from "@/lib/types";

/** Vercel Cron 인증 (CRON_SECRET). */
function verifyCron(header: string | null): boolean {
  const expected = process.env.CRON_SECRET;
  if (!expected || !header) return false;
  const provided = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

/** 오늘(KST 기준) 완료된 태스크 여부 판별 */
function isCompletedToday(task: Task): boolean {
  if (!task.completed_at) return false;
  const completedDate = new Date(task.completed_at).toLocaleDateString("ko-KR", {
    timeZone: "Asia/Seoul",
  });
  const today = new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" });
  return completedDate === today;
}

async function buildDailySummary(): Promise<DailySummary & { job_id: string; job_name: string }> {
  const keyB64 = process.env.JOBFLOW_KEY_B64;
  if (!keyB64) throw new Error("JOBFLOW_KEY_B64 미설정");

  const index = await fetchIndex();
  let total = 0, done_today = 0, in_progress = 0, todo = 0;
  const completed_tasks: string[] = [];
  let job_id = "", job_name = "";

  for (const entry of index.jobs) {
    if (entry.status === "archived") continue;
    try {
      const enc = await fetchEncFile(entry.file);
      const md  = decrypt(enc, keyB64);
      const job = parseJobMarkdown(md);

      if (!job_id) { job_id = job.job_id; job_name = job.job_name; }

      const allTasks = [
        ...job.tasks.todo,
        ...job.tasks.in_progress,
        ...job.tasks.done,
      ];
      total       += allTasks.length;
      in_progress += job.tasks.in_progress.length;
      todo        += job.tasks.todo.length;

      for (const task of job.tasks.done) {
        if (isCompletedToday(task)) {
          done_today++;
          completed_tasks.push(`${task.id} ${task.title}`);
        }
      }
    } catch {
      // 단일 파일 실패는 무시
    }
  }

  return { total, done_today, in_progress, todo, completed_tasks, job_id, job_name };
}

export async function GET(req: NextRequest) {
  if (!verifyCron(req.headers.get("authorization"))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let summary;
  try {
    summary = await buildDailySummary();
  } catch (e) {
    const msg = e instanceof Error ? e.message : "요약 생성 실패";
    return NextResponse.json({ error: msg }, { status: 500 });
  }

  // 활동 없는 날 노이즈 방지: 완료 0 + 진행중 0이면 스킵
  if (summary.done_today === 0 && summary.in_progress === 0) {
    return NextResponse.json({ ok: true, skipped: "no_activity" });
  }

  const message = buildSlackMessage({
    event:     "daily_summary",
    job_id:    summary.job_id,
    job_name:  summary.job_name,
    summary,
    timestamp: new Date().toISOString(),
    secret:    "",  // daily_summary는 Vercel 내부 호출 — secret 불필요
  });

  try {
    await sendSlackMessage(message);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Slack 전송 실패";
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  return NextResponse.json({ ok: true, done_today: summary.done_today });
}
