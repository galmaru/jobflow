/**
 * TaskSlideOver 컴포넌트 테스트.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { TaskSlideOver } from "../components/TaskSlideOver";
import type { Task } from "../lib/types";

const makeTask = (overrides: Partial<Task> = {}): Task => ({
  id:           "TASK-001",
  title:        "슬라이드 테스트 태스크",
  status:       "in_progress",
  tag:          "#frontend",
  priority:     "high",
  checklist:    [],
  started_at:   "2026-04-14T09:00:00+09:00",
  updated_at:   "2026-04-14T10:00:00+09:00",
  completed_at: null,
  ...overrides,
});

describe("TaskSlideOver", () => {
  it("task가 null이면 아무것도 렌더링되지 않는다", () => {
    const { container } = render(<TaskSlideOver task={null} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("task가 있으면 패널이 렌더링된다", () => {
    const task = makeTask();
    render(<TaskSlideOver task={task} onClose={() => {}} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("슬라이드 테스트 태스크")).toBeInTheDocument();
    expect(screen.getByText("TASK-001")).toBeInTheDocument();
  });

  it("태그와 우선순위가 표시된다", () => {
    const task = makeTask({ tag: "#backend", priority: "high" });
    render(<TaskSlideOver task={task} onClose={() => {}} />);

    expect(screen.getByText("#backend")).toBeInTheDocument();
    expect(screen.getByText("!high")).toBeInTheDocument();
  });

  it("체크리스트 항목이 표시된다", () => {
    const task = makeTask({
      checklist: [
        { text: "항목 1", checked: false },
        { text: "항목 2", checked: true },
      ],
    });
    render(<TaskSlideOver task={task} onClose={() => {}} />);

    expect(screen.getByText("항목 1")).toBeInTheDocument();
    expect(screen.getByText("항목 2")).toBeInTheDocument();
  });

  it("닫기 버튼 클릭 시 onClose가 호출된다", () => {
    const onClose = jest.fn();
    const task    = makeTask();
    render(<TaskSlideOver task={task} onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("닫기"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ESC 키 입력 시 onClose가 호출된다", () => {
    const onClose = jest.fn();
    const task    = makeTask();
    render(<TaskSlideOver task={task} onClose={onClose} />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("started_at 날짜가 표시된다", () => {
    const task = makeTask({ started_at: "2026-04-14T09:00:00+09:00" });
    render(<TaskSlideOver task={task} onClose={() => {}} />);

    expect(screen.getByText(/시작:/)).toBeInTheDocument();
  });

  it("completed_at이 있으면 완료 날짜가 표시된다", () => {
    const task = makeTask({
      status:       "done",
      completed_at: "2026-04-14T12:00:00+09:00",
    });
    render(<TaskSlideOver task={task} onClose={() => {}} />);

    expect(screen.getByText(/완료:/)).toBeInTheDocument();
  });
});
