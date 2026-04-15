"use client";

import { useEffect } from "react";
import type { Task } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  todo:        "🔵 Todo",
  in_progress: "🟡 In Progress",
  done:        "🟢 Done",
};

interface TaskSlideOverProps {
  task:    Task | null;
  onClose: () => void;
}

export function TaskSlideOver({ task, onClose }: TaskSlideOverProps) {
  // ESC 키로 닫기
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!task) return null;

  return (
    <>
      {/* 백드롭 */}
      <div
        className="fixed inset-0 bg-black/30 z-40 md:hidden"
        onClick={onClose}
        aria-hidden
      />

      {/* 슬라이드 패널 */}
      <aside
        role="dialog"
        aria-label={`태스크 상세: ${task.id}`}
        className="fixed right-0 top-0 h-full w-full max-w-sm bg-white shadow-2xl z-50 overflow-y-auto flex flex-col"
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <span className="font-mono text-sm text-gray-500">{task.id}</span>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-1 rounded hover:bg-gray-100 text-gray-500"
          >
            ✕
          </button>
        </div>

        {/* 본문 */}
        <div className="flex-1 px-5 py-4 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">{task.title}</h2>

          <div className="flex flex-wrap gap-2 text-sm">
            <span className="px-2 py-0.5 rounded-full bg-gray-100">
              {STATUS_LABEL[task.status] ?? task.status}
            </span>
            {task.tag && (
              <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
                {task.tag}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-orange-50 text-orange-700">
              !{task.priority}
            </span>
          </div>

          {/* 체크리스트 */}
          {task.checklist.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                체크리스트
              </h3>
              <ul className="space-y-1">
                {task.checklist.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className={item.checked ? "text-green-500" : "text-gray-300"}>
                      {item.checked ? "☑" : "☐"}
                    </span>
                    <span className={item.checked ? "line-through text-gray-400" : ""}>
                      {item.text}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 시간 메타 */}
          <section className="text-xs text-gray-400 space-y-1 border-t pt-3">
            {task.started_at && (
              <p>시작: {new Date(task.started_at).toLocaleString("ko-KR")}</p>
            )}
            {task.updated_at && (
              <p>업데이트: {new Date(task.updated_at).toLocaleString("ko-KR")}</p>
            )}
            {task.completed_at && (
              <p>완료: {new Date(task.completed_at).toLocaleString("ko-KR")}</p>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
