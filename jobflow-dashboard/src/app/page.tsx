"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useJobs } from "@/hooks/useJobs";
import { KanbanBoard } from "@/components/KanbanBoard";
import { JobSelector } from "@/components/JobSelector";
import type { Job } from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const { data, error, isLoading, mutate } = useJobs();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // 미인증 → 로그인 리다이렉트
  useEffect(() => {
    if (typeof localStorage !== "undefined" && !localStorage.getItem("jobflow_token")) {
      router.push("/login");
    }
  }, [router]);

  const jobs   = data?.jobs ?? [];
  const selJob = selectedJobId
    ? jobs.find((j: Job) => j.job_id === selectedJobId) ?? null
    : jobs[0] ?? null;

  return (
    <div className="min-h-screen flex flex-col">
      {/* 상단 헤더 */}
      <header className="bg-white border-b px-4 py-3 flex items-center gap-3">
        <h1 className="text-base font-bold text-gray-800">JobFlow</h1>

        {!isLoading && jobs.length > 0 && (
          <JobSelector
            jobs={jobs}
            selectedJobId={selectedJobId}
            onChange={setSelectedJobId}
          />
        )}

        <div className="ml-auto flex items-center gap-2">
          {selJob && (
            <Link
              href={`/jobs/${selJob.job_id}/history`}
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              히스토리
            </Link>
          )}
          <button
            onClick={() => mutate()}
            aria-label="새로고침"
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500"
          >
            🔄
          </button>
        </div>
      </header>

      {/* 메인 */}
      <main className="flex-1 p-4 md:p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <p className="text-gray-400">로딩 중…</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            데이터 로드 실패: {error.message}
          </div>
        )}

        {!isLoading && !error && jobs.length === 0 && (
          <div className="text-center py-20 text-gray-400">
            <p className="text-2xl mb-2">📋</p>
            <p>등록된 Job이 없습니다.</p>
            <p className="text-sm mt-1">MCP 서버에서 <code>job_new</code>를 호출하세요.</p>
          </div>
        )}

        {selJob && (
          <section>
            {/* Job 메타 */}
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-gray-800">{selJob.job_name}</h2>
              <p className="text-sm text-gray-500">{selJob.goal}</p>
            </div>
            <KanbanBoard job={selJob} />
          </section>
        )}
      </main>
    </div>
  );
}
