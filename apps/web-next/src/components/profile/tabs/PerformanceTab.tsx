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

export default function PerformanceTab({ ctx }: { ctx: ProfileTabCtx }) {
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
            <motion.div key="perf" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="space-y-6 pb-16">
              {/* Extended 30-metric grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {[
                  { label: 'Total Quizzes', value: quizAttempts.length, icon: <BookOpen size={15} />, color: 'indigo' },
                  { label: 'Avg Accuracy', value: `${avgQuiz.toFixed(1)}%`, icon: <Target size={15} />, color: 'emerald' },
                  { label: 'Coding Tasks', value: codingAttempts.length, icon: <Code2 size={15} />, color: 'violet' },
                  { label: 'Best Streak', value: `${streak}d`, icon: <Flame size={15} />, color: 'amber' },
                  { label: 'Rank', value: `#${registry?.group_rank ?? '—'}`, icon: <Trophy size={15} />, color: 'amber' },
                  { label: 'Percentile', value: `${registry?.percentile ?? 0}%`, icon: <TrendingUp size={15} />, color: 'indigo' },
                  { label: 'Assignments', value: registry?.assignments_completed ?? 0, icon: <CheckCircle2 size={15} />, color: 'emerald' },
                  { label: 'Completion Rate', value: `${(registry?.completion_rate ?? 0).toFixed(0)}%`, icon: <GitBranch size={15} />, color: 'violet' },
                  { label: 'Last Active', value: profile.last_login ? new Date(profile.last_login).toLocaleDateString() : 'N/A', icon: <Clock size={15} />, color: 'indigo' },
                  { label: 'Coding Avg', value: `${avgCoding.toFixed(1)}%`, icon: <Cpu size={15} />, color: 'violet' },
                ].map((item, idx) => (
                  <React.Fragment key={idx}>
                    <KPICard label={item.label} value={item.value} icon={item.icon} color={item.color as any} />
                  </React.Fragment>
                ))}
              </div>

              {/* Recent quiz attempts table */}
              <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                  <Activity size={14} className="text-indigo-400" /> Recent Quiz Attempts
                </h3>
                <div className="space-y-2">
                  {quizAttempts.slice(0, 15).map((a: any, i: number) => {
                    const pct = a.total > 0 ? Math.round((a.score / a.total) * 100) : 0;
                    return (
                      <div key={i} className="flex items-center gap-4 p-3 hover:bg-white/[0.02] rounded-xl transition-colors">
                        <div className="w-8 text-slate-600 font-black text-xs">{i + 1}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-bold text-slate-200 truncate">{a.bank_name || 'Unknown Quiz'}</p>
                          <p className="text-[10px] text-slate-500 font-mono">{new Date(a.attempted_at).toLocaleDateString()}</p>
                        </div>
                        <div className="text-right">
                          <div className={`font-black text-sm ${pct >= 80 ? 'text-emerald-400' : pct >= 60 ? 'text-indigo-400' : 'text-rose-400'}`}>
                            {pct}%
                          </div>
                          <div className="text-[10px] text-slate-500">{a.score}/{a.total}</div>
                        </div>
                        <div className="w-20">
                          <div className="h-1.5 bg-slate-800 rounded-full">
                            <div className={`h-full rounded-full ${pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-indigo-500' : 'bg-rose-500'}`}
                              style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {quizAttempts.length === 0 && (
                    <p className="text-slate-600 text-sm text-center py-8">No quiz attempts yet</p>
                  )}
                </div>
              </div>
            </motion.div>
</>
  );
}
