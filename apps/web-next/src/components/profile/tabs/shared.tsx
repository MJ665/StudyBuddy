'use client';
/* KPICard + Field — moved verbatim from UserProfile.tsx (5b). */
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

export function KPICard({ label, value, icon, color = 'indigo', sub }: {
  label: string; value: React.ReactNode; icon?: React.ReactNode; color?: string; sub?: string;
}) {
  const colorMap: Record<string, string> = {
    indigo: 'text-indigo-400 bg-indigo-500/10',
    violet: 'text-violet-400 bg-violet-500/10',
    emerald: 'text-emerald-400 bg-emerald-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    rose: 'text-rose-400 bg-rose-500/10',
  };
  const cls = colorMap[color] || colorMap.indigo;
  return (
    <div className="p-5 bg-slate-900/60 rounded-2xl border border-white/5 hover:border-white/10 transition-all">
      {icon && (
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center mb-3 ${cls}`}>
          {icon}
        </div>
      )}
      <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">{label}</p>
      <p className={`text-2xl font-black ${cls.split(' ')[0]}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-600 font-bold mt-1">{sub}</p>}
    </div>
  );
}


export function Field({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-black uppercase tracking-widest text-slate-500 mb-2 block flex items-center gap-2">
        {icon} {label}
      </label>
      {children}
    </div>
  );
}
