import path from "node:path";

import type { NextConfig } from "next";

// Where `npm run dev` sends /api/* requests: the Traefik gateway from `docker compose up`.
// In Docker and on the live server, Traefik routes /api/* to the services before a
// request ever reaches Next.js, so this rewrite is only used by the dev server.
const apiProxyUrl = process.env.API_PROXY_URL ?? "http://localhost";

const nextConfig: NextConfig = {
  // A self-contained server in .next/standalone, so the Docker image needs no node_modules.
  output: "standalone",
  // web/ is the project root. Without this, Next.js may pick up a package-lock.json from a
  // parent folder (e.g. your home folder) and guess the wrong root.
  outputFileTracingRoot: path.join(__dirname),
  turbopack: { root: path.join(__dirname) },
  poweredByHeader: false,
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [{ source: "/api/:path*", destination: `${apiProxyUrl}/api/:path*` }];
  },
};

export default nextConfig;
