import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Permite o backend FastAPI durante dev — em produção, mesma origem via reverse proxy.
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/api/health", destination: `${apiUrl}/health` },
      { source: "/api/auth/:path*", destination: `${apiUrl}/auth/:path*` },
      { source: "/api/chat", destination: `${apiUrl}/chat` },
    ];
  },
};

export default nextConfig;
