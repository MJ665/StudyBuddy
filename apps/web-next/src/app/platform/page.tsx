'use client';

import { useEffect, useState } from 'react';
import ApiService from '@/services/ApiService';

interface Org {
  id: number;
  name: string;
  brand_name: string;
  status: string;
  contact_name?: string;
  contact_email?: string;
  onboarded_at?: string | null;
  created_at?: string | null;
}
interface Usage {
  total_cost_usd: number;
  total_calls: number;
  by_organization: { organization: string; calls: number; cost_usd: number }[];
  by_feature: { feature: string; calls: number; cost_usd: number }[];
}
interface Stats { total_orgs: number; pending: number; approved: number; suspended: number }

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-500/15 text-amber-400',
  approved: 'bg-emerald-500/15 text-emerald-400',
  suspended: 'bg-rose-500/15 text-rose-400',
};

export default function PlatformAdminPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [o, u, s] = await Promise.all([
        ApiService.platformListOrgs(),
        ApiService.platformAIUsage(30),
        ApiService.platformStats(),
      ]);
      setOrgs(o.organizations || []);
      setUsage(u);
      setStats(s);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load. Platform Admin access required.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const act = async (id: number, action: 'approve' | 'suspend' | 'reactivate') => {
    setBusy(id);
    try {
      if (action === 'approve') {
        const r = await ApiService.platformApproveOrg(id);
        setToast(`Approved. Onboarding link: ${r.onboarding_url}`);
      } else if (action === 'suspend') {
        await ApiService.platformSuspendOrg(id);
      } else {
        await ApiService.platformReactivateOrg(id);
      }
      await load();
    } catch (e: unknown) {
      setToast(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-black tracking-tight">Platform Admin</h1>
            <p className="text-slate-400 text-sm">Powered by StudyBuddy — org governance &amp; AI cost</p>
          </div>
          <button onClick={load} className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">Refresh</button>
        </header>

        {error && <div className="mb-6 rounded-lg bg-rose-500/10 text-rose-400 p-4 text-sm">{error}</div>}
        {toast && (
          <div className="mb-6 rounded-lg bg-slate-800 p-4 text-sm break-all flex justify-between gap-4">
            <span>{toast}</span>
            <button onClick={() => setToast(null)} className="text-slate-400 shrink-0">✕</button>
          </div>
        )}

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : (
          <>
            {stats && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {([['Total orgs', stats.total_orgs], ['Pending', stats.pending], ['Approved', stats.approved], ['Suspended', stats.suspended]] as const).map(([label, val]) => (
                  <div key={label} className="rounded-xl bg-slate-900 border border-slate-800 p-5">
                    <div className="text-3xl font-black">{val}</div>
                    <div className="text-slate-400 text-xs uppercase tracking-widest mt-1">{label}</div>
                  </div>
                ))}
              </div>
            )}

            {usage && (
              <div className="rounded-xl bg-slate-900 border border-slate-800 p-6 mb-8">
                <div className="flex items-baseline justify-between mb-4">
                  <h2 className="font-bold">AI cost &amp; utilization (30d)</h2>
                  <div className="text-right">
                    <div className="text-2xl font-black text-emerald-400">${usage.total_cost_usd.toFixed(4)}</div>
                    <div className="text-slate-500 text-xs">{usage.total_calls} calls</div>
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">By organization</div>
                    {usage.by_organization.slice(0, 8).map((r) => (
                      <div key={r.organization} className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                        <span className="truncate">{r.organization}</span>
                        <span className="text-slate-400">${r.cost_usd.toFixed(4)} · {r.calls}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">By feature</div>
                    {usage.by_feature.slice(0, 8).map((r) => (
                      <div key={r.feature} className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                        <span className="truncate">{r.feature}</span>
                        <span className="text-slate-400">${r.cost_usd.toFixed(4)} · {r.calls}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
              <h2 className="font-bold p-5 border-b border-slate-800">Organizations</h2>
              {orgs.length === 0 && <div className="p-5 text-slate-500 text-sm">No organizations yet.</div>}
              {orgs.map((o) => (
                <div key={o.id} className="flex items-center justify-between gap-4 p-4 border-b border-slate-800/50">
                  <div className="min-w-0">
                    <div className="font-semibold truncate">{o.brand_name || o.name}</div>
                    <div className="text-slate-500 text-xs truncate">{o.contact_name} · {o.contact_email}</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${STATUS_STYLES[o.status] || 'bg-slate-700'}`}>{o.status}</span>
                    {o.status === 'pending' && (
                      <button disabled={busy === o.id} onClick={() => act(o.id, 'approve')} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-bold disabled:opacity-50">Approve</button>
                    )}
                    {o.status === 'approved' && (
                      <button disabled={busy === o.id} onClick={() => act(o.id, 'suspend')} className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-xs font-bold disabled:opacity-50">Suspend</button>
                    )}
                    {o.status === 'suspended' && (
                      <button disabled={busy === o.id} onClick={() => act(o.id, 'reactivate')} className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-bold disabled:opacity-50">Reactivate</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
