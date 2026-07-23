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

export default function GrowthTab({ ctx }: { ctx: ProfileTabCtx }) {
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
            <motion.div key="growth" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="space-y-10 pb-16">
              
              {profile && <ExecutiveGrowthAtlas userId={profile.id} />}

              <div className="pt-8 border-t border-white/5">
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex items-center justify-center text-indigo-400">
                      <BrainCircuit size={24} />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white">Pedagogical AI Insights</h3>
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">Deep Neural Pattern Recognition</p>
                    </div>
                  </div>
                  <button 
                    disabled={generatingAtlas}
                    onClick={() => handleSyncIntel(true)}
                    className="p-3 bg-white/5 hover:bg-white/10 text-slate-500 hover:text-white rounded-xl border border-white/5 transition-all disabled:opacity-30 active:scale-95"
                    title="Force Recalibration"
                  >
                    <RefreshCw size={18} className={generatingAtlas ? 'animate-spin' : ''} />
                  </button>
                </div>

                {generatingAtlas ? (
                  <div className="p-20 flex flex-col items-center justify-center text-center bg-slate-900/40 rounded-[2.5rem] border border-white/5 border-dashed">
                    <RefreshCcw size={48} className="text-indigo-500 animate-spin mb-6" />
                    <h3 className="text-xl font-black text-white mb-2 tracking-tight">Synthesizing AI Growth Intelligence</h3>
                    <p className="text-slate-500 text-sm max-w-xs leading-relaxed">Analyzing 30+ performance vectors, learning velocity, and competency trajectories...</p>
                  </div>
                ) : growthAtlas.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {growthAtlas.map((point, i) => (
                      <motion.div key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        className="p-6 bg-slate-900/60 rounded-[1.5rem] border border-white/5 hover:border-indigo-500/30 transition-all group">
                        <div className="flex gap-4">
                          <span className="text-[10px] font-black text-indigo-500 opacity-50 mt-1">{String(i + 1).padStart(2, '0')}</span>
                          <p className="text-sm font-medium text-slate-300 leading-relaxed group-hover:text-white transition-colors">{point}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-20 text-center bg-slate-900/40 rounded-[2.5rem] border border-white/5 border-dashed">
                    <Map size={48} className="text-slate-800 mx-auto mb-6" />
                    <h3 className="text-lg font-black text-white mb-2">No Growth Atlas Generated</h3>
                    <p className="text-slate-500 text-sm mb-8">Click 'Sync Intel' to generate your 30-point pedagogical trajectory.</p>
                    <button onClick={() => handleSyncIntel()}
                      className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black text-sm transition-all shadow-lg shadow-indigo-600/20">
                      GENERATE ATLAS
                    </button>
                  </div>
                )}
              </div>
            </motion.div>
</>
  );
}
