import React, { useEffect, useState } from 'react';
import { 
  FileText, 
  Printer, 
  ArrowLeft, 
  TrendingUp, 
  Users, 
  Target, 
  Activity,
  Award,
  Zap,
  ChevronRight,
  Download
} from 'lucide-react';
import ApiService, { ExecutiveSummary, AIResponseEnvelope } from '../../services/ApiService';
import { motion } from 'motion/react';

export default function ExecutiveReport({ batchId, onBack }: { batchId: number, onBack: () => void }) {
  const [data, setData] = useState<any>(null);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [aiInsights, setAiInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [exportingXlsx, setExportingXlsx] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingDeep, setExportingDeep] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [reportRes, summaryRes, insightsRes] = await Promise.all([
          ApiService.getBatchReport(batchId),
          ApiService.getBatchExecutiveSummary(batchId),
          ApiService.getBatchAiInsights(batchId)
        ]) as [any, ExecutiveSummary, any];
        setData(reportRes);
        setAiSummary(summaryRes.summary);
        // Defense: only keep insights with a readable body so we never render
        // hollow "Impact / Recommended Intervention" cards (Bug 21).
        setAiInsights(
          (insightsRes.insights || []).filter(
            (x: any) => x && (x.observation || x.insight)
          )
        );
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [batchId]);

  const handleXlsxDownload = async () => {
    setExportingXlsx(true);
    try {
      const result = await ApiService.exportBatchXlsx(batchId);
      if (!(result instanceof Blob)) {
        alert((result as { detail?: string } | null)?.detail || 'Excel export failed');
        return;
      }
      const url = URL.createObjectURL(result);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_${batchId}_report.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Excel export failed:', err);
    } finally {
      setExportingXlsx(false);
    }
  };

  const handleCsvDownload = async () => {
    setExportingCsv(true);
    try {
      const blob = await ApiService.exportBatchCsv(batchId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_${batchId}_report.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('CSV export failed:', err);
    } finally {
      setExportingCsv(false);
    }
  };

  const handleDeepDownload = async () => {
    setExportingDeep(true);
    try {
      const payload = {
        batch_id: batchId,
        include_metrics: true,
        include_demographics: true,
        export_format: 'json',
        deep_scan: true
      };
      const result = await ApiService.exportDeep(payload);
      let blob;
      if (result instanceof Blob) {
        blob = result;
      } else {
        blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_${batchId}_deep_export.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Deep export failed:', err);
    } finally {
      setExportingDeep(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-primary" />
      </div>
    );
  }

  if (!data) return <div>No data found</div>;

  return (
    <div id="executive-report" className="min-h-screen bg-white text-slate-900 p-8 md:p-12 print:p-0">
      <div className="max-w-5xl mx-auto">
        {/* ─── Non-Printable Header ─────────────────────────── */}
        <div className="flex items-center justify-between mb-12 print:hidden">
          <button 
            onClick={onBack}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-all font-bold"
          >
            <ArrowLeft size={18} /> Back to Insights
          </button>
          <div className="flex items-center gap-3">
            <button
              id="btn-export-csv"
              onClick={handleCsvDownload}
              disabled={exportingCsv}
              className="flex items-center gap-2 bg-slate-100 text-slate-700 px-5 py-3 rounded-2xl font-bold border border-slate-200 hover:bg-slate-200 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download size={16} /> {exportingCsv ? 'Exporting…' : 'CSV (.csv)'}
            </button>
            <button
              id="btn-export-xlsx"
              onClick={handleXlsxDownload}
              disabled={exportingXlsx}
              className="flex items-center gap-2 bg-emerald-600 text-white px-5 py-3 rounded-2xl font-bold shadow-xl shadow-emerald-600/30 hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download size={16} /> {exportingXlsx ? 'Exporting…' : 'Excel (.xlsx)'}
            </button>
            <button
              id="btn-export-deep"
              onClick={handleDeepDownload}
              disabled={exportingDeep}
              className="flex items-center gap-2 bg-purple-600 text-white px-5 py-3 rounded-2xl font-bold shadow-xl shadow-purple-600/30 hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
            >
              <Download size={16} /> {exportingDeep ? 'Exporting…' : 'Export Deep'}
            </button>
            <button 
              onClick={() => window.print()}
              className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-2xl font-bold shadow-xl shadow-indigo-600/30 hover:scale-105 active:scale-95 transition-all"
            >
              <Printer size={18} /> Print Executive Summary
            </button>
          </div>
        </div>

        {/* ─── Report Header ────────────────────────────────── */}
        <div className="border-b-4 border-slate-900 pb-10 mb-12 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white overflow-hidden shrink-0 shadow-lg">
                <img src="/images/logo.png" alt="StudyBuddy Logo" className="w-full h-full object-cover rounded-xl" />
              </div>
              <h1 className="text-4xl font-black tracking-tight text-slate-900 uppercase">Executive Intelligence</h1>
            </div>
            <p className="text-xl text-slate-500 font-medium max-w-2xl leading-relaxed italic">
              {aiSummary || "Synthesizing cross-cohort performance vectors for strategic analysis..."}
            </p>
          </div>
          <div className="text-left md:text-right">
            <p className="text-sm font-black uppercase tracking-widest text-indigo-600 mb-1">{data.batch_name}</p>
            <p className="text-xs text-slate-400 font-bold">{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
          </div>
        </div>

        {/* ─── High Level KPIs ──────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          <StatCard 
            icon={<Users className="text-indigo-600" />} 
            label="Active Talent" 
            value={data.total_members} 
            sub={`Across ${data.total_groups} Groups`}
          />
          <StatCard 
            icon={<Target className="text-emerald-600" />} 
            label="Avg Proficiency" 
            value={`${data.average_score}%`} 
            sub="Enterprise Benchmark"
          />
          <StatCard 
            icon={<Activity className="text-blue-600" />} 
            label="Total Assessments" 
            value={data.total_attempts} 
            sub="Aggregated Learning Units"
          />
          <StatCard 
            icon={<Zap className="text-amber-600" />} 
            label="Participation Rate"
            value={
              data.total_members > 0
                ? `${Math.min(100, Math.round((data.total_attempts / data.total_members) * 100))}%`
                : '—'
            }
            sub="Attempts per Enrolled Member"
          />
        </div>

        {/* ─── Top Performers & Group Insights ──────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 mb-12">
          <section>
            <h2 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3 border-b-2 border-slate-100 pb-4">
              <Award className="text-amber-500" /> TOP TALENT RECOGNITION
            </h2>
            <div className="space-y-4">
              {data.top_performers?.map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100">
                  <div className="flex items-center gap-4">
                    <span className="text-xs font-black text-slate-400 w-6">#{i+1}</span>
                    <div>
                      <p className="font-bold text-slate-900">{p.full_name}</p>
                      <p className="text-[10px] uppercase font-black tracking-widest text-slate-400">{p.group_name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-black text-indigo-600">{p.avg_score}%</p>
                    <p className="text-[10px] font-bold text-slate-400">{p.attempt_count ?? '—'} Units</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
             <h2 className="text-xl font-black text-slate-900 mb-6 flex items-center gap-3 border-b-2 border-slate-100 pb-4">
              <TrendingUp className="text-indigo-500" /> GROUP VELOCITY COMPARISON
            </h2>
            <div className="space-y-4">
              {data.group_performance?.map((g: any, i: number) => (
                <div key={i} className="space-y-2">
                   <div className="flex justify-between items-end text-xs font-bold">
                      <span className="text-slate-700 uppercase tracking-wider">{g.group_name}</span>
                      <span className="text-slate-500">{g.avg_score}% Proficiency</span>
                   </div>
                   <div className="h-3 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${g.avg_score}%` }}
                        transition={{ duration: 1, delay: i * 0.1 }}
                        className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full"
                      />
                   </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* ─── AI-Driven Strategic Observations ───────────────── */}
        <div className="bg-slate-900 text-white p-10 rounded-[3rem] shadow-2xl relative overflow-hidden mb-12">
          <div className="absolute top-0 right-0 p-10 opacity-5">
            <TrendingUp size={240} />
          </div>
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-8">
               <Zap className="text-amber-400" />
               <h2 className="text-2xl font-black uppercase tracking-tight">AI Strategic Observations</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {aiInsights.length > 0 ? aiInsights.map((insight: any, i: number) => (
                <div key={i} className="p-6 bg-white/5 border border-white/10 rounded-2xl">
                   <div className="flex justify-between items-start mb-3">
                      <span className="text-[10px] font-black uppercase tracking-[0.2em] text-indigo-400">{insight.category}</span>
                      <span className={`text-[8px] font-black uppercase px-2 py-0.5 rounded ${
                         insight.impact === 'High' ? 'bg-rose-500/20 text-rose-400' : 
                         insight.impact === 'Medium' ? 'bg-amber-500/20 text-amber-400' : 
                         'bg-emerald-500/20 text-emerald-400'
                      }`}>
                         {insight.impact} Impact
                      </span>
                   </div>
                   <h4 className="text-sm font-black mb-2 text-white">{insight.dimension}</h4>
                   <p className="text-xs text-slate-400 leading-relaxed mb-4">{insight.observation}</p>
                   <div className="pt-4 border-t border-white/5">
                      <p className="text-[9px] font-black text-indigo-300 uppercase mb-1">Recommended Intervention</p>
                      <p className="text-[10px] font-bold text-slate-300 italic">{insight.actionable_step}</p>
                   </div>
                </div>
              )) : (
                <p className="text-slate-500 italic text-sm">Synchronizing with AI Executive Engine... Observations will manifest upon neural verification.</p>
              )}
            </div>
          </div>
        </div>

        {/* ─── Footer ───────────────────────────────────────── */}
        <div className="text-center border-t border-slate-100 pt-12 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
          Generated via StudyBuddy Enterprise Engine • Data Validated {new Date().toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub }: any) {
  return (
    <div className="p-6 bg-white border border-slate-200 rounded-3xl shadow-sm hover:shadow-md transition-all">
      <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center mb-4">
        {icon}
      </div>
      <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className="text-3xl font-black text-slate-900 mb-1">{value}</p>
      <p className="text-[10px] font-bold text-slate-500">{sub}</p>
    </div>
  );
}
