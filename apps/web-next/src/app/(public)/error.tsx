'use client';

/** Route-group error boundary for public pages (login, recovery, profiles). */

export default function PublicError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-10 max-w-md w-full text-center">
        <h2 className="text-2xl font-black text-white mb-2">Something broke</h2>
        <p className="text-slate-400 text-sm mb-6 break-words">
          {error.message || 'An unexpected error occurred.'}
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all"
          >
            Try again
          </button>
          <a
            href="/login"
            className="flex-1 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-bold transition-all border border-slate-700"
          >
            Sign in
          </a>
        </div>
      </div>
    </div>
  );
}
