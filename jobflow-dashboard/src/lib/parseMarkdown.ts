/**
 * 복호화된 Markdown 문자열 → Job 객체 파싱 (클라이언트/서버 공용).
 * Python file_parser.py와 동일한 규칙을 따른다.
 */

import type { ChecklistItem, Job, JobTasks, Task, TaskPriority, TaskStatus } from "./types";

const SECTION_MAP: Record<string, TaskStatus> = {
  "### 🔵 Todo":        "todo",
  "### 🟡 In Progress": "in_progress",
  "### 🟢 Done":        "done",
};

const TASK_HEADER = /^- \[(?<status>[ ~x])\] (?<id>TASK-\d+) (?<title>[^#!]+?)(?:\s+(?<tags>(?:#\w+\s*)+))?(?:\s+(?<priority>!\w+))?\s*$/;
const CHECKLIST   = /^\s+- \[(?<checked>[ x])\] (?<text>.+)$/;
const META_RE     = /<!--\s*(\w+)\s*:\s*(.+?)\s*-->/g;

const STATUS_MAP: Record<string, TaskStatus> = { " ": "todo", "~": "in_progress", x: "done" };

function parseMeta(block: string): Record<string, string | null> {
  const meta: Record<string, string | null> = {};
  for (const m of block.matchAll(META_RE)) {
    const val = m[2].trim();
    meta[m[1]] = val === "~" || val === "" ? null : val;
  }
  return meta;
}

function parseTaskBlock(lines: string[]): Task | null {
  if (!lines.length) return null;
  const m = TASK_HEADER.exec(lines[0]);
  if (!m?.groups) return null;

  const { status, id, title, tags, priority } = m.groups;
  const checklist: ChecklistItem[] = [];

  for (const line of lines.slice(1)) {
    const cm = CHECKLIST.exec(line);
    if (cm?.groups) {
      checklist.push({ text: cm.groups.text, checked: cm.groups.checked === "x" });
    }
  }

  const meta = parseMeta(lines.join("\n"));

  return {
    id,
    title: title.trim(),
    status: STATUS_MAP[status] ?? "todo",
    tag:    tags?.trim().split(/\s+/)[0] ?? null,
    priority: ((priority ?? "!medium").slice(1)) as TaskPriority,
    checklist,
    started_at:   meta["started_at"] ?? null,
    updated_at:   meta["updated_at"] ?? null,
    completed_at: meta["completed_at"] ?? null,
  };
}

export function parseJobMarkdown(content: string): Job {
  const parts = content.split("---");
  if (parts.length < 3) throw new Error("frontmatter 파싱 실패");

  const fm   = parts[1];
  const body = parts.slice(2).join("---");

  // 간단한 YAML 파싱 (의존성 없이)
  const fmObj: Record<string, string> = {};
  for (const line of fm.split("\n")) {
    const idx = line.indexOf(":");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
    if (key) fmObj[key] = val;
  }

  const tasks: JobTasks = { todo: [], in_progress: [], done: [] };
  let currentSection: TaskStatus | null = null;
  let sectionLines: string[] = [];

  function flushSection() {
    if (!currentSection) return;
    // 태스크 헤더로 블록 분리
    const blocks: string[][] = [];
    let cur: string[] = [];
    for (const line of sectionLines) {
      if (TASK_HEADER.test(line)) {
        if (cur.length) blocks.push(cur);
        cur = [line];
      } else if (cur.length) {
        cur.push(line);
      }
    }
    if (cur.length) blocks.push(cur);

    for (const block of blocks) {
      const task = parseTaskBlock(block);
      if (task) tasks[currentSection!].push(task);
    }
  }

  for (const line of body.split("\n")) {
    const trimmed = line.trimEnd();
    if (trimmed in SECTION_MAP) {
      flushSection();
      currentSection = SECTION_MAP[trimmed];
      sectionLines   = [];
    } else if (currentSection) {
      sectionLines.push(trimmed);
    }
  }
  flushSection();

  return {
    job_id:     fmObj["job_id"]   ?? "",
    job_name:   fmObj["job_name"] ?? "",
    goal:       fmObj["goal"]     ?? "",
    status:     fmObj["status"]   ?? "todo",
    version:    parseInt(fmObj["version"] ?? "1", 10),
    updated_at: fmObj["updated_at"] ?? null,
    tasks,
  };
}
