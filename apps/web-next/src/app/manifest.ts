import type { MetadataRoute } from 'next';

/**
 * PWA web app manifest (Next 15 metadata route → served at /manifest.webmanifest,
 * auto-linked from <head>). Makes StudyBuddy installable ("Add to Home Screen" /
 * Chrome install) and gives the Android WebView wrapper a real app identity.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'StudyBuddy — AI Assessment Platform',
    short_name: 'StudyBuddy',
    description:
      'AI assessment platform for quizzes, coding, exams and knowledge transfer.',
    start_url: '/dashboard',
    scope: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#0c1324',
    theme_color: '#0c1324',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  };
}
