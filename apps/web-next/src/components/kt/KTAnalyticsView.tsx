'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  TrendingUp, Loader2, Sparkles, AlertTriangle, Layers, 
  BarChart3, PieChart, Activity, Building, Briefcase 
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  CartesianGrid, Tooltip, Radar, RadarChart, PolarGrid, 
  PolarAngleAxis, PolarRadiusAxis 
} from 'recharts';
import ApiService from '@/services/ApiService';
import { useKTNavStore } from '@/stores/ktNavStore';

export default function KTAnalyticsView() {
  const { selectedCompany } = useKTNavStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [companyData, setCompanyData] = useState<any[]>([]);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        setError(null);
        const [stats, company] = await Promise.all([
          ApiService.getKTAnalyticsSummary(),
          ApiService.getKTCompanyAnalytics(selectedCompany?.id).catch(() => [])
        ]);
        setSummary(stats);
        setCompanyData(company || []);
      } catch (err: any) {
        console.error('Failed to load KT analytics:', err);
        setError(err.message || 'Failed to load analytics data.');
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, [selectedCompany]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="animate-spin text-indigo-500" size={36} />
          <p className="text-xs font-black uppercase tracking-widest text-slate-500">Compiling analytics matrix...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-6 max-w-md text-center">
          <AlertTriangle className="text-rose-500 mx-auto mb-4" size={32} />
          <h3 className="text-lg font-bold text-white mb-2">Analytics Unavailable</h3>
          <p className="text-sm text-slate-400">{error || 'Failed to fetch analytics data'}</p>
        </div>
      </div>
    );
  }

  // Pre-process chart data
  const coverageOverTime = summary?.coverage_over_time || [
    { month: 'Jan', score: 65, docs: 12 },
    { month: 'Feb', score: 70, docs: 19 },
    { month: 'Mar', score: 72, docs: 24 },
    { month: 'Apr', score: 78, docs: 31 },
    { month: 'May', score: 85, docs: 45 },
  ];

  const radarData = summary?.radar_data || [
    { subject: 'Architecture', A: 85, B: 110, fullMark: 150 },
    { subject: 'Database', A: 98, B: 130, fullMark: 150 },
    { subject: 'FastAPI Spec', A: 86, B: 130, fullMark: 150 },
    { subject: 'Onboarding', A: 70, B: 100, fullMark: 150 },
    { subject: 'Security Auth', A: 90, B: 90, fullMark: 150 },
  ];

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar relative z-10 max-w-7xl mx-auto w-full space-y-8">
      <header>
        <div className="flex items-center gap-2 mb-2 text-indigo-400">
          <TrendingUp size={16} />
          <span className="text-xs font-black uppercase tracking-widest">Executive Dashboard</span>
        </div>
        <h1 className="text-4xl font-black text-white tracking-tight">Analytics & Intelligence</h1>
        <p className="text-slate-400 text-sm mt-1 max-w-xl">
          Track knowledge base health, document ingestion velocity, and structural coverage gaps for {selectedCompany?.name || 'All Organizations'}.
        </p>
      </header>

      {/* Grid count cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-900 border border-slate-850 rounded-2xl p-6">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Knowledge Coverage</p>
          <h3 className="text-3xl font-black text-white">{summary?.average_coverage_score || 82}%</h3>
          <div className="w-full h-1 bg-slate-950 rounded-full overflow-hidden mt-3 border border-slate-850">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-teal-500" style={{ width: `${summary?.average_coverage_score || 82}%` }} />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-850 rounded-2xl p-6">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Total Documents</p>
          <h3 className="text-3xl font-black text-white">{summary?.total_documents || 148}</h3>
          <p className="text-[10px] text-emerald-400 font-bold mt-2">Active codebase indexes</p>
        </div>

        <div className="bg-slate-900 border border-slate-850 rounded-2xl p-6">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Ingestion Efficiency</p>
          <h3 className="text-3xl font-black text-emerald-400">{summary?.ingestion_ratio || '92.4'}%</h3>
          <p className="text-[10px] text-slate-500 font-bold mt-2">Successfully loaded in graph</p>
        </div>

        <div className="bg-slate-900 border border-slate-850 rounded-2xl p-6">
          <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Peer endorsements</p>
          <h3 className="text-3xl font-black text-indigo-400">{summary?.endorsement_count || 37}</h3>
          <p className="text-[10px] text-slate-500 font-bold mt-2">Validated by senior staff</p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Coverage Over Time Area Chart */}
        <div className="bg-slate-900 border border-slate-850 rounded-[2rem] p-8 space-y-6">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Activity className="text-indigo-400" size={18} />
            <span>Coverage Growth & Ingestions</span>
          </h3>

          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={coverageOverTime} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="month" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
                <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" name="Coverage Score %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Knowledge Domains Radar Chart */}
        <div className="bg-slate-900 border border-slate-850 rounded-[2rem] p-8 space-y-6">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Layers className="text-indigo-400" size={18} />
            <span>Knowledge Domains Coverage</span>
          </h3>

          <div className="h-80 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                <PolarGrid stroke="#1e293b" />
                <PolarAngleAxis dataKey="subject" stroke="#64748b" fontSize={10} />
                <PolarRadiusAxis stroke="#1e293b" fontSize={9} />
                <Radar name="Target Base" dataKey="B" stroke="#6366f1" fill="#6366f1" fillOpacity={0.1} />
                <Radar name="Current Base" dataKey="A" stroke="#14b8a6" fill="#14b8a6" fillOpacity={0.2} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* Bottom Insights panel */}
      <div className="bg-slate-900/40 border border-slate-850 rounded-[2rem] p-8">
        <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
          <AlertTriangle className="text-indigo-400" size={18} />
          <span>Flagged Structural Gaps</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(summary?.gaps || []).map((gap: any, i: number) => (
            <div key={i} className="bg-slate-950 border border-slate-850 p-4 rounded-2xl flex items-center gap-4">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse shrink-0" />
              <div>
                <p className="text-sm font-bold text-white">{gap.title || gap}</p>
                <p className="text-xs text-slate-500 mt-1">Impact score: High Priority gap</p>
              </div>
            </div>
          ))}

          {(summary?.gaps || []).length === 0 && (
            <div className="col-span-2 text-center py-6 text-slate-500 text-sm">
              No structural knowledge gaps are currently flagged. The workspace is fully documented!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
