"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { Job } from "@/lib/types";

function getToken() {
  return typeof localStorage !== "undefined" ? localStorage.getItem("jobflow_token") : null;
}

export default function JobDetailPage({ params }: { params: Promise<{ jobId: string }> }) {
  const router = useRouter();
  const [job,     setJob]     = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");
  const [jobId,   setJobId]   = useState<string>("");

  useEffect(() => {
    params.then((p) => setJobId(p.jobId));
  }, [params]);

  useEffect(() => {
    if (!jobId) return;
    const token = getToken();
    if (!token) { router.push("/login"); return; }

    fetch("/api/jobs", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (r.status === 401) { router.push("/login"); throw new Error("Unauthorized"); }
        return r.json();
      })
      .then((data) => {
        const found = data.jobs?.find((j: Job) => j.job_id === jobId);
        if (!found) setError("Job을 찾을 수 없습니다.");
        else setJob(found);
      })
      .catch((e) => { if (e.message !== "Unauthorized") setError(e.message); })
      .finally(() => setLoading(false));
  }, [jobId, router]);

  if (loading) return <p className="p-8 text-gray-400 text-center">로딩 중…</p>;
  if (error)   return <p className="p-8 text-red-600 text-center">{error}</p>;
  if (!job)    return null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b px-4 py-3 flex items-center gap-3">
        <Link href="/" className="text-gray-500 hover:text-gray-700 text-sm">← 대시보드</Link>
        <h1 className="text-base font-bold text-gray-800">{job.job_name}</h1>
        <Link
          href={`/jobs/${jobId}/history`}
          className="ml-auto text-xs text-gray-500 hover:text-gray-700 underline"
        >
          히스토리
        </Link>
      </header>
      <main className="flex-1 p-4 md:p-6">
        <p className="text-sm text-gray-500 mb-4">{job.goal}</p>
        <KanbanBoard job={job} />
      </main>
    </div>
  );
}
