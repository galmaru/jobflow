"use client";

import type { TaskStatus } from "@/lib/types";

const TABS: { label: string; value: TaskStatus }[] = [
  { label: "Todo",        value: "todo" },
  { label: "In Progress", value: "in_progress" },
  { label: "Done",        value: "done" },
];

interface MobileTabFilterProps {
  active:   TaskStatus;
  onChange: (tab: TaskStatus) => void;
  counts:   Record<TaskStatus, number>;
}

export function MobileTabFilter({ active, onChange, counts }: MobileTabFilterProps) {
  return (
    <div className="flex border-b bg-white">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={[
            "flex-1 py-2 text-sm font-medium transition-colors",
            active === tab.value
              ? "border-b-2 border-blue-500 text-blue-600"
              : "text-gray-500 hover:text-gray-700",
          ].join(" ")}
        >
          {tab.label}
          <span className="ml-1 text-xs text-gray-400">({counts[tab.value]})</span>
        </button>
      ))}
    </div>
  );
}
