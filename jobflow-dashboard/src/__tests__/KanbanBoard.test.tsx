/**
 * KanbanBoard 컴포넌트 렌더링 테스트.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "../components/KanbanBoard";
import type { Job, Task } from "../lib/types";

const makeTask = (overrides: Partial<Task> = {}): Task => ({
  id:           "TASK-001",
  title:        "테스트 태스크",
  status:       "todo",
  tag:          null,
  priority:     "medium",
  checklist:    [],
  started_at:   null,
  updated_at:   null,
  completed_at: null,
  ...overrides,
});

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  job_id:     "job-20260414-001",
  job_name:   "테스트 Job",
  goal:       "테스트 목표",
  status:     "in_progress",
  version:    1,
  updated_at: null,
  tasks: {
    todo:        [],
    in_progress: [],
    done:        [],
  },
  ...overrides,
});

describe("KanbanBoard", () => {
  it("빈 컬럼이 있어도 렌더링된다", () => {
    const job = makeJob();
    render(<KanbanBoard job={job} />);
    // PC 칸반 — 3컬럼 헤더 존재
    expect(screen.getAllByText(/Todo/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/In Progress/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Done/i).length).toBeGreaterThan(0);
  });

  it("태스크가 있으면 카드가 렌더링된다", () => {
    const job = makeJob({
      tasks: {
        todo:        [makeTask({ id: "TASK-001", title: "첫 번째 태스크" })],
        in_progress: [makeTask({ id: "TASK-002", title: "진행 중 태스크", status: "in_progress" })],
        done:        [],
      },
    });
    render(<KanbanBoard job={job} />);
    expect(screen.getAllByText("첫 번째 태스크").length).toBeGreaterThan(0);
    expect(screen.getAllByText("진행 중 태스크").length).toBeGreaterThan(0);
  });

  it("카드 클릭 시 슬라이드 패널이 열린다", async () => {
    const user = userEvent.setup();
    const job  = makeJob({
      tasks: {
        todo:        [makeTask({ id: "TASK-001", title: "클릭 테스트 태스크" })],
        in_progress: [],
        done:        [],
      },
    });
    render(<KanbanBoard job={job} />);

    const cards = screen.getAllByText("클릭 테스트 태스크");
    await user.click(cards[0]);

    // 슬라이드 패널 열림 확인
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("슬라이드 패널 닫기 버튼 클릭 시 패널이 닫힌다", async () => {
    const user = userEvent.setup();
    const job  = makeJob({
      tasks: {
        todo:        [makeTask({ id: "TASK-001", title: "닫기 테스트" })],
        in_progress: [],
        done:        [],
      },
    });
    render(<KanbanBoard job={job} />);

    const cards = screen.getAllByText("닫기 테스트");
    await user.click(cards[0]);

    const closeBtn = screen.getByLabelText("닫기");
    await user.click(closeBtn);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("태스크 수 뱃지가 올바르게 표시된다", () => {
    const job = makeJob({
      tasks: {
        todo:        [makeTask({ id: "TASK-001" }), makeTask({ id: "TASK-002", title: "두 번째" })],
        in_progress: [makeTask({ id: "TASK-003", title: "세 번째", status: "in_progress" })],
        done:        [],
      },
    });
    render(<KanbanBoard job={job} />);
    // PC 칸반에서 숫자 뱃지 확인
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });
});
