"use client";

import type { Task } from "@/lib/types";

const PRIORITY_COLOR: Record<string, string> = {
  high:   "text-red-600",
  medium: "text-yellow-600",
  low:    "text-gray-400",
};

const STATUS_DOT: Record<string, string> = {
  todo:        "bg-blue-400",
  in_progress: "bg-yellow-400",
  done:        "bg-green-400",
};

function elapsedLabel(isoStr: string | null): string {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const h    = Math.floor(diff / 3_600_000);
  const d    = Math.floor(h / 24);
  if (d > 0) return `${d}일`;
  if (h > 0) return `${h}시간`;
  return "방금";
}

interface TaskCardProps {
  task:    Task;
  onClick: (task: Task) => void;
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const dot          = STATUS_DOT[task.status] ?? "bg-gray-300";
  const priorityText = PRIORITY_COLOR[task.priority] ?? "";

  return (
    <button
      onClick={() => onClick(task)}
      className="w-full text-left bg-white rounded-lg border border-gray-200 p-3 shadow-sm hover:shadow-md hover:border-gray-300 transition-all"
    >
      {/* 헤더 */}
      <div className="flex items-center gap-2 mb-1">
        <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
        <span className="text-xs font-mono text-gray-500">{task.id}</span>
        {task.tag && (
          <span className="text-xs bg-gray-100 rounded px-1">{task.tag}</span>
        )}
      </div>

      {/* 제목 */}
      <p className="text-sm font-medium text-gray-800 line-clamp-2">{task.title}</p>

      {/* 하단 메타 */}
      <div className="flex items-center gap-2 mt-2">
        <span className={`text-xs font-medium ${priorityText}`}>!{task.priority}</span>
        {task.status === "in_progress" && task.started_at && (
          <span className="text-xs text-gray-400 ml-auto">
            started {elapsedLabel(task.started_at)} ago
          </span>
        )}
        {task.status === "done" && (
          <span className="text-xs text-green-600 ml-auto">✓ 완료</span>
        )}
        {task.checklist.length > 0 && (
          <span className="text-xs text-gray-400 ml-auto">
            ☑ {task.checklist.filter((c) => c.checked).length}/{task.checklist.length}
          </span>
        )}
      </div>
    </button>
  );
}
