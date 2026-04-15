"use client";

import type { Job } from "@/lib/types";

interface JobSelectorProps {
  jobs:          Job[];
  selectedJobId: string | null;
  onChange:      (jobId: string | null) => void;
}

export function JobSelector({ jobs, selectedJobId, onChange }: JobSelectorProps) {
  return (
    <select
      value={selectedJobId ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
      aria-label="Job 선택"
    >
      <option value="">전체 Job</option>
      {jobs.map((job) => (
        <option key={job.job_id} value={job.job_id}>
          {job.job_name}
        </option>
      ))}
    </select>
  );
}
