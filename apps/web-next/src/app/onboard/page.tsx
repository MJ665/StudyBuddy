'use client';

import { useEffect, useState } from 'react';
import ApiService from '@/services/ApiService';

const input = 'w-full rounded-lg bg-slate-800 border border-slate-700 px-4 py-2.5 text-sm focus:outline-none focus:border-emerald-500';
const label = 'block text-slate-400 text-xs uppercase tracking-widest mb-1.5';

export default function OnboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [org, setOrg] = useState<{ org_name: string; organization_id: number } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Signup fields
  const [orgName, setOrgName] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');

  // Completion fields
  const [adminName, setAdminName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [brandName, setBrandName] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [signatureUrl, setSignatureUrl] = useState('');

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get('token');
    setToken(t);
    if (t) {
      ApiService.verifyOnboarding(t)
        .then((r) => setOrg(r))
        .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Invalid onboarding link'))
        .finally(() => setChecked(true));
    } else {
      setChecked(true);
    }
  }, []);

  const submitSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await ApiService.orgSignup({ org_name: orgName, contact_name: contactName, contact_email: contactEmail });
      setMsg('Request received! You will get an onboarding email once a StudyBuddy admin approves your organization.');
    } catch (e2: unknown) {
      setErr(e2 instanceof Error ? e2.message : 'Signup failed');
    } finally { setBusy(false); }
  };

  const submitComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await ApiService.completeOnboarding({
        token: token!, admin_full_name: adminName, admin_email: adminEmail,
        admin_password: adminPassword, brand_name: brandName || undefined,
        logo_url: logoUrl || undefined, signature_url: signatureUrl || undefined,
      });
      setMsg('Onboarding complete! Your L&D Admin can now sign in.');
    } catch (e2: unknown) {
      setErr(e2 instanceof Error ? e2.message : 'Onboarding failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-emerald-400 font-black text-2xl">StudyBuddy</div>
          <div className="text-slate-500 text-sm">Multi-tenant AI assessment platform</div>
        </div>

        {msg ? (
          <div className="rounded-xl bg-emerald-500/10 text-emerald-300 p-6 text-center">{msg}</div>
        ) : !checked ? (
          <div className="text-slate-500 text-center">Loading…</div>
        ) : token ? (
          // Completion wizard (token present)
          org ? (
            <form onSubmit={submitComplete} className="rounded-xl bg-slate-900 border border-slate-800 p-6 space-y-4">
              <h1 className="font-bold text-lg">Finish onboarding {org.org_name}</h1>
              {err && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-3 text-sm">{err}</div>}
              <div><label className={label}>L&amp;D Admin full name</label><input className={input} value={adminName} onChange={(e) => setAdminName(e.target.value)} required /></div>
              <div><label className={label}>L&amp;D Admin email</label><input type="email" className={input} value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required /></div>
              <div><label className={label}>Password (min 8)</label><input type="password" className={input} value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} required minLength={8} /></div>
              <div><label className={label}>Brand name (optional)</label><input className={input} value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder={org.org_name} /></div>
              <div><label className={label}>Org logo URL (optional)</label><input className={input} value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} /></div>
              <div><label className={label}>Admin signature URL (optional)</label><input className={input} value={signatureUrl} onChange={(e) => setSignatureUrl(e.target.value)} /></div>
              <button disabled={busy} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2.5 font-bold disabled:opacity-50">{busy ? 'Completing…' : 'Complete onboarding'}</button>
              <p className="text-center text-slate-600 text-xs">Powered by StudyBuddy</p>
            </form>
          ) : (
            <div className="rounded-xl bg-rose-500/10 text-rose-400 p-6 text-center">{err || 'Invalid or expired onboarding link.'}</div>
          )
        ) : (
          // Public signup (no token)
          <form onSubmit={submitSignup} className="rounded-xl bg-slate-900 border border-slate-800 p-6 space-y-4">
            <h1 className="font-bold text-lg">Register your organization</h1>
            {err && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-3 text-sm">{err}</div>}
            <div><label className={label}>Organization name</label><input className={input} value={orgName} onChange={(e) => setOrgName(e.target.value)} required minLength={2} /></div>
            <div><label className={label}>Your name</label><input className={input} value={contactName} onChange={(e) => setContactName(e.target.value)} required minLength={2} /></div>
            <div><label className={label}>Your email</label><input type="email" className={input} value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} required /></div>
            <button disabled={busy} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2.5 font-bold disabled:opacity-50">{busy ? 'Submitting…' : 'Request access'}</button>
            <p className="text-center text-slate-600 text-xs">A StudyBuddy admin will review and email you an onboarding link.</p>
          </form>
        )}
      </div>
    </div>
  );
}
