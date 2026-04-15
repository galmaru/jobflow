/** GitHub API 클라이언트 (서버 사이드 전용). */

const GH_API = "https://api.github.com";

function headers() {
  const token = process.env.GH_TOKEN;
  if (!token) throw new Error("GH_TOKEN 환경변수가 설정되지 않았습니다.");
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function getRepo(): string {
  const repo = process.env.GH_REPO;
  if (!repo) throw new Error("GH_REPO 환경변수가 설정되지 않았습니다.");
  return repo;
}

function getTasksPath(): string {
  return (process.env.GH_TASKS_PATH ?? "tasks").replace(/\/$/, "");
}

/** .jobflow-index.json 조회 */
export async function fetchIndex(): Promise<{ jobs: IndexEntry[] }> {
  const repo      = getRepo();
  const tasksPath = getTasksPath();
  const url       = `${GH_API}/repos/${repo}/contents/${tasksPath}/.jobflow-index.json`;

  const res = await fetch(url, { headers: headers(), cache: "no-store" });
  if (res.status === 404) return { jobs: [] };
  if (!res.ok) throw new Error(`GitHub API 오류: ${res.status} ${res.statusText}`);

  const data = await res.json();
  const content = Buffer.from(data.content, "base64").toString("utf-8");
  return JSON.parse(content);
}

export interface IndexEntry {
  file: string;
  job_id: string;
  version: number;
  status: string;
  updated_at: string | null;
}

/** 암호화된 .enc 파일 다운로드 → Buffer 반환 */
export async function fetchEncFile(filename: string): Promise<Buffer> {
  const repo      = getRepo();
  const tasksPath = getTasksPath();
  const url       = `${GH_API}/repos/${repo}/contents/${tasksPath}/${filename}`;

  const res = await fetch(url, { headers: headers(), cache: "no-store" });
  if (!res.ok) throw new Error(`파일 다운로드 실패 (${filename}): ${res.status}`);

  const data    = await res.json();
  const content = data.content as string;
  return Buffer.from(content.replace(/\n/g, ""), "base64");
}

/** Job의 커밋 히스토리 조회 */
export async function fetchCommits(jobEncFilename: string): Promise<CommitInfo[]> {
  const repo      = getRepo();
  const tasksPath = getTasksPath();
  const path      = `${tasksPath}/${jobEncFilename}`;
  const url       = `${GH_API}/repos/${repo}/commits?path=${encodeURIComponent(path)}&per_page=30`;

  const res = await fetch(url, { headers: headers(), cache: "no-store" });
  if (!res.ok) return [];

  const data = await res.json();
  return (data as RawCommit[]).map((c) => ({
    sha:     c.sha,
    message: c.commit.message,
    date:    c.commit.author?.date ?? "",
  }));
}

export interface CommitInfo {
  sha: string;
  message: string;
  date: string;
}

interface RawCommit {
  sha: string;
  commit: { message: string; author?: { date?: string } };
}

/** 특정 커밋의 파일 내용 가져오기 (ref=sha) */
export async function fetchEncFileAtSha(filename: string, sha: string): Promise<Buffer | null> {
  const repo      = getRepo();
  const tasksPath = getTasksPath();
  const url       = `${GH_API}/repos/${repo}/contents/${tasksPath}/${filename}?ref=${sha}`;

  const res = await fetch(url, { headers: headers(), cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) return null;

  const data    = await res.json();
  const content = data.content as string;
  return Buffer.from(content.replace(/\n/g, ""), "base64");
}

/** 커밋의 parent SHA 조회 */
export async function fetchParentSha(sha: string): Promise<string | null> {
  const repo = getRepo();
  const url  = `${GH_API}/repos/${repo}/commits/${sha}`;

  const res = await fetch(url, { headers: headers(), cache: "no-store" });
  if (!res.ok) return null;

  const data = await res.json();
  return data.parents?.[0]?.sha ?? null;
}
