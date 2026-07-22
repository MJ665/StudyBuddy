'use client';

import React, { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useKTGateStore } from '@/stores/ktGateStore';
import { useKTNavStore } from '@/stores/ktNavStore';
import ApiService from '@/services/ApiService';

export default function KTScopedProjectView() {
  const { scopedProjectIds, scopeLabel } = useKTGateStore();
  const { selectProject, setView } = useKTNavStore();
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    Promise.all(
      scopedProjectIds.map(id => ApiService.getKTProjectDetails(id).catch(() => null))
    ).then(res => setProjects(res.filter(Boolean))).catch(console.error);
  }, [scopedProjectIds]);

  return (
    <div className="p-8 max-w-7xl mx-auto w-full">
      <div className="mb-8 p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-2xl flex items-center gap-3">
        <ShieldCheck size={20} className="text-emerald-400" />
        <div>
          <p className="text-emerald-400 font-bold text-sm">Access Key Active</p>
          <p className="text-slate-400 text-xs">{scopeLabel} — {scopedProjectIds.length} project(s) unlocked</p>
        </div>
      </div>
      
      <h2 className="text-2xl font-black text-white mb-6">Accessible Projects</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {projects.map(project => (
          <button
            key={project.id}
            onClick={() => {
              selectProject(project);
              setView('documents' as any);
            }}
            className="p-6 bg-slate-900 border border-slate-800 rounded-2xl text-left hover:border-indigo-500/50 transition-all group"
          >
            <h3 className="font-bold text-white group-hover:text-indigo-400 transition-colors">{project.name}</h3>
            <p className="text-xs text-slate-400 mt-1">{project.doc_count || 0} accessible documents</p>
            <div className="flex gap-4 mt-4">
              <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                Chat →
              </span>
              <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                Documents →
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
