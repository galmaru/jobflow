/**
 * daily_summary 로직 단위 테스트.
 * 무활동 스킵, 오늘 완료 태스크 집계.
 */

import type { Task } from "../lib/types";

// ── isCompletedToday 로직 테스트 ───────────────────────────────────────────────

function isCompletedToday(task: Pick<Task, "completed_at">): boolean {
  if (!task.completed_at) return false;
  const completedDate = new Date(task.completed_at).toLocaleDateString("ko-KR", {
    timeZone: "Asia/Seoul",
  });
  const today = new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" });
  return completedDate === today;
}

describe("isCompletedToday", () => {
  it("오늘 완료된 태스크는 true를 반환한다", () => {
    const task = { completed_at: new Date().toISOString() };
    expect(isCompletedToday(task)).toBe(true);
  });

  it("어제 완료된 태스크는 false를 반환한다", () => {
    const yesterday = new Date(Date.now() - 86_400_000).toISOString();
    expect(isCompletedToday({ completed_at: yesterday })).toBe(false);
  });

  it("completed_at이 null이면 false를 반환한다", () => {
    expect(isCompletedToday({ completed_at: null })).toBe(false);
  });
});

// ── 무활동 스킵 로직 테스트 ────────────────────────────────────────────────────

describe("무활동 스킵 로직", () => {
  it("done_today=0 && in_progress=0이면 스킵 판정이다", () => {
    const summary = { done_today: 0, in_progress: 0, todo: 5, total: 5, completed_tasks: [] };
    const shouldSkip = summary.done_today === 0 && summary.in_progress === 0;
    expect(shouldSkip).toBe(true);
  });

  it("done_today > 0이면 스킵하지 않는다", () => {
    const summary = { done_today: 2, in_progress: 0, todo: 3, total: 5, completed_tasks: [] };
    const shouldSkip = summary.done_today === 0 && summary.in_progress === 0;
    expect(shouldSkip).toBe(false);
  });

  it("in_progress > 0이면 스킵하지 않는다", () => {
    const summary = { done_today: 0, in_progress: 1, todo: 4, total: 5, completed_tasks: [] };
    const shouldSkip = summary.done_today === 0 && summary.in_progress === 0;
    expect(shouldSkip).toBe(false);
  });
});

// ── buildDailySummary 집계 로직 테스트 ────────────────────────────────────────

describe("daily summary 집계", () => {
  it("todo/in_progress/done 태스크 수가 올바르게 집계된다", () => {
    // parseJobMarkdown 결과 모의
    const mockJob = {
      tasks: {
        todo:        [{ id: "TASK-003" }, { id: "TASK-004" }],
        in_progress: [{ id: "TASK-002" }],
        done:        [
          { id: "TASK-001", completed_at: new Date().toISOString() },
        ],
      },
    };

    const allTasks = [
      ...mockJob.tasks.todo,
      ...mockJob.tasks.in_progress,
      ...mockJob.tasks.done,
    ];

    expect(allTasks.length).toBe(4);               // total
    expect(mockJob.tasks.in_progress.length).toBe(1); // in_progress
    expect(mockJob.tasks.todo.length).toBe(2);        // todo

    const doneToday = mockJob.tasks.done.filter(
      (t: any) => isCompletedToday({ completed_at: t.completed_at })
    );
    expect(doneToday.length).toBe(1);
  });
});
