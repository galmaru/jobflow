import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title:       "JobFlow Dashboard",
  description: "개인 태스크 관리 칸반 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-gray-100 min-h-screen text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
