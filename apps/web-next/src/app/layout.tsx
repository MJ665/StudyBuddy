import type { Metadata } from 'next';
import { ReactQueryProvider } from '@/lib/ReactQueryProvider';
import { BrandingProvider } from '@/components/common/Branding';
import './globals.css';
import 'katex/dist/katex.min.css';

export const metadata: Metadata = {
  title: 'StudyBuddy — AI Assessment Platform',
  description: 'StudyBuddy — multi-tenant AI assessment platform for quizzes, coding, exams and knowledge transfer.',
  icons: {
    icon: '/images/logo.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Google Fonts — Inter */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        {/* Material Symbols Outlined — used in Sidebar nav icons */}
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ReactQueryProvider>
          <BrandingProvider>
            {children}
          </BrandingProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
