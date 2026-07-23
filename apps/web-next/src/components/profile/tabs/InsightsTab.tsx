'use client';
/* Extracted verbatim from UserProfile.tsx (5b decomposition). State and
   handlers arrive via the ctx object assembled in UserProfile. */
/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useEffect, useState, useRef } from 'react';
import {
  User, Mail, Building2, Linkedin, Globe, Code2, Video,
  BrainCircuit, ScrollText, Map, ShieldCheck, RefreshCcw, RefreshCw, ExternalLink,
  Flame, Github, Edit3, Plus, Trash2, Link2,
  TrendingUp, TrendingDown, Award, Zap, Target, Clock, BarChart3,
  CheckCircle2, XCircle, Layers, BookOpen, Star, Trophy, Cpu, Sparkles,
  X, GitBranch
} from 'lucide-react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  Tooltip, AreaChart, Area, XAxis, YAxis,
  BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';
import ApiService, { AIResponseEnvelope } from '../../../services/ApiService';
import { motion, AnimatePresence } from 'motion/react';
import { useToast } from '../../ui/Toast';
import ActivityHeatmap from '../../common/ActivityHeatmap';
import ExecutiveGrowthAtlas from '../../dashboard/ExecutiveGrowthAtlas';
import { Activity, Camera, Save, Copy } from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Type definitions
// ─────────────────────────────────────────────────────────────────────────────
type TabId = 'INSIGHTS' | 'PERFORMANCE' | 'SKILLS' | 'GROWTH' | 'REGISTRY' | 'SECURITY';

