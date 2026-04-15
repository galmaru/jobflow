"use client";

import { useState } from "react";
import type { Job, Task, TaskStatus } from "@/lib/types";
import { TaskCard } from "./TaskCard";
import { TaskSlideOver } from "./TaskSlideOver";
import { MobileTabFilter } from "./MobileTabFilter";

const COLUMNS: { status: TaskStatus; label: string; icon: string }[] = [
  { status: "todo",        label: "Todo",        icon: "🔵" },
  { status: "in_progress", label: "In Progress", icon: "🟡" },
  { status: "done",        label: "Done",        icon: "🟢" },
];

interface KanbanBoardProps {
  job: Job;
}

export function KanbanBoard({ job }: KanbanBoardProps) {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [mobileTab,    setMobileTab]    = useState<TaskStatus>("todo");

  const counts: Record<TaskStatus, number> = {
    todo:        job.tasks.todo.length,
    in_progress: job.tasks.in_progress.length,
    done:        job.tasks.done.length,
  };

  return (
    <>
      {/* 모바일: 탭 필터 */}
      <div className="md:hidden">
        <MobileTabFilter active={mobileTab} onChange={setMobileTab} counts={counts} />
        <div className="p-4 space-y-3">
          {job.tasks[mobileTab].map((task) => (
            <TaskCard key={task.id} task={task} onClick={setSelectedTask} />
          ))}
          {job.tasks[mobileTab].length === 0 && (
            <p className="text-center text-sm text-gray-400 py-8">태스크 없음</p>
          )}
        </div>
      </div>

      {/* PC: 3컬럼 칸반 */}
      <div className="hidden md:grid md:grid-cols-3 md:gap-4">
        {COLUMNS.map(({ status, label, icon }) => (
          <div key={status} className="bg-gray-50 rounded-xl p-3">
            {/* 컬럼 헤더 */}
            <div className="flex items-center gap-2 mb-3">
              <span>{icon}</span>
              <h3 className="text-sm font-semibold text-gray-700">{label}</h3>
              <span className="ml-auto text-xs bg-white border rounded-full px-2 py-0.5 text-gray-500">
                {counts[status]}
              </span>
            </div>

            {/* 태스크 카드 목록 */}
            <div className="space-y-2">
              {job.tasks[status].map((task) => (
                <TaskCard key={task.id} task={task} onClick={setSelectedTask} />
              ))}
              {job.tasks[status].length === 0 && (
                <p className="text-center text-xs text-gray-300 py-4">비어 있음</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 슬라이드 상세 패널 */}
      <TaskSlideOver task={selectedTask} onClose={() => setSelectedTask(null)} />
    </>
  );
}
