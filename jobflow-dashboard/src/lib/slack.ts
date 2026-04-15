/**
 * Slack Block Kit 메시지 빌더.
 * 이벤트 유형별로 Slack Incoming Webhook에 전송할 payload를 생성한다.
 */

export type NotifyEvent = "task_done" | "stage_changed" | "task_added" | "daily_summary";

export interface DailySummary {
  total:            number;
  done_today:       number;
  in_progress:      number;
  todo:             number;
  completed_tasks:  string[];
}

export interface NotifyPayload {
  event:       NotifyEvent;
  job_id:      string;
  job_name:    string;
  task_id?:    string;
  task_title?: string;
  from_stage?: string;
  to_stage?:   string;
  summary?:    DailySummary;
  timestamp:   string;
  secret:      string;
}

const STAGE_ICON: Record<string, string> = {
  todo:        "🔵",
  in_progress: "🟡",
  done:        "🟢",
};

function stageLabel(stage: string): string {
  const icon  = STAGE_ICON[stage] ?? "";
  const label = stage === "in_progress" ? "In Progress" : stage.charAt(0).toUpperCase() + stage.slice(1);
  return `${icon} ${label}`;
}

function dashboardUrl(jobId: string): string {
  const base = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.NEXT_PUBLIC_DASHBOARD_URL ?? "";
  return base ? `${base}/jobs/${jobId}` : "";
}

function formatTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
  } catch {
    return iso;
  }
}

export function buildSlackMessage(payload: NotifyPayload): object {
  const { event, job_name, job_id, task_id, task_title, from_stage, to_stage, summary, timestamp } = payload;
  const url = dashboardUrl(job_id);

  const actionsBlock = url
    ? [{
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "대시보드 보기" },
          url,
        }],
      }]
    : [];

  if (event === "task_done") {
    return {
      blocks: [
        { type: "header", text: { type: "plain_text", text: "✅ 태스크 완료" } },
        {
          type: "section",
          fields: [
            { type: "mrkdwn", text: `*Job*\n${job_name}` },
            { type: "mrkdwn", text: `*태스크*\n${task_id} ${task_title}` },
            { type: "mrkdwn", text: `*완료 시각*\n${formatTs(timestamp)}` },
          ],
        },
        ...actionsBlock,
      ],
    };
  }

  if (event === "stage_changed") {
    return {
      blocks: [
        { type: "header", text: { type: "plain_text", text: "🔄 태스크 단계 변경" } },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*${task_id}* ${task_title}\n${stageLabel(from_stage ?? "")} → ${stageLabel(to_stage ?? "")}\n*Job:* ${job_name}`,
          },
        },
        ...actionsBlock,
      ],
    };
  }

  if (event === "task_added") {
    return {
      blocks: [
        { type: "header", text: { type: "plain_text", text: "➕ 새 태스크 추가" } },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*${task_id}* ${task_title}\n*Job:* ${job_name}`,
          },
        },
        ...actionsBlock,
      ],
    };
  }

  if (event === "daily_summary" && summary) {
    const dateStr = formatTs(timestamp).split(" ")[0];
    const completedList = summary.completed_tasks.length
      ? summary.completed_tasks.map((t) => `• ${t}`).join("\n")
      : "없음";

    return {
      blocks: [
        { type: "header", text: { type: "plain_text", text: `📊 일일 진행 요약 — ${dateStr}` } },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: [
              `✅ 오늘 완료: *${summary.done_today}*개`,
              `🟡 진행 중: *${summary.in_progress}*개`,
              `🔵 남은 Todo: *${summary.todo}*개`,
            ].join("\n"),
          },
        },
        {
          type: "section",
          text: { type: "mrkdwn", text: `*오늘 완료한 태스크:*\n${completedList}` },
        },
        ...actionsBlock,
      ],
    };
  }

  // 알 수 없는 이벤트 — 기본 텍스트
  return { text: `[JobFlow] ${event}: ${job_name}` };
}

/** Slack Incoming Webhook으로 메시지 전송 */
export async function sendSlackMessage(message: object): Promise<void> {
  const webhookUrl = process.env.SLACK_WEBHOOK_URL;
  if (!webhookUrl) throw new Error("SLACK_WEBHOOK_URL 환경변수 미설정");

  const res = await fetch(webhookUrl, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(message),
  });

  if (!res.ok) {
    throw new Error(`Slack Webhook 실패: ${res.status} ${res.statusText}`);
  }
}
