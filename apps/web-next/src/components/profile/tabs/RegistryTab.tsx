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

export default function RegistryTab({ ctx }: { ctx: ProfileTabCtx }) {
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
            <motion.div key="registry" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="space-y-6 pb-16">
              <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                <h3 className="font-black text-white mb-6 flex items-center gap-2">
                  <ScrollText size={18} className="text-indigo-400" /> Complete Activity Audit Trail
                </h3>
                <div className="space-y-2">
                  {(allAttempts)
                    .sort((a: any, b: any) => new Date(b.attempted_at).getTime() - new Date(a.attempted_at).getTime())
                    .map((evt: any, i: number) => (
                      <div key={i} className="flex gap-4 p-4 hover:bg-white/[0.02] rounded-xl transition-colors group">
                        <div className="w-1.5 h-1.5 rounded-full bg-slate-700 group-hover:bg-indigo-500 mt-2 transition-colors flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold text-slate-300">
                            {evt.bank_name ? `Quiz: ${evt.bank_name}` : evt.question_title ? `Code: ${evt.question_title}` : 'Activity'} —  score {evt.score ?? '—'} {evt.total ? `/ ${evt.total} (${Math.round((evt.score / evt.total) * 100)}%)` : ''}
                          </p>
                          <p className="text-[10px] text-slate-500 font-bold uppercase mt-0.5">{new Date(evt.attempted_at).toLocaleString()}</p>
                        </div>
                      </div>
                    ))}
                  {allAttempts.length === 0 && (
                    <p className="text-slate-600 text-sm text-center py-12">No activity recorded yet</p>
                  )}
                </div>
              </div>
            </motion.div>
</>
  );
}
