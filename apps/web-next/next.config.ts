import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Proxy /api/* → http://127.0.0.1:8000/* in local dev
  // This mirrors the Vite proxy: { '/api': { target: 'http://127.0.0.1:8000', rewrite: path => path.replace(/^\/api/, '') } }
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
      {
        source: '/profile/:slug',
        destination: '/',
      },
      {
        source: '/p/:slug',
        destination: '/',
      },
    ];
  },
};

export default nextConfig;
