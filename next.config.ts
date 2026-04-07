import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Force a fresh build ID on every build so Vercel's CDN cache is invalidated.
  // Without this, Next.js may reuse a cached build hash and serve a stale JS bundle.
  generateBuildId: async () => `build-${Date.now()}`,
};

export default nextConfig;
