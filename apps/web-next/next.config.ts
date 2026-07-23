import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Proxy /api/* → the FastAPI backend in local dev.
  // (The old '/profile/:slug' and '/p/:slug' → '/' rewrites are GONE: they
  // were state-machine-era shims that shadowed the real dynamic routes
  // src/app/(public)/profile/[slug] and src/app/p/[slug] after Phase 4.)
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
