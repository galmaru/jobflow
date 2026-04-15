/** 공통 타입 정의 */

export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "high" | "medium" | "low";

export interface ChecklistItem {
  text: string;
  checked: boolean;
}

export interface Task {
  id: string;
  title: string;
  status: TaskStatus;
  tag: string | null;
  priority: TaskPriority;
  checklist: ChecklistItem[];
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface JobTasks {
  todo: Task[];
  in_progress: Task[];
  done: Task[];
}

export interface Job {
  job_id: string;
  job_name: string;
  goal: string;
  status: string;
  version: number;
  updated_at: string | null;
  tasks: JobTasks;
}

export interface JobsResponse {
  jobs: Job[];
}

export interface CommitEntry {
  sha: string;
  message: string;
  date: string;
  version: number | null;
}

export interface HistoryListResponse {
  commits: CommitEntry[];
}

export interface HistoryDiffResponse {
  sha: string;
  content: string;
  parent_content: string;
}
