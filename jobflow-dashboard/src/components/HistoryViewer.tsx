"use client";

import { useEffect, useRef, useState } from "react";
import type { CommitEntry } from "@/lib/types";

function getToken() {
  return typeof localStorage !== "undefined" ? localStorage.getItem("jobflow_token") : null;
}

async function fetchHistory(jobId: string, sha?: string) {
  const url = sha
    ? `/api/history/${jobId}?sha=${sha}`
    : `/api/history/${jobId}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${getToken() ?? ""}` },
  });
  if (!res.ok) throw new Error(`히스토리 로드 실패: ${res.status}`);
  return res.json();
}

interface HistoryViewerProps {
  jobId: string;
}

export default function HistoryViewer({ jobId }: HistoryViewerProps) {
  const [commits,    setCommits]    = useState<CommitEntry[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [diffHtml,   setDiffHtml]   = useState<string>("");
  const [activeSha,  setActiveSha]  = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHistory(jobId)
      .then((data) => setCommits(data.commits ?? []))
      .catch(() => setCommits([]))
      .finally(() => setLoading(false));
  }, [jobId]);

  async function handleCommitClick(sha: string) {
    if (activeSha === sha) return;
    setActiveSha(sha);
    setDiffLoading(true);
    setDiffHtml("");

    try {
      const data = await fetchHistory(jobId, sha);

      // diff2html은 동적 import (메인 번들에서 분리)
      const { html: Diff2Html } = await import("diff2html");
      const { createTwoFilesPatch } = await import("diff");

      const patch   = createTwoFilesPatch("이전", "현재", data.parent_content ?? "", data.content ?? "");
      const html    = Diff2Html(patch, { drawFileList: false, matching: "lines", outputFormat: "side-by-side" });
      setDiffHtml(html);
    } catch {
      setDiffHtml("<p class='text-red-500'>diff 렌더링 실패</p>");
    } finally {
      setDiffLoading(false);
    }
  }

  if (loading) return <p className="text-gray-400 py-8 text-center">히스토리 로딩 중…</p>;
  if (!commits.length) return <p className="text-gray-400 py-8 text-center">커밋 기록이 없습니다.</p>;

  return (
    <div className="flex gap-4">
      {/* 커밋 목록 */}
      <aside className="w-80 flex-shrink-0 space-y-1">
        {commits.map((c) => (
          <button
            key={c.sha}
            onClick={() => handleCommitClick(c.sha)}
            className={[
              "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
              activeSha === c.sha
                ? "bg-blue-50 border border-blue-300 text-blue-800"
                : "hover:bg-gray-100 text-gray-700",
            ].join(" ")}
          >
            <p className="font-medium truncate">{c.message}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {new Date(c.date).toLocaleString("ko-KR")}
            </p>
          </button>
        ))}
      </aside>

      {/* diff 뷰 */}
      <div className="flex-1 min-w-0">
        {diffLoading && <p className="text-gray-400 text-sm">diff 로딩 중…</p>}
        {!diffLoading && !diffHtml && (
          <p className="text-gray-400 text-sm">커밋을 선택하면 변경사항이 표시됩니다.</p>
        )}
        {diffHtml && (
          <>
            <link
              rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/diff2html/bundles/css/diff2html.min.css"
            />
            <div
              ref={containerRef}
              dangerouslySetInnerHTML={{ __html: diffHtml }}
              className="overflow-x-auto text-sm"
            />
          </>
        )}
      </div>
    </div>
  );
}
