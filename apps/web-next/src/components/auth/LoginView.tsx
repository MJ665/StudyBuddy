import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Building2, 
  UserCircle2, 
  ShieldCheck, 
  ArrowRight, 
  ChevronRight, 
  History, 
  Loader2, 
  AlertCircle,
  Mail,
  Lock,
  Globe
} from 'lucide-react';
import ApiService from '../../services/ApiService';

interface LoginViewProps {
  onLoginSuccess: (user: any) => void;
  onForgotPassword: () => void;
}

export default function LoginView({ onLoginSuccess, onForgotPassword }: LoginViewProps) {
  const [groups, setGroups] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | ''>('');
  const [selectedUserId, setSelectedUserId] = useState<number | ''>('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  // View States
  const [isRegistering, setIsRegistering] = useState(false);
  const [isSuperAdminView, setIsSuperAdminView] = useState(false);

  // Hierarchy Selection for Registration
  const [orgs, setOrgs] = useState<any[]>([]);
  const [depts, setDepts] = useState<any[]>([]);
  const [verticals, setVerticals] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  
  const [selOrg, setSelOrg] = useState<number | ''>('');
  const [selDept, setSelDept] = useState<number | ''>('');
  const [selVert, setSelVert] = useState<number | ''>('');
  const [selBatch, setSelBatch] = useState<number | ''>('');

  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupPattern, setNewGroupPattern] = useState('<name>sigmoid@123');
  const [newAdminName, setNewAdminName] = useState('');
  const [newAdminEmail, setNewAdminEmail] = useState('');

  const fetchGroups = () => {
    setLoading(true);
    ApiService.getGroups()
      .then(res => setGroups(Array.isArray(res) ? res : []))
      .catch()
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchGroups();
    ApiService.getOrgs().then(res => setOrgs(res)).catch();
  }, []);

  useEffect(() => {
    if (selOrg) ApiService.getDepartments(Number(selOrg)).then(res => setDepts(res));
    else setDepts([]);
    setSelDept('');
  }, [selOrg]);

  useEffect(() => {
    if (selDept) ApiService.getVerticals(Number(selDept)).then(res => setVerticals(res));
    else setVerticals([]);
    setSelVert('');
  }, [selDept]);

  useEffect(() => {
    if (selVert) ApiService.getBatches(Number(selVert)).then(res => setBatches(res));
    else setBatches([]);
    setSelBatch('');
  }, [selVert]);

  useEffect(() => {
    if (selectedGroupId && !isRegistering && !isSuperAdminView) {
      ApiService.request(`/auth/public/groups/${selectedGroupId}/users`)
        .then((res: any) => setUsers(Array.isArray(res) ? res : []))
        .catch((err: any) => console.error(err));
    } else {
      setUsers([]);
    }
    setSelectedUserId('');
  }, [selectedGroupId, isRegistering, isSuperAdminView]);

  const handleRegisterGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!newGroupName || !newGroupPattern || !newAdminName || !newAdminEmail || !selBatch) {
      setError("Please fill all fields and select a Batch");
      return;
    }
    try {
      await ApiService.request('/auth/groups/register', {
         method: 'POST', headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ 
             name: newGroupName, 
             password_pattern: newGroupPattern,
             admin_name: newAdminName,
             admin_email: newAdminEmail,
             batch_id: selBatch
         })
      });
      setIsRegistering(false);
      fetchGroups();
    } catch (err: any) {
      setError(err.message || "Failed to register group");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (isRegistering) return handleRegisterGroup(e);
    
    if (isSuperAdminView) {
      try {
        const res = await ApiService.superAdminLogin(password);
        localStorage.setItem('study_token', res.access_token);
        onLoginSuccess(res);
      } catch (err: any) {
        setError(err.message || "Invalid L&D Access Token");
      }
      return;
    }
    
    if (!selectedGroupId || !selectedUserId || !password) {
      setError("Please fill all fields");
      return;
    }
    
    try {
      const selectedUser = users.find(u => u.id === selectedUserId);
      const res = await ApiService.login(selectedGroupId as number, selectedUser.full_name, password);
      localStorage.setItem('study_token', res.access_token);
      onLoginSuccess(res);
    } catch (err: any) {
      setError(err.message || "Invalid credentials");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
        <Loader2 className="animate-spin text-brand-primary mb-4" size={40} />
        <p className="text-slate-400 font-black uppercase tracking-[0.3em] text-xs">Synchronizing Protocol</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex font-plus-jakarta antialiased relative overflow-hidden">
      {/* ─── Background Aesthetics ─────────────────────────── */}
      <div className="absolute inset-0 z-0">
         <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-brand-primary/10 blur-[120px] rounded-full" />
         <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-indigo-500/10 blur-[150px] rounded-full" />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-8 z-10">
        <motion.div
           initial={{ opacity: 0, scale: 0.95 }}
           animate={{ opacity: 1, scale: 1 }}
           className="w-full max-w-xl bg-slate-900/40 backdrop-blur-2xl border border-white/5 rounded-[3rem] p-12 shadow-[0_32px_128px_-16px_rgba(0,0,0,0.8)]"
        >
          {/* Header */}
          <div className="text-center mb-12">
             <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-6 group hover:scale-110 transition-transform shadow-lg overflow-hidden shrink-0 border border-white/10 bg-white/5">
                <img src="/images/logo.png" alt="StudyBuddy Logo" className="w-full h-full object-cover rounded-2xl" />
             </div>
             <h1 className="text-4xl font-black text-white mb-3 tracking-tight">StudyBuddy <span className="text-brand-primary text-xl align-top">v3</span></h1>
             <p className="text-slate-500 font-bold uppercase tracking-[0.15em] text-[10px]">Enterprise L&D Orchestration Protocol</p>
          </div>

          {/* Navigation Tabs */}
          <div className="grid grid-cols-3 gap-2 bg-slate-950/50 p-2 rounded-[1.5rem] border border-white/5 mb-10">
             {[
               { id: 'member', label: 'Member', icon: UserCircle2, color: 'bg-indigo-600' },
               { id: 'ld', label: 'L&D Admin', icon: ShieldCheck, color: 'bg-rose-600' },
               { id: 'new', label: 'New Hub', icon: Building2, color: 'bg-amber-600' }
             ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setIsRegistering(tab.id === 'new');
                    setIsSuperAdminView(tab.id === 'ld');
                  }}
                  className={`flex flex-col items-center gap-2 py-4 rounded-2xl transition-all ${
                    (tab.id === 'new' && isRegistering) || 
                    (tab.id === 'ld' && isSuperAdminView) ||
                    (tab.id === 'member' && !isRegistering && !isSuperAdminView)
                      ? `${tab.color} text-white shadow-2xl`
                      : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                  }`}
                >
                   <tab.icon size={20} />
                   <span className="text-[9px] font-black uppercase tracking-widest">{tab.label}</span>
                </button>
             ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <AnimatePresence mode="wait">
              {isRegistering ? (
                 <motion.div 
                   key="register"
                   initial={{ opacity: 0, x: -20 }}
                   animate={{ opacity: 1, x: 0 }}
                   exit={{ opacity: 0, x: 20 }}
                   className="space-y-5"
                 >
                    <div className="grid grid-cols-2 gap-4">
                       <select value={selOrg} onChange={(e) => setSelOrg(e.target.value ? Number(e.target.value) : '')} className="bg-slate-950 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-2">
                          <option value="">Organization</option>
                          {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                       </select>
                       <select value={selDept} onChange={(e) => setSelDept(e.target.value ? Number(e.target.value) : '')} className="bg-slate-950 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-2" disabled={!selOrg}>
                          <option value="">Department</option>
                          {depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                       </select>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                       <select value={selVert} onChange={(e) => setSelVert(e.target.value ? Number(e.target.value) : '')} className="bg-slate-950 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-2" disabled={!selDept}>
                          <option value="">Vertical</option>
                          {verticals.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                       </select>
                       <select value={selBatch} onChange={(e) => setSelBatch(e.target.value ? Number(e.target.value) : '')} className="bg-slate-950 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-2" disabled={!selVert}>
                          <option value="">Batch</option>
                          {batches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                       </select>
                    </div>

                    <div className="relative group">
                       <input type="text" value={newGroupName} onChange={e => setNewGroupName(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 pl-12 text-sm text-white focus:ring-2 focus:ring-amber-500/50" placeholder="New Hub Name" />
                       <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-amber-500 transition-colors" size={18} />
                    </div>
                    <div className="relative group">
                       <input type="text" value={newGroupPattern} onChange={e => setNewGroupPattern(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 pl-12 text-sm text-white focus:ring-2 focus:ring-amber-500/50" />
                       <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-amber-500 transition-colors" size={18} />
                       <p className="text-[9px] text-slate-600 mt-2 italic px-1">Pattern e.g. {'<name>'}sigmoid@123</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                       <div className="relative group">
                          <input type="text" value={newAdminName} onChange={e => setNewAdminName(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 pl-12 text-sm text-white focus:ring-2" placeholder="Full Name" />
                          <UserCircle2 className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                       </div>
                       <div className="relative group">
                          <input type="email" value={newAdminEmail} onChange={e => setNewAdminEmail(e.target.value)} className="w-full bg-slate-950 border border-white/5 rounded-2xl p-4 pl-12 text-sm text-white focus:ring-2" placeholder="Email" />
                          <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                       </div>
                    </div>
                 </motion.div>
              ) : isSuperAdminView ? (
                 <motion.div 
                   key="ld-admin"
                   initial={{ opacity: 0, x: -20 }}
                   animate={{ opacity: 1, x: 0 }}
                   exit={{ opacity: 0, x: 20 }}
                   className="space-y-6"
                 >
                    <div className="bg-rose-500/5 border border-rose-500/20 rounded-3xl p-6 text-center">
                       <ShieldCheck className="mx-auto text-rose-500 mb-3" size={32} />
                       <p className="text-xs text-rose-200/60 leading-relaxed font-medium">
                          Strict hierarchy enforcement active. Enter your L&D master orchestration key to bypass standard protocol.
                       </p>
                    </div>
                    <div className="relative group">
                       <input
                         type="password"
                         placeholder="L&D Authorization Key"
                         value={password}
                         onChange={(e) => setPassword(e.target.value)}
                         className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 pl-14 text-sm text-white focus:ring-2 focus:ring-rose-600/50 tracking-[0.5em]"
                       />
                       <Lock className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-rose-500 transition-colors" size={20} />
                    </div>
                 </motion.div>
              ) : (
                 <motion.div 
                    key="login"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className="space-y-5"
                 >
                    <div className="relative group">
                       <select
                         value={selectedGroupId}
                         onChange={(e) => setSelectedGroupId(e.target.value ? Number(e.target.value) : '')}
                         className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 pl-14 text-sm text-white focus:ring-2 focus:ring-indigo-500/50 appearance-none font-bold"
                       >
                         <option value="">Operational Hub</option>
                         {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                       </select>
                       <Building2 className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-indigo-400 transition-colors" size={20} />
                    </div>

                    <AnimatePresence>
                      {selectedGroupId && (
                        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="relative group">
                           <select
                             value={selectedUserId}
                             onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : '')}
                             className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 pl-14 text-sm text-white focus:ring-2 focus:ring-indigo-500/50 appearance-none font-bold"
                           >
                             <option value="">Identity Profile</option>
                             {users.map(u => <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>)}
                           </select>
                           <UserCircle2 className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-indigo-400 transition-colors" size={20} />
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <AnimatePresence>
                     {selectedUserId && (
                        <div className="flex flex-col gap-2">
                           <div className="relative group">
                              <input
                                type="password"
                                placeholder="Security Signature"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 pl-14 text-sm text-white focus:ring-2 focus:ring-indigo-500/50"
                              />
                              <Lock className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-indigo-400 transition-colors" size={20} />
                           </div>
                           <button 
                             type="button" 
                             onClick={onForgotPassword} 
                             className="text-[10px] text-slate-500 hover:text-indigo-400 font-bold uppercase tracking-widest self-end px-2"
                           >
                             Forgot Password?
                           </button>
                        </div>
                     )}
                    </AnimatePresence>
                 </motion.div>
              )}
            </AnimatePresence>

            {error && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl">
                 <AlertCircle size={16} className="text-rose-500 shrink-0" />
                 <p className="text-[10px] font-bold text-rose-300 uppercase tracking-widest leading-none">{error}</p>
              </motion.div>
            )}

            <button
              type="submit"
              disabled={
                isRegistering ? (!newGroupName || !newAdminName || !selBatch) : 
                isSuperAdminView ? !password :
                (!selectedGroupId || !selectedUserId || !password)
              }
              className={`group w-full py-5 rounded-[1.5rem] font-black uppercase tracking-[0.2em] text-xs transition-all shadow-2xl active:scale-[0.98] ${
                isRegistering ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-900/40' : 
                isSuperAdminView ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-900/40' : 
                'bg-brand-primary text-surface-dim hover:scale-[1.02] shadow-brand-primary/20'
              } disabled:opacity-20 flex items-center justify-center gap-2`}
            >
              {isRegistering ? 'Initialize L&D Hub' : isSuperAdminView ? 'Authenticate L&D' : 'Enter Protocol'}
              <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />
            </button>
          </form>
        </motion.div>
        
         <p className="mt-12 text-[10px] text-slate-600 font-bold uppercase tracking-[0.4em] flex items-center gap-3">
            <History size={12} /> Version Control Trace 3.1.2026
         </p>
      </div>

    </div>
  );
}
