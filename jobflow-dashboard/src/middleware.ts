import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifyBearer } from "@/lib/auth";

export function middleware(req: NextRequest) {
  // /api/slack/* 는 자체 인증 로직 (NOTIFY_SECRET, CRON_SECRET) 사용
  if (req.nextUrl.pathname.startsWith("/api/slack/")) {
    return NextResponse.next();
  }

  if (req.nextUrl.pathname.startsWith("/api/")) {
    if (!verifyBearer(req.headers.get("authorization"))) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  return NextResponse.next();
}

export const config = { matcher: "/api/:path*" };
