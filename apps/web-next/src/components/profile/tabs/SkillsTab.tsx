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

export default function SkillsTab({ ctx }: { ctx: ProfileTabCtx }) {
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
            <motion.div key="skills" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="space-y-6 pb-16">
              {/* Skill tags */}
              <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                  <Layers size={14} className="text-indigo-400" /> Technical Skills & Tags
                </h3>
                {expertiseSkills.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {expertiseSkills.map((skill: string, i: number) => (
                      <span key={i}
                        className="px-4 py-2 bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 rounded-xl text-sm font-bold">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-600 text-sm">
                    {isOwnProfile ? 'No skills added yet. Edit your profile to add skills.' : 'No skills listed.'}
                  </p>
                )}
                {isOwnProfile && (
                  <button onClick={openEdit}
                    className="mt-4 flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl text-xs font-bold border border-white/10 transition-all">
                    <Plus size={12} /> Add / Edit Skills
                  </button>
                )}
              </div>

              {/* Strength bars (if set) */}
              {strengthEntries.length > 0 && (
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                    <Star size={14} className="text-amber-400" /> Proficiency Ratings
                  </h3>
                  <div className="space-y-4">
                    {strengthEntries.map(([sk, val]: [string, any]) => (
                      <div key={sk}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-300 font-bold">{sk}</span>
                          <span className="text-indigo-400 font-black">{val}%</span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                          <motion.div className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full"
                            initial={{ width: 0 }} animate={{ width: `${val}%` }} transition={{ duration: 0.8, ease: 'easeOut' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Knowledge stack from quiz history */}
              {registry?.topic_breakdown && Object.keys(registry.topic_breakdown).length > 0 && (
                <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-5 flex items-center gap-2">
                    <BrainCircuit size={14} className="text-violet-400" /> Knowledge Stack (from Quizzes)
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(registry.topic_breakdown).map(([topic, data]: any) => (
                      <div key={topic}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-300 font-bold">{topic}</span>
                          <span className="text-indigo-400 font-black">{data.avg?.toFixed(0) ?? 0}%</span>
                        </div>
                        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-indigo-500/70 rounded-full" style={{ width: `${data.avg ?? 0}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
</>
  );
}