interface ProfileEditState {
  full_name: string;
  profile_photo_url: string;
  intro_video_url: string;
  github_url: string;
  linkedin_url: string;
  leetcode_url: string;
  codolio_url: string;
  expertise_json: { skills: string[]; strengths: Record<string, number> };
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
import { KPICard, Field } from './shared';
import type { ProfileTabCtx } from './types';

export default function InsightsTab({ ctx }: { ctx: ProfileTabCtx }) {
  const { profile, registry, vectors, quizAttempts, codingAttempts, allAttempts,
    avgQuiz, avgCoding, totalAttempts, streak, weightedProficiency,
    consistencyIndex, learningVelocity, weeklyActivity, growthAtlas,
    generatingAtlas, isOwnProfile, saving, newSkill, setNewSkill, skillInputRef,
    openEdit, handleSave, addSkill, removeSkill, handlePhotoUpload,
    handleSyncIntel, setShowEditModal, setActiveTab, onBack,
    currentUserId, slug, toast, loading,
    scoreHistory, scoreDistribution, radarData, expertiseSkills, strengthEntries } = ctx;
  return (
<>
            <motion.div key="insights" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="grid grid-cols-1 xl:grid-cols-3 gap-8 pb-16">
              
              {/* Left Column: Core Charts + Insights */}
              <div className="xl:col-span-2 space-y-8">
                
                {/* Scientific Insights */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <Zap size={60} />
                    </div>
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Weighted Proficiency</p>
                    <div className="flex items-end gap-3">
                      <span className="text-4xl font-black text-white">{weightedProficiency}%</span>
                      <span className="text-[10px] font-bold text-indigo-400 mb-1.5 uppercase tracking-widest flex items-center gap-1">
                         Blend Index <Sparkles size={10} />
                      </span>
                    </div>
                    <div className="mt-4 h-1 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 transition-all" style={{ width: `${weightedProficiency}%` }} />
                    </div>
                  </div>

                  <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <Activity size={60} />
                    </div>
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Consistency Index</p>
                    <div className="flex items-end gap-3">
                      <span className="text-4xl font-black text-white">{(consistencyIndex || 0).toFixed(0)}</span>
                      <span className="text-[10px] font-bold text-emerald-400 mb-1.5 uppercase tracking-widest flex items-center gap-1">
                         Stability <ShieldCheck size={10} />
                      </span>
                    </div>
                    <div className="mt-4 h-1 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 transition-all" style={{ width: `${consistencyIndex}%` }} />
                    </div>
                  </div>

                  <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <TrendingUp size={60} />
                    </div>
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Learning Velocity</p>
                    <div className="flex items-end gap-3">
                      <span className="text-4xl font-black text-white">{((learningVelocity || 0) * 10).toFixed(1)}</span>
                      <span className="text-[10px] font-bold text-purple-400 mb-1.5 uppercase tracking-widest flex items-center gap-1">
                         Units/Day <Zap size={10} />
                      </span>
                    </div>
                    <div className="mt-4 h-1 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 transition-all" style={{ width: `${Math.min(100, learningVelocity * 10)}%` }} />
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                {/* KPI row 1 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <KPICard label="Quiz Proficiency" value={`${avgQuiz.toFixed(1)}%`} 
                    icon={<Target size={16} />} color="indigo"
                    sub={totalAttempts > 0 ? `${quizAttempts.length} quizzes` : 'No attempts'} />
                  <KPICard label="Coding Mastery" value={`${avgCoding.toFixed(1)}%`}
                    icon={<Cpu size={16} />} color="violet"
                    sub={`${codingAttempts.length} problems`} />
                  <KPICard label="Day Streak" value={`${streak}🔥`}
                    icon={<Flame size={16} />} color="amber" sub="Consecutive days" />
                  <KPICard label="Total Attempts" value={totalAttempts}
                    icon={<Activity size={16} />} color="emerald" sub="All time" />
                </div>

                {/* KPI row 2 */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <KPICard label="Best Quiz Score"
                    value={quizAttempts.length ? `${Math.max(...quizAttempts.map((a: any) => a.total > 0 ? Math.round(a.score / a.total * 100) : 0))}%` : 'N/A'}
                    icon={<Trophy size={16} />} color="amber" />
                  <KPICard label="Completion Rate"
                    value={`${(registry?.completion_rate ?? 0).toFixed(0)}%`}
                    icon={<CheckCircle2 size={16} />} color="emerald" />
                  <KPICard label="Assignments Done"
                    value={registry?.assignments_completed ?? 0}
                    icon={<BookOpen size={16} />} color="indigo" />
                </div>

                {/* Score over time */}
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                    <TrendingUp size={14} className="text-indigo-400" /> Quiz Score Trajectory (last 10)
                  </h3>
                  {scoreHistory.length > 1 ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <AreaChart data={scoreHistory}>
                        <defs>
                          <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="idx" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip
                          contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 12 }}
                          labelStyle={{ color: '#94a3b8' }} />
                        <Area type="monotone" dataKey="accuracy" stroke="#6366f1" strokeWidth={2}
                          fill="url(#scoreGrad)" dot={{ fill: '#6366f1', r: 3 }} name="Accuracy %" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-slate-600 text-sm text-center py-10">Complete more quizzes to unlock trajectory analysis</p>
                  )}
                </div>

                {/* Activity Heatmap */}
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                    <Zap size={14} className="text-amber-400" /> Activity Heatmap
                  </h3>
                  <ActivityHeatmap userId={profile.id} />
                </div>

                {/* Weekly activity bars */}
                {weeklyActivity.length > 0 && (
                  <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                      <Clock size={14} className="text-violet-400" /> Weekly Engagement
                    </h3>
                    <ResponsiveContainer width="100%" height={140}>
                      <BarChart data={weeklyActivity}>
                        <XAxis dataKey="week" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip
                          contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 12 }} />
                        <Bar dataKey="attempts" radius={[4, 4, 0, 0]} name="Attempts">
                          {weeklyActivity.map((_, i) => (
                            <Cell key={i} fill={i === weeklyActivity.length - 1 ? '#6366f1' : '#1e293b'} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Score distribution */}
                {quizAttempts.length > 0 && (
                  <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                      <Star size={14} className="text-amber-400" /> Score Distribution
                    </h3>
                    <div className="flex items-center gap-8">
                      <ResponsiveContainer width="50%" height={160}>
                        <PieChart>
                          <Pie data={scoreDistribution} dataKey="count" nameKey="range" cx="50%" cy="50%" outerRadius={60}>
                            {scoreDistribution.map((_, i) => (
                              <Cell key={i} fill={['#ef4444', '#f59e0b', '#6366f1', '#10b981'][i]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 11 }} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-2 flex-1">
                        {scoreDistribution.map((d, i) => (
                          <div key={d.range} className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2 text-slate-400">
                              <span className="w-2 h-2 rounded-full inline-block" style={{ background: ['#ef4444', '#f59e0b', '#6366f1', '#10b981'][i] }} />
                              {d.range}%
                            </span>
                            <span className="font-black text-white">{d.count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

              {/* Right: Radar + quick stats */}
              <div className="space-y-6">
                {/* Radar */}
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                    <BrainCircuit size={14} className="text-indigo-400" /> Competency Radar
                  </h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="rgba(255,255,255,0.05)" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                      <Radar name="Score" dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={2} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* Pros / Cons AI (from registry) */}
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
                    <Zap size={14} className="text-emerald-400" /> AI Strengths
                  </h3>
                  {(registry?.pros || ['Strong quiz engagement', 'Consistent learning pattern']).map((p: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-slate-300">{p}</span>
                    </div>
                  ))}
                </div>

                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
                    <TrendingDown size={14} className="text-rose-400" /> Growth Areas
                  </h3>
                  {(registry?.cons || ['Focus on coding challenges', 'Increase daily attempts']).map((c: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <XCircle size={14} className="text-rose-400 mt-0.5 flex-shrink-0" />
                      <span className="text-xs text-slate-300">{c}</span>
                    </div>
                  ))}
                </div>

                {/* Percentile rank */}
                <div className="p-6 bg-gradient-to-br from-indigo-900/30 to-slate-900/60 rounded-3xl border border-indigo-500/20">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
                    <Trophy size={14} className="text-amber-400" /> Group Rank
                  </h3>
                  <div className="text-4xl font-black text-white mb-1">
                    #{registry?.group_rank ?? '—'}
                  </div>
                  <div className="text-xs text-slate-500">of {registry?.group_size ?? '—'} members</div>
                  {registry?.percentile != null && (
                    <div className="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all"
                        style={{ width: `${registry.percentile}%` }} />
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
</>
  );
}
