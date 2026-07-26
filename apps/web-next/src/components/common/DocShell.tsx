import React from 'react';

/**
 * Dark-theme chrome for standalone document pages (privacy, terms, …). These
 * routes have no (app)/(public) layout, so they must provide their own themed
 * background — otherwise text renders on the browser's default white.
 */
export function DocShell({
  title,
  updated,
  children,
}: {
  title: string;
  updated?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0c1324] text-slate-300">
      <header className="border-b border-white/5">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4 md:px-8">
          <a href="/" className="flex items-center gap-2.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/images/logo.png" alt="StudyBuddy" className="h-7 w-7 rounded-lg object-cover" />
            <span className="text-base font-black text-white">StudyBuddy</span>
          </a>
          <div className="flex items-center gap-5 text-sm font-semibold text-slate-400">
            <a href="/" className="hover:text-white transition-colors">Home</a>
            <a href="/login" className="rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-500 transition-colors">Sign in</a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-14 md:px-8">
        <h1 className="text-3xl font-black text-white">{title}</h1>
        {updated && <p className="mt-1 text-sm text-slate-500">{updated}</p>}
        <div className="mt-10 space-y-8 leading-relaxed [&_h2]:text-lg [&_h2]:font-bold [&_h2]:text-white [&_a]:text-indigo-400 [&_a]:underline [&_strong]:text-slate-100">
          {children}
        </div>
      </main>

      <footer className="border-t border-white/5">
        <p className="mx-auto max-w-3xl px-5 py-8 text-center text-xs text-slate-600 md:px-8">
          © {new Date().getFullYear()} StudyBuddy · <a href="/privacy" className="hover:text-slate-400">Privacy</a> · <a href="/terms" className="hover:text-slate-400">Terms</a> · <a href="/contact-me" className="hover:text-slate-400">Contact</a>
        </p>
      </footer>
    </div>
  );
}
