/**
 * Root route (`/`) — the public marketing home.
 *
 * Server component so the content is in the SSR'd HTML (good for SEO + link
 * previews). <AuthedRedirect/> is a tiny client island that bounces already
 * logged-in visitors into their dashboard, preserving the pre-landing behavior.
 * The installed mobile app + PWA never hit this route — they open /dashboard
 * directly (see apps/mobile: EXPO_PUBLIC_ENTRY_PATH, and manifest.ts start_url).
 */
import type { Metadata } from 'next';
import AuthedRedirect from '@/components/landing/AuthedRedirect';
import LandingPage from '@/components/landing/LandingPage';

export const metadata: Metadata = {
  title: 'StudyBuddy — Enterprise Assessment & Knowledge Transfer',
  description:
    'StudyBuddy is the single platform to assess and grow every employee (quizzes, coding, proctored exams) and to retain the knowledge of the people who leave, through AI-powered, cited knowledge transfer.',
  openGraph: {
    title: 'StudyBuddy — Assess. Retain. Grow.',
    description:
      'Assess your people. Keep the knowledge they carry. One enterprise platform for assessment + AI knowledge transfer.',
    siteName: 'StudyBuddy',
    type: 'website',
    images: [{ url: '/images/logo.png' }],
  },
  twitter: {
    card: 'summary',
    title: 'StudyBuddy — Assess. Retain. Grow.',
    description: 'Enterprise assessment + AI knowledge transfer, in one platform.',
  },
};

export default function Home() {
  return (
    <>
      <AuthedRedirect />
      <LandingPage />
    </>
  );
}
