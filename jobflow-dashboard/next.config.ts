import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 서버 사이드 전용 모듈이 클라이언트 번들에 포함되지 않도록
  serverExternalPackages: [],
};

export default nextConfig;
