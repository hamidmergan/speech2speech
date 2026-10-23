import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// Where the API lives. Read while this config is loaded, which for `next build`
// means the destinations below are frozen into the build: setting BACKEND_URL on
// a built container has no effect any more. In Docker it is a build argument of
// frontend/Dockerfile, set by docker-compose.yml. For `npm run dev` the shell
// value applies, the default fits the port the compose file publishes.
const backendUrl = process.env.BACKEND_URL || "http://localhost:8100";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {
    // A local model may take minutes for one answer, the default would cut it off.
    proxyTimeout: 600000,
    optimizePackageImports: ["@phosphor-icons/react"],
  },
  async rewrites() {
    // Everything the browser calls goes through this origin, the backend stays inside the network.
    return [
      {
        source: "/api/access/:path*",
        destination: `${backendUrl}/access/:path*`,
      },
      {
        source: "/api/access",
        destination: `${backendUrl}/access`,
      },
      {
        source: "/api/config",
        destination: `${backendUrl}/config`,
      },
      {
        source: "/api/interpreter/:path*",
        destination: `${backendUrl}/interpreter/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
