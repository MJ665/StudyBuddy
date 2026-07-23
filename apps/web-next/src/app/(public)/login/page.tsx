'use client';

/**
 * Email-first login (owner decision #6) — the ONLY sign-in path.
 *
 * Individual email + password credentials; new accounts receive theirs by
 * email at creation. The legacy group-pattern login is fully retired.
 */

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { KeyRound, Loader2, Mail } from 'lucide-react';

import ApiService from '@/services/ApiService';
import { landingRouteFor, useSessionStore } from '@/stores/sessionStore';

export default function LoginPage() {
  const router = useRouter();
  const { user, hydrated, hydrate } = useSessionStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!hydrated) void hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (hydrated && user) router.replace(landingRouteFor(user));
  }, [hydrated, user, router]);

  const finishLogin = async () => {
    const me = await hydrate();
    router.replace(landingRouteFor(me));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setBusy(true);
    try {
      await ApiService.loginWithEmail(email.trim().toLowerCase(), password);
      await finishLogin();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid email or password');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black text-white">Welcome back</h1>
          <p className="text-slate-400 mt-2">Sign in to your StudyHub account</p>
        </div>

        <form
          onSubmit={submit}
          className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-5"
        >
          <label className="block">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Work email
            </span>
            <div className="mt-2 flex items-center gap-3 bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 focus-within:border-indigo-500">
              <Mail size={18} className="text-slate-500" />
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="bg-transparent flex-1 text-white outline-none placeholder:text-slate-600"
              />
            </div>
          </label>

          <label className="block">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Password
            </span>
            <div className="mt-2 flex items-center gap-3 bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 focus-within:border-indigo-500">
              <KeyRound size={18} className="text-slate-500" />
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="bg-transparent flex-1 text-white outline-none placeholder:text-slate-600"
              />
            </div>
          </label>

          {error && (
            <p className="text-sm text-rose-400 bg-rose-900/20 border border-rose-500/20 rounded-xl px-4 py-3">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white py-3.5 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30"
          >
            {busy && <Loader2 size={18} className="animate-spin" />}
            Sign in
          </button>

          <div className="flex items-center justify-between text-sm pt-1">
            <button
              type="button"
              onClick={() => router.push('/forgot-password')}
              className="text-slate-400 hover:text-white"
            >
              Forgot password?
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
