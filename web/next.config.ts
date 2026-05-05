import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Permite o backend FastAPI durante dev — em produção, mesma origem via reverse proxy.
  async rewrites() {
    // INTERNAL_API_URL é resolvido server-side (rewrite roda no Node do Next).
    // Em Docker, o container web fala com `http://api:8000` via DNS interno.
    // No host nativo, cai em http://localhost:8000.
    const apiUrl =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return [
      { source: "/api/health", destination: `${apiUrl}/health` },
      { source: "/api/auth/:path*", destination: `${apiUrl}/auth/:path*` },
      { source: "/api/chat", destination: `${apiUrl}/chat` },
      { source: "/api/admin/:path*", destination: `${apiUrl}/admin/:path*` },
      { source: "/api/tenant-users", destination: `${apiUrl}/tenant-users` },
      { source: "/api/tenant-users/:path*", destination: `${apiUrl}/tenant-users/:path*` },
      { source: "/api/cobrancas/:path*", destination: `${apiUrl}/cobrancas/:path*` },
    ];
  },
};

export default nextConfig;
