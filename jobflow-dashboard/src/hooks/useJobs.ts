"use client";

import useSWR from "swr";
import type { JobsResponse } from "@/lib/types";

function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem("jobflow_token");
}

const fetcher = (url: string): Promise<JobsResponse> =>
  fetch(url, {
    headers: { Authorization: `Bearer ${getToken() ?? ""}` },
  }).then((r) => {
    if (r.status === 401) {
      localStorage.removeItem("jobflow_token");
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!r.ok) throw new Error(`API 오류: ${r.status}`);
    return r.json();
  });

export function useJobs() {
  return useSWR<JobsResponse>("/api/jobs", fetcher, {
    revalidateOnFocus:   true,
    refreshInterval:     30_000,
    shouldRetryOnError:  false,
  });
}
