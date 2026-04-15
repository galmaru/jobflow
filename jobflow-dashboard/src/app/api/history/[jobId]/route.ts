import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { decrypt } from "@/lib/decrypt";
import {
  fetchCommits,
  fetchEncFileAtSha,
  fetchIndex,
  fetchParentSha,
} from "@/lib/github";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params;
  const sha       = req.nextUrl.searchParams.get("sha");
  const keyB64    = process.env.JOBFLOW_KEY_B64;

  if (!keyB64) {
    return NextResponse.json({ error: "JOBFLOW_KEY_B64 환경변수 미설정" }, { status: 500 });
  }

  try {
    // jobId → enc 파일명 매핑
    const index      = await fetchIndex();
    const entry      = index.jobs.find((j) => j.job_id === jobId);
    const encFilename = entry?.file ?? `todo-${jobId}.md.enc`;

    if (!sha) {
      // sha 미지정: 커밋 목록 반환
      const commits = await fetchCommits(encFilename);
      const list = commits.map((c) => ({
        sha:     c.sha,
        message: c.message,
        date:    c.date,
        version: entry?.version ?? null,
      }));
      return NextResponse.json({ commits: list });
    }

    // sha 지정: 해당 커밋 복호화 + 이전 커밋 복호화 → diff 원본 반환
    const encData = await fetchEncFileAtSha(encFilename, sha);
    if (!encData) {
      return NextResponse.json({ error: "파일을 찾을 수 없습니다." }, { status: 404 });
    }
    const content = decrypt(encData, keyB64);

    const parentSha     = await fetchParentSha(sha);
    let parent_content  = "";
    if (parentSha) {
      const parentEnc = await fetchEncFileAtSha(encFilename, parentSha);
      if (parentEnc) {
        try {
          parent_content = decrypt(parentEnc, keyB64);
        } catch {
          parent_content = "";
        }
      }
    }

    return NextResponse.json({ sha, content, parent_content });
  } catch (e) {
    const message = e instanceof Error ? e.message : "알 수 없는 오류";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
