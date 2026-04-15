import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifyBearer } from "@/lib/auth";
import { decrypt } from "@/lib/decrypt";
import { fetchEncFile, fetchIndex } from "@/lib/github";
import { parseJobMarkdown } from "@/lib/parseMarkdown";
import type { Job } from "@/lib/types";

export async function GET(req: NextRequest) {
  if (!verifyBearer(req.headers.get("authorization"))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const keyB64 = process.env.JOBFLOW_KEY_B64;
  if (!keyB64) {
    return NextResponse.json({ error: "JOBFLOW_KEY_B64 환경변수 미설정" }, { status: 500 });
  }

  try {
    const index = await fetchIndex();
    if (!index.jobs.length) {
      return NextResponse.json({ jobs: [] });
    }

    // 병렬 다운로드 + 복호화
    const results = await Promise.allSettled(
      index.jobs.map(async (entry) => {
        const encData = await fetchEncFile(entry.file);
        const md      = decrypt(encData, keyB64);
        return parseJobMarkdown(md);
      })
    );

    const jobs: Job[] = [];
    for (const r of results) {
      if (r.status === "fulfilled") {
        jobs.push(r.value);
      }
      // fulfilled가 아닌 경우(rejected)는 스킵 — 단일 파일 오류가 전체를 막지 않도록
    }

    return NextResponse.json({ jobs });
  } catch (e) {
    const message = e instanceof Error ? e.message : "알 수 없는 오류";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
