'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Building2, Plus, ArrowRight, Loader2, Sparkles, Globe } from 'lucide-react';
import ApiService from '@/services/ApiService';
import type { KTCompany } from '@/types/kt';
import { useKTNavStore } from '@/stores/ktNavStore';
import { toast } from 'react-hot-toast';

interface KTCompanySelectorViewProps {
  user: any;
}

export default function KTCompanySelectorView({ user }: KTCompanySelectorViewProps) {
  const { selectCompany } = useKTNavStore();
  const [companies, setCompanies] = useState<KTCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newCompanyDomain, setNewCompanyDomain] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchCompanies = async () => {
    setLoading(true);
    try {
      const res = await ApiService.listKTCompanies();
      setCompanies(res || []);
    } catch (err) {
      console.error('Failed to load companies:', err);
      toast.error('Failed to load companies grid');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompanyName.trim()) return;

    setCreating(true);
    try {
      await ApiService.createKTCompany({
        name: newCompanyName,
        domain: newCompanyDomain || undefined,
      });
      toast.success('Workspace space created successfully!');
      setNewCompanyName('');
      setNewCompanyDomain('');
      setShowCreateForm(false);
      fetchCompanies();
    } catch (err: any) {
      toast.error(err.message || 'Failed to create company');
    } finally {
      setCreating(false);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08
      }
    }
  } as const;

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 100, damping: 15 } }
  } as const;

  const isAdmin = ['LDAdmin', 'GroupAdmin'].includes(user.role);

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar relative z-10 max-w-7xl mx-auto w-full">
      {/* Header Banner */}
      <header className="mb-12 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2 text-indigo-400">
            <Sparkles size={16} />
            <span className="text-xs font-black uppercase tracking-widest">Knowledge Hub</span>
          </div>
          <h1 className="text-4xl font-black text-white tracking-tight">Select Knowledge Base</h1>
          <p className="text-slate-400 text-sm mt-1 max-w-xl">
            Choose a corporate domain workspace to explore technical projects, run graph queries, and verify knowledge coverage.
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3.5 rounded-2xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/20 active:scale-95 border border-indigo-500/30"
          >
            <Plus size={18} />
            <span>Create Domain</span>
          </button>
        )}
      </header>

      {/* Creation Modal / Form Card */}
      {showCreateForm && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-slate-900 border border-slate-800 rounded-[2rem] p-8 mb-10 shadow-2xl relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/5 rounded-full blur-[80px] pointer-events-none" />
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
            <Building2 className="text-indigo-400" size={20} />
            <span>Create New Corporate Workspace</span>
          </h2>
          <form onSubmit={handleCreateCompany} className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
            <div className="space-y-2">
              <label className="text-xs font-black uppercase tracking-widest text-slate-500">Company Name</label>
              <input
                type="text"
                placeholder="e.g. Acme Corp"
                className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                value={newCompanyName}
                onChange={(e) => setNewCompanyName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-black uppercase tracking-widest text-slate-500">Domain Filter (Optional)</label>
              <input
                type="text"
                placeholder="e.g. acme.com"
                className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm font-mono"
                value={newCompanyDomain}
                onChange={(e) => setNewCompanyDomain(e.target.value)}
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={creating}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white py-3.5 rounded-2xl font-bold transition-all shadow-lg shadow-indigo-500/10 flex items-center justify-center gap-2 text-sm"
              >
                {creating ? <Loader2 className="animate-spin" size={16} /> : 'Save Domain'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-3.5 rounded-2xl font-bold transition-all border border-slate-700 text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        </motion.div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="h-[400px] flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="animate-spin text-indigo-500" size={36} />
            <p className="text-xs font-black uppercase tracking-widest text-slate-500">Fetching corporate registry...</p>
          </div>
        </div>
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {companies.map((company) => (
            <motion.div
              key={company.id}
              variants={cardVariants}
              onClick={() => selectCompany(company)}
              className="group bg-slate-900/40 hover:bg-slate-900 border border-slate-850 hover:border-slate-750 rounded-[2rem] p-8 cursor-pointer transition-all shadow-xl hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between h-64"
            >
              {/* Card top banner */}
              <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-indigo-500 to-violet-600 opacity-0 group-hover:opacity-100 transition-opacity" />
              
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 group-hover:bg-indigo-600/10 transition-colors">
                  <Building2 size={24} className="text-indigo-400 group-hover:scale-110 transition-transform" />
                </div>
                
                <div>
                  <h3 className="text-xl font-bold text-white group-hover:text-indigo-400 transition-colors truncate">{company.name}</h3>
                  <div className="flex items-center gap-1.5 mt-2 text-slate-500">
                    <Globe size={12} />
                    <span className="text-xs font-mono">{company.domain || 'no domain lock'}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-800/40">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500 group-hover:text-slate-400 transition-colors">
                  Access Space
                </span>
                <div className="w-8 h-8 rounded-full bg-slate-950 flex items-center justify-center text-slate-500 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                  <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                </div>
              </div>
            </motion.div>
          ))}

          {companies.length === 0 && (
            <div className="col-span-full bg-slate-900/25 border border-slate-850 rounded-[2rem] p-12 text-center flex flex-col items-center justify-center min-h-[300px]">
              <Building2 size={40} className="text-slate-700 mb-4" />
              <h3 className="text-lg font-bold text-slate-400">No Domains Registered</h3>
              <p className="text-xs text-slate-500 mt-2 max-w-sm">
                Get started by creating your first corporate domain workspace to manage knowledge assets.
              </p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
