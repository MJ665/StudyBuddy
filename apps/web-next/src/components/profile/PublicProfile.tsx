'use client';

import React, { useEffect, useState } from 'react';
import { 
  User, Mail, Building2, Linkedin, Github, Code2, Globe, 
  MessageSquare, Send, ShieldCheck, Flame, Star, Trophy,
  BrainCircuit, Zap, Target, Activity, Clock, BarChart3,
  TrendingUp, Layers, BookOpen, Cpu, Sparkles, Map,
  CheckCircle2, AlertCircle, Share2, Award, ExternalLink,
  ScrollText, RefreshCw
} from 'lucide-react';
import { 
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  Tooltip, AreaChart, Area, XAxis, YAxis,
  BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';
import { motion, AnimatePresence } from 'motion/react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';
import ActivityHeatmap from '../common/ActivityHeatmap';

type TabId = 'STRATEGIC' | 'ANALYTICS' | 'REGISTRY' | 'ATLAS' | 'COMMUNITY';

export default function PublicProfile({ 
  slug, 
  onBack,
  onLoginClick,
  isLoggedIn = false
}: { 
  slug: string; 
  onBack: () => void;
  onLoginClick: () => void;
  isLoggedIn?: boolean;
}) {
  const { toast } = useToast();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('STRATEGIC');
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchProfile();
  }, [slug]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const res = await ApiService.getPublicProfile(slug);
      setProfile(res);
    } catch (err) {
      toast('error', 'Profile not found in tactical registry');
    } finally {
      setLoading(false);
    }
  };

  const handlePostComment = async () => {
    if (!isLoggedIn) {
      toast('error', 'Authentication required for feedback transmission');
      return;
    }
    if (!comment.trim()) return;

    setSubmitting(true);
    try {
      await ApiService.postProfileComment(slug, comment);
      setComment('');
      toast('success', 'Comment successfully drop-shipped to profile');
      fetchProfile(); // Refresh profile with new comments
    } catch (err) {
      toast('error', 'Transmission failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center bg-slate-950">
      <div className="relative">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-indigo-500 border-r-2 border-r-transparent" />
        <div className="absolute inset-0 flex items-center justify-center">
            <BrainCircuit size={24} className="text-indigo-500 animate-pulse" />
        </div>
      </div>
    </div>
  );

  if (!profile) return (
    <div className="flex-1 flex flex-col items-center justify-center bg-slate-950 p-8 text-center">
      <div className="w-20 h-20 bg-slate-900 rounded-full flex items-center justify-center mb-6 text-slate-700 border border-white/5">
        <User size={40} />
      </div>
      <h2 className="text-2xl font-black text-white mb-2">Registry Entry Missing</h2>
      <p className="text-slate-500 mb-8 max-w-sm">The profile you are looking for does not exist or has been decommissioned.</p>
      <button onClick={onBack} className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl font-bold border border-white/10 transition-all">
        Back to Dashboard
      </button>
    </div>
  );

  const initials = profile.full_name?.split(' ').map((n: any) => n[0]).join('').toUpperCase().slice(0, 2) ?? '?';
  const emailPrefix = profile.email?.split('@')[0] ?? '';
  const vectors = profile.vectors || {};
  const metrics = vectors.metrics || {};
  const charts = vectors.charts || {};
  const registry = profile.registry || {};
  const atlas = profile.atlas?.atlas || [];

  // Helper for KPI Cards
  const KPICard = ({ label, value, sub, icon, color }: any) => (
    <div className="p-6 bg-slate-900/40 rounded-3xl border border-white/5 hover:border-white/10 transition-all group">
      <div className={`w-10 h-10 rounded-xl bg-${color}-500/10 flex items-center justify-center text-${color}-400 mb-4 border border-${color}-500/20 group-hover:scale-110 transition-transform`}>
        {icon}
      </div>
      <div className="text-2xl font-black text-white mb-1">{value}</div>
      <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</div>
      {sub && <div className="text-[10px] text-slate-600 mt-1 font-bold">{sub}</div>}
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto bg-slate-950 text-slate-200 scroll-smooth">
      {/* ─── Hero Section ────────────────────────────────────────── */}
      <div className="relative">
        <div className="h-72 bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-950 border-b border-white/5 relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(99,102,241,0.15),transparent_70%)]" />
          <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-10" />
          
          <div className="absolute top-6 left-8 flex gap-4">
            <button onClick={onBack} className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-all rounded-xl text-xs font-black border border-white/10">
              ← BACK
            </button>
          </div>
          
          <div className="absolute top-6 right-8 flex gap-3">
             <button onClick={() => {
               navigator.clipboard.writeText(window.location.href);
               toast('success', 'Tactical profile link copied to clipboard');
             }} className="p-2.5 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-all rounded-xl border border-white/10">
                <Share2 size={18} />
             </button>
          </div>
        </div>

        <div className="px-10 -mt-24 max-w-7xl mx-auto relative z-10">
          <div className="flex flex-col md:flex-row items-end gap-8 mb-12">
            <div className="relative group">
              <div className="w-48 h-48 rounded-[3rem] bg-slate-800 border-[6px] border-slate-950 overflow-hidden shadow-2xl transition-transform group-hover:scale-[1.02]">
                {profile.profile_photo_url ? (
                  <img src={profile.profile_photo_url} alt={profile.full_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-indigo-600 to-violet-700 text-white text-6xl font-black">
                    {initials}
                  </div>
                )}
              </div>
              <div className="absolute -bottom-2 -right-2 bg-indigo-500 text-white p-3 rounded-2xl shadow-xl border-[4px] border-slate-950">
                <ShieldCheck size={24} />
              </div>
            </div>

            <div className="flex-1 pb-4">
              <div className="flex items-center gap-4 mb-4 flex-wrap">
                <h1 className="text-5xl font-black text-white tracking-tight">{profile.full_name}</h1>
                <div className="flex items-center gap-2">
                    <span className="px-4 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[10px] font-black uppercase tracking-widest text-indigo-400">
                    {profile.role}
                    </span>
                    <span className="px-4 py-1.5 bg-white/5 border border-white/10 rounded-full text-[10px] font-black uppercase tracking-widest text-slate-400">
                    {profile.hierarchy?.organization || 'Registry Organization'}
                    </span>
                    {profile.streak_count > 0 && (
                    <span className="flex items-center gap-1.5 px-4 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-full text-[10px] font-black uppercase tracking-widest text-amber-400">
                        <Flame size={14} /> {profile.streak_count}d STREAK
                    </span>
                    )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-6 text-slate-400 text-sm font-bold">
                <span className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5"><Mail size={16} className="text-indigo-400" /> {profile.email}</span>
                <span className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5"><Building2 size={16} className="text-indigo-400" /> {profile.hierarchy?.department || 'Operations'}</span>
                <span className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5"><Globe size={16} className="text-indigo-400" /> studyhub.ai/profile/{profile.custom_slug || emailPrefix}</span>
              </div>
            </div>

            <div className="flex gap-3 pb-4">
              {profile.linkedin_url && (
                <a href={profile.linkedin_url} target="_blank" rel="noopener" className="p-4 bg-white/5 hover:bg-blue-600/20 text-slate-400 hover:text-blue-400 rounded-2xl border border-white/10 transition-all shadow-lg hover:shadow-blue-600/10">
                  <Linkedin size={24} />
                </a>
              )}
              {profile.github_url && (
                <a href={profile.github_url} target="_blank" rel="noopener" className="p-4 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-2xl border border-white/10 transition-all shadow-lg">
                  <Github size={24} />
                </a>
              )}
            </div>
          </div>

          {/* ─── Navigation Tabs ────────────────────────────────────── */}
          <div className="flex gap-1 p-1.5 bg-slate-900/60 rounded-2xl border border-white/5 w-fit mb-10 overflow-x-auto">
            {([
              { id: 'STRATEGIC', label: 'STRATEGIC OVERVIEW', icon: <Target size={14} /> },
              { id: 'ANALYTICS', label: 'DEEP ANALYTICS', icon: <BarChart3 size={14} /> },
              { id: 'ATLAS', label: 'GROWTH ATLAS', icon: <Map size={14} /> },
              { id: 'REGISTRY', label: 'ACTIVITY REGISTRY', icon: <ScrollText size={14} /> },
              { id: 'COMMUNITY', label: 'COMMUNITY', icon: <MessageSquare size={14} /> },
            ] as { id: TabId; label: string; icon: any }[]).map(tab => (
              <button 
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2.5 px-6 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${
                  activeTab === tab.id 
                  ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-600/20 border border-indigo-500/50' 
                  : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.2 }}
              className="pb-24"
            >
              {/* ─── STRATEGIC TAB ──────────────────────────────────── */}
              {activeTab === 'STRATEGIC' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <div className="lg:col-span-2 space-y-8">
                    {/* Bio Section */}
                    {profile.bio && (
                      <div className="p-10 bg-slate-900/60 rounded-[2.5rem] border border-white/5 relative overflow-hidden group">
                        <div className="absolute top-0 left-0 w-1.5 h-full bg-indigo-500" />
                        <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                          <User size={14} className="text-indigo-400" /> OPERATOR BIOGRAPHY
                        </h3>
                        <p className="text-2xl text-slate-200 leading-relaxed font-medium italic">"{profile.bio}"</p>
                      </div>
                    )}

                    {/* Performance Vectors (Radar) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div className="p-8 bg-slate-900/60 rounded-[2.5rem] border border-white/5 flex flex-col items-center">
                         <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8 self-start flex items-center gap-2">
                           <BrainCircuit size={14} className="text-indigo-400" /> PROFICIENCY VECTORS
                         </h3>
                         <div className="w-full aspect-square max-w-[300px]">
                            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={charts.radar_data || []}>
                                <PolarGrid stroke="rgba(255,255,255,0.05)" />
                                <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 10, fontWeight: 900 }} />
                                <Radar
                                  name="Operator"
                                  dataKey="A"
                                  stroke="#6366f1"
                                  fill="#6366f1"
                                  fillOpacity={0.5}
                                />
                                <Tooltip contentStyle={{ background: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '12px' }} />
                              </RadarChart>
                            </ResponsiveContainer>
                         </div>
                         <div className="mt-6 text-center">
                            <div className="text-3xl font-black text-white">{charts.weighted_proficiency}%</div>
                            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Global Blend Index</div>
                         </div>
                      </div>

                      <div className="p-8 bg-slate-900/60 rounded-[2.5rem] border border-white/5">
                        <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8 flex items-center gap-2">
                          <Layers size={14} className="text-indigo-400" /> SKILL CLUSTER
                        </h3>
                        <div className="flex flex-wrap gap-3">
                          {(profile.expertise_json?.skills || []).map((s: string, i: number) => (
                            <div key={i} className="group relative">
                                <div className="absolute inset-0 bg-indigo-500/20 blur-lg opacity-0 group-hover:opacity-100 transition-opacity" />
                                <span className="relative px-4 py-2.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl text-xs font-black uppercase tracking-wider block">
                                    {s}
                                </span>
                            </div>
                          ))}
                        </div>
                        
                        <div className="mt-12 pt-12 border-t border-white/5">
                            <div className="flex items-center justify-between mb-4">
                                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Consistency Rating</span>
                                <span className="text-xs font-black text-emerald-400 uppercase">{metrics.m18b_consistency_label?.value || 'Stable'}</span>
                            </div>
                            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${metrics.m18_consistency?.raw || 70}%` }}
                                    className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400" 
                                />
                            </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-6">
                     <KPICard 
                        label="Overall Accuracy" 
                        value={metrics.m02_overall_accuracy?.value || '0%'} 
                        icon={<Target size={20} />} 
                        color="indigo" 
                        sub={`${metrics.m01_total_quiz_attempts?.raw || 0} Total Attempts`}
                     />
                     <KPICard 
                        label="Coding Mastery" 
                        value={metrics.m13_avg_ai_score?.value || '0%'} 
                        icon={<Cpu size={20} />} 
                        color="violet" 
                        sub={`${metrics.m12_coding_attempts?.raw || 0} Lab Challenges`}
                     />
                     <KPICard 
                        label="Group Percentile" 
                        value={metrics.m26_percentile?.value || 'Top 100%'} 
                        icon={<Award size={20} />} 
                        color="amber" 
                        sub={`Ranked amongst peers`}
                     />
                     
                     <div className="p-8 bg-gradient-to-br from-slate-900 to-slate-950 rounded-[2.5rem] border border-white/5">
                        <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                           <Layers size={14} className="text-indigo-400" /> TACTICAL HIERARCHY
                        </h3>
                        <div className="space-y-4">
                           <div className="flex flex-col">
                              <span className="text-[9px] font-black text-slate-600 uppercase tracking-tighter">Organization</span>
                              <span className="text-xs font-bold text-slate-200">{profile.hierarchy?.organization}</span>
                           </div>
                           <div className="flex flex-col">
                              <span className="text-[9px] font-black text-slate-600 uppercase tracking-tighter">Department</span>
                              <span className="text-xs font-bold text-slate-200">{profile.hierarchy?.department}</span>
                           </div>
                           <div className="flex flex-col">
                              <span className="text-[9px] font-black text-slate-600 uppercase tracking-tighter">Batch Registry</span>
                              <span className="text-xs font-bold text-slate-200">{profile.hierarchy?.batch}</span>
                           </div>
                           <div className="flex flex-col">
                              <span className="text-[9px] font-black text-slate-600 uppercase tracking-tighter">Tactical Group</span>
                              <span className="text-xs font-bold text-indigo-400">{profile.hierarchy?.group}</span>
                           </div>
                        </div>
                     </div>

                     <div className="p-8 bg-gradient-to-br from-slate-900 to-slate-950 rounded-[2.5rem] border border-white/5">
                        <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
                           <Activity size={14} className="text-emerald-400" /> STATUS SUMMARY
                        </h3>
                        <div className="space-y-5">
                           <div className="flex items-center justify-between">
                              <span className="text-xs text-slate-500 font-bold">Registry Status</span>
                              <span className="flex items-center gap-1.5 text-xs font-black text-emerald-400">
                                 <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> ACTIVE
                              </span>
                           </div>
                           <div className="flex items-center justify-between">
                              <span className="text-xs text-slate-500 font-bold">Risk Level</span>
                              <span className="text-xs font-black text-slate-200">{metrics.m29_risk?.value || 'On Track'}</span>
                           </div>
                           <div className="flex items-center justify-between">
                              <span className="text-xs text-slate-500 font-bold">Trajectory</span>
                              <span className="text-xs font-black text-indigo-400">{metrics.m17b_velocity_label?.value || 'Improving'}</span>
                           </div>
                        </div>
                     </div>
                  </div>
                </div>
              )}

              {/* ─── ANALYTICS TAB ──────────────────────────────────── */}
              {activeTab === 'ANALYTICS' && (
                <div className="space-y-8">
                   <div className="p-10 bg-slate-900/60 rounded-[2.5rem] border border-white/5">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8 flex items-center gap-2">
                        <Activity size={14} className="text-fuchsia-400" /> ANNUAL ENGAGEMENT REGISTRY
                      </h3>
                      <ActivityHeatmap userId={profile.id} initialData={profile.heatmap} />
                   </div>

                   <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                   <div className="p-10 bg-slate-900/60 rounded-[2.5rem] border border-white/5">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8 flex items-center gap-2">
                        <TrendingUp size={14} className="text-indigo-400" /> SCORE TRAJECTORY (LAST 7 DAYS)
                      </h3>
                      <div className="h-[300px] w-full">
                         <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                            <AreaChart data={charts.activity_trend || []}>
                               <defs>
                                  <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                                     <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                     <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                  </linearGradient>
                               </defs>
                               <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 10, fontWeight: 900 }} />
                               <YAxis axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 10 }} />
                               <Tooltip contentStyle={{ background: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '12px' }} />
                               <Area type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={3} fill="url(#chartGrad)" dot={{ r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#0f172a' }} />
                            </AreaChart>
                         </ResponsiveContainer>
                      </div>
                   </div>

                   <div className="p-10 bg-slate-900/60 rounded-[2.5rem] border border-white/5">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8 flex items-center gap-2">
                        <Zap size={14} className="text-amber-400" /> TOPIC BREADTH & MASTERY
                      </h3>
                      <div className="space-y-6">
                        {(charts.topic_mastery || []).slice(0, 5).map((t: any, i: number) => (
                           <div key={i}>
                              <div className="flex items-center justify-between mb-2">
                                 <span className="text-xs font-black text-white uppercase tracking-wider">{t.topic}</span>
                                 <div className="flex items-center gap-3">
                                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-md ${
                                       t.mastery === 'Expert' ? 'bg-emerald-500/10 text-emerald-400' :
                                       t.mastery === 'Proficient' ? 'bg-indigo-500/10 text-indigo-400' :
                                       'bg-slate-500/10 text-slate-400'
                                    }`}>
                                       {t.mastery}
                                    </span>
                                    <span className="text-xs font-bold text-slate-400">{t.avg_accuracy}%</span>
                                 </div>
                              </div>
                              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                 <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${t.avg_accuracy}%` }}
                                    className="h-full bg-indigo-500"
                                 />
                              </div>
                           </div>
                        ))}
                        {(!charts.topic_mastery || charts.topic_mastery.length === 0) && (
                           <div className="text-center py-20 text-slate-600 italic">No topic data available yet.</div>
                        )}
                      </div>
                   </div>
                </div>
              </div>
            )}

              {/* ─── ATLAS TAB ──────────────────────────────────── */}
              {activeTab === 'ATLAS' && (
                <div className="max-w-4xl mx-auto space-y-8">
                   <div className="p-12 bg-slate-900/60 rounded-[3rem] border border-white/5 relative overflow-hidden">
                      <div className="absolute top-0 right-0 p-12 opacity-5">
                         <Map size={180} className="text-indigo-500" />
                      </div>
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-10 flex items-center gap-2">
                         <Sparkles size={14} className="text-violet-400" /> AI GROWTH NARRATIVE
                      </h3>
                      <div className="space-y-12 relative z-10">
                        {atlas.map((point: string, i: number) => (
                           <motion.div 
                              key={i}
                              initial={{ opacity: 0, x: -20 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: i * 0.1 }}
                              className="flex gap-8 group"
                           >
                              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-black shrink-0 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                                 {i + 1}
                              </div>
                              <div className="pt-2">
                                 <p className="text-xl text-slate-200 leading-relaxed font-medium">{point}</p>
                              </div>
                           </motion.div>
                        ))}
                        {atlas.length === 0 && (
                           <div className="text-center py-20">
                              <BrainCircuit size={48} className="text-slate-800 mx-auto mb-6" />
                              <p className="text-slate-500 italic">The AI growth model is currently processing this operator's vectors.</p>
                           </div>
                        )}
                      </div>
                   </div>
                </div>
              )}

              {/* ─── REGISTRY TAB ──────────────────────────────────── */}
              {activeTab === 'REGISTRY' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
                   <div className="space-y-6">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                        <ScrollText size={14} className="text-indigo-400" /> QUIZ ATTEMPTS
                      </h3>
                      <div className="space-y-4">
                         {(registry.quiz_attempts || []).slice(0, 10).map((a: any) => (
                            <div key={a.id} className="p-5 bg-slate-900/40 rounded-2xl border border-white/5 flex items-center justify-between hover:bg-slate-900/60 transition-colors">
                               <div className="flex items-center gap-4">
                                  <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-indigo-400">
                                     <Code2 size={20} />
                                  </div>
                                  <div>
                                     <div className="text-sm font-bold text-white">{a.bank_name}</div>
                                     <div className="text-[10px] text-slate-500 font-black uppercase tracking-tighter">{new Date(a.attempted_at).toLocaleDateString()}</div>
                                  </div>
                               </div>
                               <div className="text-right">
                                  <div className="text-lg font-black text-indigo-400">{Math.round(a.score/a.total * 100)}%</div>
                                  <div className="text-[10px] text-slate-600 font-bold uppercase">{a.score}/{a.total}</div>
                               </div>
                            </div>
                         ))}
                         {(!registry.quiz_attempts || registry.quiz_attempts.length === 0) && (
                            <div className="text-center py-10 bg-slate-900/20 rounded-2xl border border-dashed border-white/5 text-slate-600 italic">No quiz history recorded.</div>
                         )}
                      </div>
                   </div>

                   <div className="space-y-6">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                        <Cpu size={14} className="text-violet-400" /> CODING LAB SESSIONS
                      </h3>
                      <div className="space-y-4">
                         {(registry.coding_attempts || []).slice(0, 10).map((a: any) => (
                            <div key={a.id} className="p-5 bg-slate-900/40 rounded-2xl border border-white/5 flex items-center justify-between hover:bg-slate-900/60 transition-colors">
                               <div className="flex items-center gap-4">
                                  <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-violet-400">
                                     <Zap size={20} />
                                  </div>
                                  <div>
                                     <div className="text-sm font-bold text-white">{a.question_title}</div>
                                     <div className="text-[10px] text-slate-500 font-black uppercase tracking-tighter">{new Date(a.attempted_at).toLocaleDateString()}</div>
                                  </div>
                               </div>
                               <div className="text-right">
                                  <div className="text-lg font-black text-violet-400">{a.score}%</div>
                                  <div className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">AI Audit Score</div>
                               </div>
                            </div>
                         ))}
                         {(!registry.coding_attempts || registry.coding_attempts.length === 0) && (
                            <div className="text-center py-10 bg-slate-900/20 rounded-2xl border border-dashed border-white/5 text-slate-600 italic">No coding sessions recorded.</div>
                         )}
                      </div>
                   </div>
                </div>
              )}

              {/* ─── COMMUNITY TAB ──────────────────────────────────── */}
              {activeTab === 'COMMUNITY' && (
                <div className="max-w-4xl mx-auto space-y-12">
                   <div className="space-y-6">
                      <div className="flex items-center justify-between">
                         <h3 className="text-2xl font-black text-white flex items-center gap-4">
                           <MessageSquare size={28} className="text-indigo-400" /> Professional Endorsements
                         </h3>
                         <span className="px-4 py-1.5 bg-white/5 border border-white/10 rounded-full text-xs font-black text-slate-400">
                            {profile.comments?.length || 0} CONTRIBUTIONS
                         </span>
                      </div>

                      <div className="bg-slate-900/60 rounded-[2.5rem] border border-white/5 p-10">
                        {isLoggedIn ? (
                          <div className="space-y-6">
                            <div className="relative group">
                              <textarea
                                value={comment}
                                onChange={(e) => setComment(e.target.value)}
                                placeholder="Provide a professional assessment or drop a word of encouragement..."
                                className="w-full bg-slate-800/40 border border-white/5 rounded-3xl p-8 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 transition-all resize-none h-40 text-lg"
                              />
                              <div className="absolute inset-0 bg-indigo-500/5 rounded-3xl opacity-0 group-focus-within:opacity-100 pointer-events-none transition-opacity" />
                            </div>
                            <div className="flex items-center justify-between">
                               <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">Signed interaction via secure registry</p>
                               <button 
                                onClick={handlePostComment}
                                disabled={submitting || !comment.trim()}
                                className="flex items-center gap-3 px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-black shadow-2xl shadow-indigo-600/30 transition-all disabled:opacity-50 hover:scale-[1.02] active:scale-95"
                               >
                                {submitting ? <RefreshCw size={20} className="animate-spin" /> : <Send size={20} />}
                                POST ENDORSEMENT
                               </button>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-10 bg-slate-800/20 rounded-3xl border border-dashed border-white/10">
                             <AlertCircle size={40} className="text-slate-700 mx-auto mb-4" />
                             <h4 className="text-lg font-black text-white mb-2">AUTHENTICATION GATED</h4>
                             <p className="text-slate-500 mb-8 max-w-sm mx-auto">Only verified members of the StudyBuddy registry can drop professional endorsements.</p>
                             <button onClick={onLoginClick} className="px-10 py-4 bg-white text-slate-950 rounded-2xl font-black text-sm hover:bg-indigo-400 transition-all">
                                LOGIN TO SYSTEM
                             </button>
                          </div>
                        )}
                      </div>

                      <div className="space-y-6 mt-12">
                         {profile.comments?.map((c: any) => (
                           <motion.div 
                             key={c.id}
                             initial={{ opacity: 0, y: 15 }}
                             animate={{ opacity: 1, y: 0 }}
                             className="p-8 bg-slate-900/40 rounded-[2rem] border border-white/5 hover:border-white/10 transition-all flex gap-6 group"
                           >
                             <div className="w-16 h-16 rounded-2xl bg-slate-800 flex-shrink-0 overflow-hidden border border-white/10 relative">
                               {c.author.profile_photo_url ? (
                                 <img src={c.author.profile_photo_url} className="w-full h-full object-cover" />
                               ) : (
                                 <div className="w-full h-full flex items-center justify-center bg-indigo-900/30 text-indigo-400 text-xl font-black uppercase">
                                   {c.author.full_name[0]}
                                 </div>
                               )}
                               <div className="absolute inset-0 border border-white/10 rounded-2xl pointer-events-none" />
                             </div>
                             <div className="flex-1 min-w-0">
                               <div className="flex items-center justify-between mb-3">
                                  <div>
                                     <h4 className="font-black text-white group-hover:text-indigo-400 transition-colors">@{c.author.email_prefix}</h4>
                                     <p className="text-[10px] text-slate-600 font-black uppercase tracking-tighter">Verified Collaborator</p>
                                  </div>
                                  <span className="text-[10px] text-slate-500 font-black bg-white/5 px-2 py-1 rounded-md">{new Date(c.created_at).toLocaleDateString()}</span>
                               </div>
                               <p className="text-slate-300 text-lg leading-relaxed">{c.content}</p>
                             </div>
                           </motion.div>
                         ))}
                         {(!profile.comments || profile.comments.length === 0) && (
                            <div className="text-center py-24 border-4 border-dashed border-white/5 rounded-[3rem]">
                               <MessageSquare size={48} className="text-slate-800 mx-auto mb-6" />
                               <p className="text-slate-600 font-bold italic">This profile hasn't received any professional endorsements yet.</p>
                            </div>
                         )}
                      </div>
                   </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
