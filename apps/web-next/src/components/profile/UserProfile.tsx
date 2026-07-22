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
          {activeTab === 'INSIGHTS' && (
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
          )}

          {/* ── PERFORMANCE TAB ──────────────────────────────────── */}
          {activeTab === 'PERFORMANCE' && (
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
          )}

          {/* ── SKILLS TAB ──────────────────────────────────────── */}
          {activeTab === 'SKILLS' && (
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
          )}

          {/* ── GROWTH ATLAS TAB ─────────────────────────────────── */}
          {activeTab === 'GROWTH' && (
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
          )}

          {/* ── REGISTRY TAB ─────────────────────────────────────── */}
          {activeTab === 'REGISTRY' && (
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
          )}

          {/* ── SECURITY TAB ─────────────────────────────────────── */}
          {activeTab === 'SECURITY' && isOwnProfile && (
            <motion.div key="security" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="space-y-8 pb-16">
              
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Password Management */}
                <div className="p-8 bg-slate-900/60 rounded-[2.5rem] border border-white/5 space-y-6">
                  <div className="flex items-center gap-4 mb-2">
                    <div className="w-12 h-12 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex items-center justify-center text-amber-400">
                      <Zap size={24} />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white">Change Credentials</h3>
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">Strategic Identity Rotation</p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 block">Current Access Key</label>
                      <input 
                        type="password" 
                        id="current_password"
                        placeholder="••••••••"
                        className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-amber-500 outline-none transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 block">New Access Key</label>
                      <input 
                        type="password" 
                        id="new_password"
                        placeholder="Min 8 characters"
                        className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-emerald-500 outline-none transition-colors"
                      />
                    </div>
                    <button 
                      onClick={async () => {
                        const curr = (document.getElementById('current_password') as HTMLInputElement).value;
                        const next = (document.getElementById('new_password') as HTMLInputElement).value;
                        if (!curr || !next) return toast('error', 'Both keys required for rotation.');
                        try {
                          await ApiService.changePassword(curr, next);
                          toast('success', 'Credentials rotated successfully.');
                          (document.getElementById('current_password') as HTMLInputElement).value = '';
                          (document.getElementById('new_password') as HTMLInputElement).value = '';
                        } catch (err: any) {
                          toast('error', err.message);
                        }
                      }}
                      className="w-full py-4 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-2xl font-black text-xs uppercase tracking-widest transition-all active:scale-[0.98]"
                    >
                      Apply Rotation
                    </button>
                  </div>
                </div>

                {/* Session Management */}
                <div className="p-8 bg-slate-900/60 rounded-[2.5rem] border border-white/5 space-y-6">
                  <div className="flex items-center gap-4 mb-2">
                    <div className="w-12 h-12 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-center justify-center text-rose-400">
                      <RefreshCcw size={24} />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white">Session Control</h3>
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">Global Access Revocation</p>
                    </div>
                  </div>

                  <div className="bg-rose-500/5 border border-rose-500/10 rounded-2xl p-6">
                    <p className="text-xs text-slate-400 leading-relaxed mb-6">
                      Suspicious activity detected? You can immediately revoke all active sessions across all devices. This will invalidate your current session as well.
                    </p>
                    <button 
                      onClick={async () => {
                        if (!window.confirm("CRITICAL: This will log you out of ALL devices. Continue?")) return;
                        try {
                          await ApiService.logoutAll();
                          toast('success', 'Global revocation successful. Finalizing...');
                          setTimeout(() => ApiService.logout(), 2000);
                        } catch (err: any) {
                          toast('error', err.message);
                        }
                      }}
                      className="w-full py-4 bg-rose-500/10 hover:bg-rose-500 text-rose-400 hover:text-white rounded-2xl font-black text-xs uppercase tracking-widest transition-all active:scale-[0.98]"
                    >
                      Invoke Global Logout
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'SECURITY' && !isOwnProfile && (
             <motion.div key="security-locked" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-20 text-center">
                <ShieldCheck size={48} className="text-slate-800 mx-auto mb-4" />
                <h3 className="text-slate-500 font-bold">Security protocols are restricted to the identity owner.</h3>
             </motion.div>
          )}
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
function KPICard({ label, value, icon, color = 'indigo', sub }: {
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

function Field({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-black uppercase tracking-widest text-slate-500 mb-2 block flex items-center gap-2">
        {icon} {label}
      </label>
      {children}
    </div>
  );
}
