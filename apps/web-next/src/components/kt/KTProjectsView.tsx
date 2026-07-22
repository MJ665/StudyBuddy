'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  FolderKanban, Plus, ArrowRight, Loader2, Sparkles, Code, 
  BookOpen, Users, CheckCircle2, AlertCircle, Trash2, Key, Copy 
} from 'lucide-react';
import ApiService from '@/services/ApiService';
import type { KTProject } from '@/types/kt';
import { useKTNavStore } from '@/stores/ktNavStore';
import { toast } from 'react-hot-toast';
import KTQuickKeyModal from './KTQuickKeyModal';

interface KTProjectsViewProps {
  user: any;
}

export default function KTProjectsView({ user }: KTProjectsViewProps) {
  const { selectedCompany, selectProject } = useKTNavStore();
  const [projects, setProjects] = useState<KTProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [clientName, setClientName] = useState('');
  const [techStackInput, setTechStackInput] = useState('');
  const [creating, setCreating] = useState(false);

  // Key Generation State
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [selectedProjectForKey, setSelectedProjectForKey] = useState<KTProject | null>(null);

  const fetchProjects = async () => {
    if (!selectedCompany) return;
    setLoading(true);
    try {
      const res = await ApiService.getKTProjects(selectedCompany.id);
      setProjects(res || []);
    } catch (err) {
      console.error('Failed to load projects:', err);
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [selectedCompany]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompany || !name.trim()) return;

    setCreating(true);
    try {
      const techStack = techStackInput
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0);

      await ApiService.createKTProject({
        name,
        company_id: selectedCompany.id,
        description: description || undefined,
        client_name: clientName || undefined,
        tech_stack: techStack,
        group_id: user.group_id || undefined,
      });

      toast.success('Project workspace added!');
      setName('');
      setDescription('');
      setClientName('');
      setTechStackInput('');
      setShowCreateModal(false);
      fetchProjects();
    } catch (err: any) {
      toast.error(err.message || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };



  // Grade generator based on knowledge coverage score
  const getGrade = (score: number) => {
    if (score >= 90) return { label: 'Grade A', color: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30' };
    if (score >= 75) return { label: 'Grade B', color: 'text-teal-400 bg-teal-950/40 border-teal-500/30' };
    if (score >= 60) return { label: 'Grade C', color: 'text-amber-400 bg-amber-950/40 border-amber-500/30' };
    return { label: 'Grade F (Critical Gaps)', color: 'text-rose-400 bg-rose-950/40 border-rose-500/30' };
  };

  const isAdmin = ['LDAdmin', 'GroupAdmin'].includes(user.role);

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar relative z-10 max-w-7xl mx-auto w-full">
      <header className="mb-12 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2 text-indigo-400">
            <Sparkles size={16} />
            <span className="text-xs font-black uppercase tracking-widest">{selectedCompany?.name} Space</span>
          </div>
          <h1 className="text-4xl font-black text-white tracking-tight">Technical Projects</h1>
          <p className="text-slate-400 text-sm mt-1 max-w-xl">
            Inspect project coverage scopes, engineering knowledge graphs, and tech stack configurations for {selectedCompany?.name}.
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3.5 rounded-2xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/20 active:scale-95 border border-indigo-500/30"
          >
            <Plus size={18} />
            <span>Create Project</span>
          </button>
        )}
      </header>

      {/* New Project Modal Overlay */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-8 max-w-xl w-full shadow-2xl relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-indigo-500/5 rounded-full blur-[60px] pointer-events-none" />
            
            <h2 className="text-2xl font-black text-white mb-2 flex items-center gap-3">
              <FolderKanban className="text-indigo-400" size={24} />
              <span>Create New Project</span>
            </h2>
            <p className="text-slate-400 text-xs mb-6">Initialize a new codebase registry container scoped to {selectedCompany?.name}.</p>

            <form onSubmit={handleCreateProject} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Project Name</label>
                <input
                  type="text"
                  placeholder="e.g. Customer Portal API"
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Description</label>
                <textarea
                  placeholder="Enter core description, system boundaries, or architecture notes..."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm resize-none"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Client / Product Owner</label>
                  <input
                    type="text"
                    placeholder="e.g. Internal Products"
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-500">Tech Stack (comma-separated)</label>
                  <input
                    type="text"
                    placeholder="e.g. Next.js, Python, FastAPI"
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                    value={techStackInput}
                    onChange={(e) => setTechStackInput(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-slate-800/40">
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white py-4 rounded-2xl font-bold transition-all shadow-xl shadow-indigo-500/25 flex items-center justify-center gap-2"
                >
                  {creating ? <Loader2 className="animate-spin" size={18} /> : 'Launch Project container'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-4 rounded-2xl font-bold transition-all border border-slate-700"
                >
                  Close
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {selectedProjectForKey && (
        <KTQuickKeyModal 
          isOpen={showKeyModal} 
          onClose={() => setShowKeyModal(false)} 
          project={selectedProjectForKey} 
        />
      )}

      {loading ? (
        <div className="h-[400px] flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="animate-spin text-indigo-500" size={36} />
            <p className="text-xs font-black uppercase tracking-widest text-slate-500">Scanning codebase indices...</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {projects.map((project) => {
            const coverage = project.knowledge_coverage_score || 0;
            const grade = getGrade(coverage);

            return (
              <div
                key={project.id}
                onClick={() => selectProject(project)}
                className="group bg-slate-900/40 hover:bg-slate-900 border border-slate-850 hover:border-slate-750 rounded-[2rem] p-8 cursor-pointer transition-all shadow-xl hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between min-h-[320px]"
              >
                {/* Visual Accent */}
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 to-teal-500 opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="space-y-4">
                  {/* Top info row */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 group-hover:bg-indigo-600/10 transition-all">
                      <FolderKanban size={24} className="text-indigo-400 group-hover:scale-110 transition-transform" />
                    </div>

                    <div className="flex items-center gap-2">
                      {isAdmin && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedProjectForKey(project);
                            setShowKeyModal(true);
                          }}
                          className="p-1.5 rounded-lg hover:bg-emerald-500/20 text-emerald-400/50 hover:text-emerald-400 border border-transparent hover:border-emerald-500/30 transition-all opacity-0 group-hover:opacity-100"
                          title="Generate Access Key"
                        >
                          <Key size={16} />
                        </button>
                      )}
                      <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full border tracking-widest ${grade.color}`}>
                        {grade.label}
                      </span>
                    </div>
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 className="text-xl font-bold text-white group-hover:text-indigo-400 transition-colors truncate">
                      {project.name}
                    </h3>
                    <p className="text-slate-400 text-xs mt-2 line-clamp-3 leading-relaxed">
                      {project.description || 'No system definition or architectural documentation has been submitted yet for this workspace container.'}
                    </p>
                  </div>

                  {/* Tech stack */}
                  {project.tech_stack && project.tech_stack.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-2">
                      {project.tech_stack.slice(0, 4).map((tech, i) => (
                        <span key={i} className="text-[10px] font-bold bg-slate-950 border border-slate-800 text-slate-400 px-2.5 py-1 rounded-xl flex items-center gap-1">
                          <Code size={10} className="text-indigo-500" />
                          {tech}
                        </span>
                      ))}
                      {project.tech_stack.length > 4 && (
                        <span className="text-[9px] font-black uppercase tracking-wider text-slate-500 py-1 px-1">
                          +{project.tech_stack.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Bottom stats row */}
                <div className="mt-8 pt-6 border-t border-slate-850 flex items-center justify-between">
                  <div className="flex items-center gap-6">
                    {/* Coverage bar preview */}
                    <div>
                      <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Knowledge Coverage</p>
                      <div className="flex items-center gap-2.5">
                        <div className="w-24 h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                          <div 
                            className="h-full bg-gradient-to-r from-indigo-500 to-teal-500" 
                            style={{ width: `${coverage}%` }}
                          />
                        </div>
                        <span className="text-xs font-bold text-white">{coverage}%</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-center">
                        <p className="text-[9px] font-black uppercase tracking-widest text-slate-500">Docs</p>
                        <p className="text-sm font-bold text-white">{project.doc_count || 0}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[9px] font-black uppercase tracking-widest text-slate-500">Ingested</p>
                        <p className="text-sm font-bold text-emerald-400">{project.ingested_doc_count || 0}</p>
                      </div>
                    </div>
                  </div>

                  <div className="w-8 h-8 rounded-full bg-slate-950 flex items-center justify-center text-slate-500 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                    <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              </div>
            );
          })}

          {projects.length === 0 && (
            <div className="col-span-2 bg-slate-900/20 border border-slate-850 rounded-[2.5rem] p-12 text-center flex flex-col items-center justify-center min-h-[300px]">
              <FolderKanban size={40} className="text-slate-700 mb-4" />
              <h3 className="text-lg font-bold text-slate-400">No Projects Found</h3>
              <p className="text-xs text-slate-500 mt-2 max-w-sm">
                Register a technical project container inside {selectedCompany?.name} to start uploading architecture and onboarding files.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
