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
import ApiService, { AIResponseEnvelope } from '../../services/ApiService';
import { motion, AnimatePresence } from 'motion/react';
import { useToast } from '../ui/Toast';
import ActivityHeatmap from '../common/ActivityHeatmap';
import ExecutiveGrowthAtlas from '../dashboard/ExecutiveGrowthAtlas';
import { Activity, Camera, Save, Copy } from 'lucide-react';
import { KPICard, Field } from './tabs/shared';
import InsightsTab from './tabs/InsightsTab';
import PerformanceTab from './tabs/PerformanceTab';
import SkillsTab from './tabs/SkillsTab';
import GrowthTab from './tabs/GrowthTab';
import RegistryTab from './tabs/RegistryTab';
import SecurityTab from './tabs/SecurityTab';

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
export default function UserProfile({
  slug,
  currentUserId,
  onBack,
  isOwnProfile = false,
}: {
  slug?: string;
  currentUserId?: number;
  onBack: () => void;
  isOwnProfile?: boolean;
}) {
  const { toast } = useToast();
  const [profile, setProfile] = useState<any>(null);
  const [registry, setRegistry] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('INSIGHTS');
  const [growthAtlas, setGrowthAtlas] = useState<string[]>([]);
  const [generatingAtlas, setGeneratingAtlas] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editState, setEditState] = useState<ProfileEditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [newSkill, setNewSkill] = useState('');
  const skillInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { fetchProfile(); }, [slug, currentUserId]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      let res: any;
      if (isOwnProfile) {
        res = await ApiService.getOwnProfile();
      } else if (slug) {
        res = await ApiService.getProfileBySlug(slug);
      } else if (currentUserId) {
        res = await ApiService.getProfileBySlug(String(currentUserId));
      } else {
        res = await ApiService.getOwnProfile();
      }
      setProfile(res);

      try {
        const profileId = res.custom_slug || res.id;
        const reg = await ApiService.getProfileRegistry(String(profileId));
        setRegistry(reg);
      } catch (err) {
        console.warn("Registry sync failed:", err);
        setRegistry(null);
      }
    } catch (err) {
      toast('error', 'Failed to load profile intelligence');
    } finally {
      setLoading(false);
    }
  };

  const openEdit = () => {
    if (!profile) return;
    const ex = profile.expertise_json || {};
    setEditState({
      full_name: profile.full_name || '',
      profile_photo_url: profile.profile_photo_url || '',
      intro_video_url: profile.intro_video_url || '',
      github_url: profile.github_url || '',
      linkedin_url: profile.linkedin_url || '',
      leetcode_url: profile.leetcode_url || '',
      codolio_url: profile.codolio_url || '',
      expertise_json: {
        skills: ex.skills || [],
        strengths: ex.strengths || {},
      },
    });
    setShowEditModal(true);
  };

  const handleSave = async () => {
    if (!editState) return;
    setSaving(true);
    try {
      const res = await ApiService.updateProfile(editState);
      setProfile((prev: any) => ({ ...prev, ...res.user, ...editState }));
      setShowEditModal(false);
      toast('success', 'Profile updated successfully');
    } catch (err: any) {
      toast('error', err.message || 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const addSkill = () => {
    if (!newSkill.trim() || !editState) return;
    if (editState.expertise_json.skills.includes(newSkill.trim())) return;
    setEditState(prev => prev ? {
      ...prev,
      expertise_json: {
        ...prev.expertise_json,
        skills: [...prev.expertise_json.skills, newSkill.trim()],
      }
    } : prev);
    setNewSkill('');
    skillInputRef.current?.focus();
  };

  const removeSkill = (skillToRemove: string) => {
    if (!editState) return;
    setEditState(prev => prev ? {
      ...prev,
      expertise_json: {
        ...prev.expertise_json,
        skills: prev.expertise_json.skills.filter(s => s !== skillToRemove)
      }
    } : prev);
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !profile) return;
    
    if (file.size > 5 * 1024 * 1024) {
      toast('error', 'Image size exceeds 5MB limit');
      return;
    }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      toast('error', 'Unsupported image format');
      return;
    }

    try {
      // Validate dimensions & crop to square using Canvas
      const img = new Image();
      img.src = URL.createObjectURL(file);
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
      });

      const size = Math.min(img.width, img.height);
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 512;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas not supported');
      
      const startX = (img.width - size) / 2;
      const startY = (img.height - size) / 2;
      
      ctx.drawImage(img, startX, startY, size, size, 0, 0, 512, 512);
      
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(b => b ? resolve(b) : reject(new Error('Canvas conversion failed')), 'image/jpeg', 0.9);
      });
      
      const processedFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", { type: 'image/jpeg' });

      const presigned = await ApiService.getProfilePresignedUpload(processedFile.name, processedFile.type);
      
      const formData = new FormData();
      Object.entries(presigned.upload_url.fields).forEach(([k, v]) => {
        formData.append(k, v as string);
      });
      formData.append('file', processedFile);

      const uploadRes = await fetch(presigned.upload_url.url, {
        method: 'POST',
        body: formData
      });
      
      if (uploadRes.ok) {
        await ApiService.updateProfile({ profile_photo_url: presigned.public_url });
        setProfile((prev: any) => ({ ...prev, profile_photo_url: presigned.public_url }));
        toast('success', 'Tactical imagery updated & optimized');
      } else {
        toast('error', 'S3 transmission rejected');
      }
    } catch (err) {
      toast('error', 'Imagery manipulation or transmission failed');
    }
  };

  const handleSyncIntel = async (force: boolean = false) => {
    if (!profile) return;
    setGeneratingAtlas(true);
    setActiveTab('GROWTH');
    try {
      const profileId = profile.custom_slug || profile.id;
      const res = await ApiService.getProfileAtlas(String(profileId), force) as AIResponseEnvelope;
      setGrowthAtlas(res.data?.atlas || (res as any).atlas || []);
      toast('success', force ? 'AI Growth Atlas recalibrated' : 'AI Growth Atlas synchronized');
    } catch {
      toast('error', 'AI Engine timed out. Please retry.');
    } finally {
      setGeneratingAtlas(false);
    }
  };

  // ─── Derived insight metrics ───────────────────────────────────────────────
  const vectors = profile?.performance_vectors;
  const quizAttempts = registry?.quiz_attempts || [];
  const codingAttempts = registry?.coding_attempts || [];
  const allAttempts = [...quizAttempts, ...codingAttempts];
  const avgQuiz = vectors?.metrics?.m02_overall_accuracy?.raw ?? registry?.averages?.quiz ?? 0;
  const avgCoding = vectors?.metrics?.m13_avg_ai_score?.raw ?? registry?.averages?.coding ?? 0;
  const totalAttempts = allAttempts.length;
  const streak = profile?.streak_count || 0;

  // ─── Scientific Metrics ──────────────────────────────────────────────────
  const weightedProficiency = Math.round((avgQuiz * 0.4) + (avgCoding * 0.6));
  const consistencyIndex = vectors?.metrics?.m18_consistency?.raw ?? Math.min(100, streak * 10);
  const learningVelocity = vectors?.metrics?.m17_velocity?.raw ?? 0;

  const weeklyActivity = React.useMemo(() => {
    const counts: Record<string, number> = {};
    allAttempts.forEach((a: any) => {
      const d = new Date(a.attempted_at);
      const wk = `W${Math.ceil(d.getDate() / 7)}`;
      counts[wk] = (counts[wk] || 0) + 1;
    });
    return Object.entries(counts).slice(-8).map(([w, v]) => ({ week: w, attempts: v }));
  }, [allAttempts]);

  const scoreHistory = React.useMemo(() =>
    quizAttempts.slice(-10).map((a: any, i: number) => ({
      idx: i + 1,
      accuracy: a.total > 0 ? Math.round((a.score / a.total) * 100) : 0,
    })), [quizAttempts]);

  const radarData = vectors?.metrics ? [
    { subject: 'Accuracy', value: vectors.metrics.m02_overall_accuracy.raw },
    { subject: 'Coding', value: vectors.metrics.m14_coding_success.raw },
    { subject: 'Consistency', value: vectors.metrics.m18_consistency.raw },
    { subject: 'Velocity', value: Math.min(100, Math.max(0, 50 + vectors.metrics.m17_velocity.raw * 5)) },
    { subject: 'Streak', value: Math.min(100, vectors.metrics.m07_streak.raw * 5) },
    { subject: 'Percentile', value: vectors.metrics.m26_percentile.raw },
  ] : [
    { subject: 'Quiz Acc.', value: avgQuiz },
    { subject: 'Code Mastery', value: avgCoding },
    { subject: 'Consistency', value: Math.min(100, streak * 10) },
    { subject: 'Attempts', value: Math.min(100, totalAttempts * 5) },
    { subject: 'Streak', value: Math.min(100, streak * 15) },
    { subject: 'Completion', value: Math.min(100, (registry?.completion_rate || 0)) },
  ];

  const scoreDistribution = React.useMemo(() => {
    const buckets: Record<string, number> = { '0-40': 0, '41-60': 0, '61-80': 0, '81-100': 0 };
    quizAttempts.forEach((a: any) => {
      const pct = a.total > 0 ? (a.score / a.total) * 100 : 0;
      if (pct <= 40) buckets['0-40']++;
      else if (pct <= 60) buckets['41-60']++;
      else if (pct <= 80) buckets['61-80']++;
      else buckets['81-100']++;
    });
    return Object.entries(buckets).map(([range, count]) => ({ range, count }));
  }, [quizAttempts]);

  if (loading) return (
    <div className="flex-1 flex items-center justify-center bg-slate-950">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-indigo-500" />
    </div>
  );

  if (!profile) return (
    <div className="p-8 text-center text-slate-500 bg-slate-950 flex-1">Profile not found</div>
  );

  const emailSlug = profile.email?.split('@')[0] ?? '';
  const initials = profile.full_name?.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) ?? '?';
  const expertise = profile.expertise_json || {};
  const expertiseSkills = Array.isArray(expertise.skills) ? expertise.skills : [];
  const strengthEntries = typeof expertise.strengths === 'object' && expertise.strengths !== null ? Object.entries(expertise.strengths) : [];

  // Helper Card Component
  const KPICard = ({ label, value, icon, color, sub }: any) => (
    <div className="p-6 bg-slate-900/60 rounded-3xl border border-white/5 flex flex-col justify-between">
      <div className="flex items-center gap-3 text-slate-400 mb-2">
        <div className={`text-${color}-400`}>{icon}</div>
        <span className="text-[10px] font-black uppercase tracking-widest">{label}</span>
      </div>
      <div className="text-2xl font-black text-white">{value}</div>
      {sub && <div className="text-[10px] text-slate-600 mt-1">{sub}</div>}
    </div>
  );

  // Context handed to the extracted tab components (5b decomposition).
  const tabCtx = { profile, registry, vectors, quizAttempts, codingAttempts,
    allAttempts, avgQuiz, avgCoding, totalAttempts, streak, weightedProficiency,
    consistencyIndex, learningVelocity, weeklyActivity, growthAtlas,
    generatingAtlas, isOwnProfile, saving, newSkill, setNewSkill, skillInputRef,
    openEdit, handleSave, addSkill, removeSkill, handlePhotoUpload,
    handleSyncIntel, setShowEditModal, setActiveTab, onBack,
    currentUserId, slug, toast, loading,
    scoreHistory, scoreDistribution, radarData, expertiseSkills, strengthEntries };

  return (
    <div className="flex-1 overflow-y-auto bg-slate-950">
      {/* ─── Hero Banner ───────────────────────────────────────────── */}
      <div className="relative">
        <div className="h-52 bg-gradient-to-r from-violet-950/60 via-indigo-900/30 to-slate-950 relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_rgba(99,102,241,0.2),transparent_60%)]" />
          <button onClick={onBack}
            className="absolute top-6 left-8 flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm font-bold"
          >
            ← Back
          </button>
          <div className="absolute top-6 right-8 flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full text-xs text-slate-400 font-mono">
            <Link2 size={12} />
            @{emailSlug}
          </div>
        </div>

        <div className="px-10 -mt-16 flex items-end justify-between flex-wrap gap-4">
          <div className="flex items-end gap-6">
            <div className="relative flex-shrink-0 cursor-pointer group" onClick={() => isOwnProfile && document.getElementById('photo-upload')?.click()}>
              <div className="w-32 h-32 rounded-3xl bg-slate-800 border-4 border-slate-950 overflow-hidden shadow-2xl relative">
                {profile.profile_photo_url ? (
                  <img src={profile.profile_photo_url} alt={profile.full_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-indigo-600 to-violet-700 text-white text-4xl font-black">
                    {initials}
                  </div>
                )}
                {isOwnProfile && (
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                    <Camera size={24} className="text-white" />
                  </div>
                )}
              </div>
              <input type="file" id="photo-upload" className="hidden" accept="image/*" onChange={handlePhotoUpload} />
              {profile.role === 'LDAdmin' && (
                <div className="absolute -top-2 -right-2 bg-indigo-500 text-white p-1.5 rounded-xl shadow-lg">
                  <ShieldCheck size={16} />
                </div>
              )}
            </div>

            <div className="pb-3 pt-16">
              <h1 className="text-3xl font-black text-white flex items-center gap-3 flex-wrap">
                {profile.full_name}
                <span className={`text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full border ${
                  profile.role === 'LDAdmin' ? 'bg-violet-500/20 border-violet-500/40 text-violet-300' :
                  profile.role === 'Mentor' ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' :
                  'bg-white/5 border-white/10 text-slate-400'
                }`}>
                  {profile.role}
                </span>
                {streak > 0 && (
                  <span className="flex items-center gap-1 text-amber-400 text-sm font-black">
                    <Flame size={16} /> {streak}d streak
                  </span>
                )}
              </h1>
              <p className="text-slate-400 text-sm flex items-center gap-3 mt-2 flex-wrap">
                <span className="flex items-center gap-1"><Mail size={13} />{profile.email}</span>
                <span className="flex items-center gap-1"><Building2 size={13} />Group {profile.group_id}</span>
              </p>
              {isOwnProfile && (
                <div className="flex items-center gap-3 bg-slate-900/50 p-2 mt-4 rounded-xl border border-white/5 w-fit">
                  <span className="text-slate-400 text-xs font-medium pl-2">Public Link:</span>
                  <code className="text-amber-400 bg-amber-400/10 px-2 py-1 rounded-md text-xs select-all">
                    {typeof window !== 'undefined' ? `${window.location.origin}/profile/${profile.id}` : `http://localhost:3000/profile/${profile.id}`}
                  </code>
                  <button 
                    onClick={() => {
                      if (typeof window !== 'undefined') {
                        navigator.clipboard.writeText(`${window.location.origin}/profile/${profile.id}`);
                        toast('success', 'Public profile link copied to clipboard');
                      }
                    }}
                    className="p-1.5 hover:bg-white/5 rounded-md text-slate-400 hover:text-white transition-colors"
                    title="Copy link"
                  >
                    <Copy size={14} />
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 pb-3 flex-wrap">
            {profile.linkedin_url && (
              <a href={profile.linkedin_url} target="_blank" rel="noopener"
                className="p-2.5 bg-white/5 hover:bg-blue-600/20 text-slate-400 hover:text-blue-400 rounded-xl border border-white/10 transition-all" title="LinkedIn">
                <Linkedin size={18} />
              </a>
            )}
            {profile.github_url && (
              <a href={profile.github_url} target="_blank" rel="noopener"
                className="p-2.5 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl border border-white/10 transition-all" title="GitHub">
                <Github size={18} />
              </a>
            )}
            {profile.leetcode_url && (
              <a href={profile.leetcode_url} target="_blank" rel="noopener"
                className="p-2.5 bg-white/5 hover:bg-amber-600/20 text-slate-400 hover:text-amber-400 rounded-xl border border-white/10 transition-all" title="LeetCode">
                <Code2 size={18} />
              </a>
            )}
            {profile.codolio_url && (
              <a href={profile.codolio_url} target="_blank" rel="noopener"
                className="p-2.5 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl border border-white/10 transition-all" title="Codolio">
                <Globe size={18} />
              </a>
            )}
            <button onClick={() => handleSyncIntel()}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black text-sm shadow-lg shadow-indigo-600/20 transition-all">
              <RefreshCcw size={15} className={generatingAtlas ? 'animate-spin' : ''} />
              SYNC INTEL
            </button>
            {isOwnProfile && (
              <button onClick={openEdit}
                className="flex items-center gap-2 px-5 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-xl font-black text-sm border border-white/10 transition-all">
                <Edit3 size={15} /> EDIT PROFILE
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ─── Intro Video (if set) ──────────────────────────────────── */}
      {profile.intro_video_url && (
        <div className="px-10 mt-8">
          <div className="rounded-3xl overflow-hidden bg-slate-900 border border-white/5 max-w-2xl">
            <div className="p-4 border-b border-white/5 flex items-center gap-2 text-slate-400 text-sm font-bold">
              <Video size={16} className="text-indigo-400" /> Introduction Video
            </div>
            <div className="aspect-video">
              {profile.intro_video_url.includes('youtube') || profile.intro_video_url.includes('youtu.be') ? (
                <iframe
                  src={profile.intro_video_url.replace('watch?v=', 'embed/').replace('youtu.be/', 'www.youtube.com/embed/')}
                  className="w-full h-full" frameBorder="0" allowFullScreen
                />
              ) : (
                <a href={profile.intro_video_url} target="_blank" rel="noopener"
                  className="flex items-center justify-center h-full gap-3 text-indigo-400 hover:text-indigo-300 transition-colors font-bold">
                  <ExternalLink size={20} /> Watch Intro Video
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Tabs ─────────────────────────────────────────────────── */}
      <div className="px-10 pt-8">
        <div className="flex gap-1 p-1 bg-slate-900/60 rounded-2xl border border-white/5 w-fit overflow-x-auto mb-8">
          {([
            { id: 'INSIGHTS', label: 'Insights', icon: <BrainCircuit size={14} /> },
            { id: 'PERFORMANCE', label: 'Performance', icon: <BarChart3 size={14} /> },
            { id: 'SKILLS', label: 'Skills & Expertise', icon: <Layers size={14} /> },
            { id: 'GROWTH', label: 'AI Growth Atlas', icon: <Map size={14} /> },
            { id: 'REGISTRY', label: 'Activity Registry', icon: <ScrollText size={14} /> },
            { id: 'SECURITY', label: 'Security & Access', icon: <ShieldCheck size={14} /> },
          ] as { id: TabId; label: string; icon: React.ReactNode }[]).map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-black text-xs transition-all whitespace-nowrap ${
                activeTab === t.id
                  ? 'bg-slate-800 text-indigo-400 shadow-xl border border-white/5'
                  : 'text-slate-500 hover:text-slate-300'
              }`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {/* ── INSIGHTS TAB ──────────────────────────────────────── */}
          {activeTab === 'INSIGHTS' && <InsightsTab ctx={tabCtx} />}

          {/* ── PERFORMANCE TAB ──────────────────────────────────── */}
          {activeTab === 'PERFORMANCE' && <PerformanceTab ctx={tabCtx} />}

          {/* ── SKILLS TAB ──────────────────────────────────────── */}
          {activeTab === 'SKILLS' && <SkillsTab ctx={tabCtx} />}

          {/* ── GROWTH ATLAS TAB ─────────────────────────────────── */}
          {activeTab === 'GROWTH' && <GrowthTab ctx={tabCtx} />}

          {/* ── REGISTRY TAB ─────────────────────────────────────── */}
          {activeTab === 'REGISTRY' && <RegistryTab ctx={tabCtx} />}

          {/* ── SECURITY TAB ─────────────────────────────────────── */}

          {activeTab === 'SECURITY' && <SecurityTab ctx={tabCtx} />}
        </AnimatePresence>
      </div>

      {/* ─── Edit Profile Modal ───────────────────────────────────── */}
      <AnimatePresence>
        {showEditModal && editState && (
          <motion.div key="modal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-2xl bg-slate-900 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between px-8 py-6 border-b border-white/5">
                <h2 className="text-xl font-black text-white flex items-center gap-3">
                  <Edit3 size={20} className="text-indigo-400" /> Edit Profile
                </h2>
                <button onClick={() => setShowEditModal(false)}
                  className="p-2 text-slate-500 hover:text-white rounded-xl hover:bg-white/5 transition-all">
                  <X size={20} />
                </button>
              </div>

              <div className="p-8 max-h-[70vh] overflow-y-auto space-y-6">
                {/* Name */}
                <Field label="Full Name" icon={<User size={14} />}>
                  <input value={editState.full_name}
                    onChange={e => setEditState(prev => prev ? { ...prev, full_name: e.target.value } : prev)}
                    className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                </Field>

                {/* Photo URL */}
                <Field label="Profile Photo URL" icon={<Camera size={14} />}>
                  <input value={editState.profile_photo_url}
                    onChange={e => setEditState(prev => prev ? { ...prev, profile_photo_url: e.target.value } : prev)}
                    placeholder="https://example.com/photo.jpg"
                    className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                </Field>

                {/* Intro video */}
                <Field label="Intro Video URL (YouTube or direct)" icon={<Video size={14} />}>
                  <input value={editState.intro_video_url}
                    onChange={e => setEditState(prev => prev ? { ...prev, intro_video_url: e.target.value } : prev)}
                    placeholder="https://youtube.com/watch?v=..."
                    className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                </Field>

                {/* Social links */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label="LinkedIn" icon={<Linkedin size={14} />}>
                    <input value={editState.linkedin_url}
                      onChange={e => setEditState(prev => prev ? { ...prev, linkedin_url: e.target.value } : prev)}
                      placeholder="https://linkedin.com/in/..."
                      className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                  </Field>
                  <Field label="GitHub" icon={<Github size={14} />}>
                    <input value={editState.github_url}
                      onChange={e => setEditState(prev => prev ? { ...prev, github_url: e.target.value } : prev)}
                      placeholder="https://github.com/..."
                      className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                  </Field>
                  <Field label="LeetCode" icon={<Code2 size={14} />}>
                    <input value={editState.leetcode_url}
                      onChange={e => setEditState(prev => prev ? { ...prev, leetcode_url: e.target.value } : prev)}
                      placeholder="https://leetcode.com/u/..."
                      className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                  </Field>
                  <Field label="Codolio" icon={<Globe size={14} />}>
                    <input value={editState.codolio_url}
                      onChange={e => setEditState(prev => prev ? { ...prev, codolio_url: e.target.value } : prev)}
                      placeholder="https://codolio.com/..."
                      className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                  </Field>
                </div>

                {/* Skills */}
                <div>
                  <label className="text-xs font-black uppercase tracking-widest text-slate-500 mb-3 block flex items-center gap-2">
                    <Layers size={14} /> Skills & Tags
                  </label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {editState.expertise_json.skills.map(skill => (
                      <span key={skill}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 rounded-xl text-sm font-bold">
                        {skill}
                        <button onClick={() => removeSkill(skill)} className="text-indigo-500 hover:text-white transition-colors">
                          <X size={12} />
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input ref={skillInputRef} value={newSkill}
                      onChange={e => setNewSkill(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                      placeholder="Add skill (press Enter)"
                      className="flex-1 bg-slate-800 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:border-indigo-500 outline-none transition-colors" />
                    <button onClick={addSkill}
                      className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black text-sm transition-all">
                      <Plus size={16} />
                    </button>
                  </div>
                </div>
              </div>

              <div className="px-8 py-5 border-t border-white/5 flex justify-end gap-3">
                <button onClick={() => setShowEditModal(false)}
                  className="px-6 py-2.5 text-slate-400 hover:text-white rounded-xl font-black text-sm border border-white/10 hover:bg-white/5 transition-all">
                  Cancel
                </button>
                <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black text-sm transition-all disabled:opacity-50">
                  {saving ? <RefreshCcw size={14} className="animate-spin" /> : <Save size={14} />}
                  {saving ? 'Saving...' : 'Save Profile'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Small Helpers ────────────────────────────────────────────────────────────

