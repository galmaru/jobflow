/**
 * buildSlackMessage 단위 테스트 — 이벤트별 Block Kit 형식 검증.
 */
import { buildSlackMessage } from "../lib/slack";
import type { NotifyPayload } from "../lib/slack";

const BASE: Omit<NotifyPayload, "event"> = {
  job_id:    "job-20260414-001",
  job_name:  "KBO 스케줄 웹앱",
  task_id:   "TASK-002",
  task_title: "UI 컴포넌트 설계",
  timestamp: "2026-04-14T10:30:00+09:00",
  secret:    "test-secret",
};

describe("buildSlackMessage", () => {
  describe("task_done", () => {
    it("header에 '태스크 완료' 텍스트가 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "task_done" }) as any;
      const header = msg.blocks.find((b: any) => b.type === "header");
      expect(header?.text.text).toMatch(/완료/);
    });

    it("fields에 job_name과 task 정보가 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "task_done" }) as any;
      const section = msg.blocks.find((b: any) => b.type === "section");
      const text = JSON.stringify(section?.fields);
      expect(text).toContain("KBO 스케줄 웹앱");
      expect(text).toContain("TASK-002");
    });
  });

  describe("stage_changed", () => {
    it("header에 '단계 변경' 텍스트가 포함된다", () => {
      const msg = buildSlackMessage({
        ...BASE,
        event:      "stage_changed",
        from_stage: "todo",
        to_stage:   "in_progress",
      }) as any;
      const header = msg.blocks.find((b: any) => b.type === "header");
      expect(header?.text.text).toMatch(/단계/);
    });

    it("from_stage와 to_stage 아이콘이 포함된다", () => {
      const msg = buildSlackMessage({
        ...BASE,
        event:      "stage_changed",
        from_stage: "todo",
        to_stage:   "in_progress",
      }) as any;
      const text = JSON.stringify(msg.blocks);
      expect(text).toContain("🔵");
      expect(text).toContain("🟡");
    });
  });

  describe("task_added", () => {
    it("header에 '새 태스크 추가' 텍스트가 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "task_added" }) as any;
      const header = msg.blocks.find((b: any) => b.type === "header");
      expect(header?.text.text).toMatch(/태스크 추가/);
    });

    it("task_id와 task_title이 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "task_added" }) as any;
      const text = JSON.stringify(msg.blocks);
      expect(text).toContain("TASK-002");
      expect(text).toContain("UI 컴포넌트 설계");
    });
  });

  describe("daily_summary", () => {
    const summary = {
      total:            10,
      done_today:       3,
      in_progress:      2,
      todo:             5,
      completed_tasks:  ["TASK-001 설계", "TASK-002 구현"],
    };

    it("header에 '일일 진행 요약' 텍스트가 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "daily_summary", summary }) as any;
      const header = msg.blocks.find((b: any) => b.type === "header");
      expect(header?.text.text).toMatch(/요약/);
    });

    it("완료/진행중/Todo 수가 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "daily_summary", summary }) as any;
      const text = JSON.stringify(msg.blocks);
      expect(text).toContain("3");
      expect(text).toContain("2");
      expect(text).toContain("5");
    });

    it("completed_tasks 목록이 포함된다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "daily_summary", summary }) as any;
      const text = JSON.stringify(msg.blocks);
      expect(text).toContain("TASK-001 설계");
      expect(text).toContain("TASK-002 구현");
    });

    it("completed_tasks가 비어있으면 '없음'이 표시된다", () => {
      const msg = buildSlackMessage({
        ...BASE,
        event:   "daily_summary",
        summary: { ...summary, completed_tasks: [] },
      }) as any;
      const text = JSON.stringify(msg.blocks);
      expect(text).toContain("없음");
    });
  });

  describe("알 수 없는 이벤트", () => {
    it("text 필드가 있는 기본 메시지를 반환한다", () => {
      const msg = buildSlackMessage({ ...BASE, event: "unknown_event" as any }) as any;
      expect(msg.text).toBeDefined();
    });
  });
});
