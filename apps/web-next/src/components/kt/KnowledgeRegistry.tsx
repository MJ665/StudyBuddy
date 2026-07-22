'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  BookOpen, FileText, Search, Filter, 
  ChevronRight, Calendar, User, CheckCircle2, 
  Clock, History, MessageSquare, Star, Loader2, Plus 
} from 'lucide-react';
import ApiService from '@/services/ApiService';
import { format } from 'date-fns';
import { useKTNavStore } from '@/stores/ktNavStore';
import { useToast } from '../ui/Toast';

interface Document {
  id: string;
  title: string;
  doc_type: string;
  author_id: string | number;
  author_name?: string;
  co_author_names?: string[];
  co_author_emails?: string[];
  created_at: string;
  tags: string[];
  version: number;
  endorsement_count?: number;
  quality_score?: number;
  sprint?: string;
}

interface Project {
  id: string;
  name: string;
  doc_count: number;
  last_doc_at: string;
  documents?: Document[];
}

interface KnowledgeRegistryProps {
  onViewHistory: (docId: string) => void;
  onViewDocument: (docId: string) => void;
  onCreateDocument?: () => void;
  accessKey?: string;
}

const KnowledgeRegistry = ({ onViewHistory, onViewDocument, onCreateDocument, accessKey }: KnowledgeRegistryProps) => {
  const { toast } = useToast();
  const { 
    selectedCompany,
    selectedProject, 
    selectProject,
    selectedSprint, 
    sprintList, 
    selectSprint, 
    setSprintList 
  } = useKTNavStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [projectSearch, setProjectSearch] = useState('');

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await ApiService.getKTProjects(selectedCompany?.id);
        setProjects(data || []);
        if (!selectedProject && data && data.length > 0) {
          selectProject(data[0] as any);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchProjects();
  }, [selectedCompany?.id]);

  const handleSelectProject = async (p: Project) => {
    setLoading(true);
    try {
      const docsData = await ApiService.getKTDocuments({ project_id: p.id }, accessKey);
      setDocs(docsData || []);
      
      // Extract unique sprints and save to the store
      const sprints = Array.from(
        new Set(
          (docsData || [])
            .map((d: any) => d.sprint)
            .filter((s: string | null | undefined): s is string => typeof s === 'string' && s.trim() !== '')
        )
      ).sort() as string[];
      setSprintList(sprints);
      
      // Reset selected sprint if it's not in the new project's sprints
      if (selectedSprint && !sprints.includes(selectedSprint)) {
        selectSprint(null);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedProject) {
      handleSelectProject(selectedProject as any);
    }
  }, [selectedProject?.id]);

  const handleEndorse = async (docId: string) => {
    try {
      await ApiService.endorseKTDocument(docId);
      toast.success('Document endorsed by peer!');
      // Refresh docs
      if (selectedProject) handleSelectProject(selectedProject as any);
    } catch (err: any) {
      toast.error(err.message || 'Failed to endorse');
      console.error(err);
    }
  };

  const filteredProjects = projects.filter(p => 
    p.name.toLowerCase().includes(projectSearch.toLowerCase())
  );

  const filteredDocs = docs.filter(doc => {
    const matchesSearch = search === '' || 
      doc.title.toLowerCase().includes(search.toLowerCase()) ||
      doc.doc_type.toLowerCase().includes(search.toLowerCase()) ||
      (doc.tags && doc.tags.some(tag => tag.toLowerCase().includes(search.toLowerCase())));
      
    const matchesSprint = !selectedSprint || doc.sprint === selectedSprint;
    
    return matchesSearch && matchesSprint;
  });

  return (
    <div className="grid grid-cols-12 gap-8 h-full">
      {/* Projects Sidebar */}
      <div className="col-span-3 space-y-4">
        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input 
            type="text"
            placeholder="Search projects..."
            className="w-full pl-12 pr-4 py-3 bg-slate-900 border border-slate-800 rounded-2xl text-xs font-medium focus:border-indigo-500 transition-all outline-none text-white"
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
          />
        </div>

        <div className="space-y-2 overflow-y-auto max-h-[500px] custom-scrollbar pr-2">
          {filteredProjects.map((p) => (
            <button
              key={p.id}
              onClick={() => selectProject(p as any)}
              className={`w-full p-4 rounded-2xl flex items-center justify-between group transition-all border ${
                selectedProject?.id === p.id 
                ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400' 
                : 'bg-slate-900/50 border-slate-800 text-slate-500 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${
                  selectedProject?.id === p.id ? 'bg-indigo-500/20 border-indigo-500/30' : 'bg-slate-800 border-slate-700'
                }`}>
                  <BookOpen size={14} />
                </div>
                <div className="text-left">
                  <p className="text-[10px] font-black uppercase tracking-widest leading-none mb-1">{p.name}</p>
                  <p className="text-[9px] font-bold opacity-60">{p.doc_count} Documents</p>
                </div>
              </div>
              <ChevronRight size={14} className={`${selectedProject?.id === p.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-all`} />
            </button>
          ))}
        </div>
      </div>

      {/* Document List */}
      <div className="col-span-9 bg-slate-900/30 border border-slate-800 rounded-[2.5rem] overflow-hidden flex flex-col">
        <div className="p-8 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
          <div>
            <h3 className="text-xl font-black text-white">{selectedProject?.name || 'Knowledge Registry'}</h3>
            <p className="text-xs text-slate-500 font-medium">Browse verified organizational intelligence.</p>
          </div>
          <div className="flex items-center gap-2">
            {onCreateDocument && (
              <button 
                onClick={onCreateDocument}
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/20 active:scale-95 text-xs"
              >
                <Plus size={16} /> Create Doc
              </button>
            )}
            <button className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-slate-500 hover:text-white transition-all">
              <Filter size={18} />
            </button>
          </div>
        </div>

        {/* Document Search & Sprint Pills */}
        <div className="px-8 py-4 bg-slate-900/20 border-b border-slate-800/80 flex flex-col gap-4">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
            <input 
              type="text"
              placeholder="Search documents by title, type, or tags..."
              className="w-full pl-12 pr-4 py-3 bg-slate-950/60 border border-slate-800/80 rounded-xl text-xs font-medium focus:border-indigo-500 transition-all outline-none text-white"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {sprintList.length > 0 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
              <span className="text-[9px] font-black uppercase tracking-widest text-slate-500 mr-2 whitespace-nowrap">Sprints:</span>
              <button
                onClick={() => selectSprint(null)}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border ${
                  selectedSprint === null
                  ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.1)]'
                  : 'bg-slate-900 border-slate-800/60 text-slate-500 hover:border-slate-700'
                }`}
              >
                All Sprints
              </button>
              {sprintList.map((sprint) => (
                <button
                  key={sprint}
                  onClick={() => selectSprint(sprint)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all border whitespace-nowrap ${
                    selectedSprint === sprint
                    ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.1)]'
                    : 'bg-slate-900 border-slate-800/60 text-slate-500 hover:border-slate-700'
                  }`}
                >
                  {sprint}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="animate-spin text-indigo-500" size={32} />
            </div>
          ) : docs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center">
              <FileText size={48} className="mb-4 opacity-10" />
              <p className="text-sm font-bold uppercase tracking-widest">No documents found</p>
              <p className="text-xs mt-2">Start documenting to build your project memory.</p>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center">
              <FileText size={48} className="mb-4 opacity-10" />
              <p className="text-sm font-bold uppercase tracking-widest">No matching documents</p>
              <p className="text-xs mt-2">Adjust your search or sprint filters.</p>
            </div>
          ) : (
            filteredDocs.map((doc, i) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="group p-6 bg-slate-900 border border-slate-800 rounded-3xl hover:border-indigo-500/50 transition-all relative overflow-hidden"
              >
                <div className="flex justify-between items-start mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 border border-indigo-500/20">
                      <FileText size={20} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 text-[9px] font-black rounded border border-indigo-500/20 uppercase">
                          {doc.doc_type}
                        </span>
                        {doc.sprint && (
                          <span className="px-2 py-0.5 bg-indigo-950 text-indigo-300 text-[9px] font-black rounded border border-indigo-900 uppercase">
                            {doc.sprint}
                          </span>
                        )}
                        <span className="px-2 py-0.5 bg-slate-800 text-slate-500 text-[9px] font-black rounded border border-slate-700 uppercase">
                          v{doc.version}
                        </span>
                      </div>
                      <h4 
                        onClick={() => onViewDocument(doc.id)}
                        className="text-lg font-bold text-white group-hover:text-indigo-400 transition-colors cursor-pointer"
                      >
                        {doc.title}
                      </h4>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => onViewHistory(doc.id)}
                      className="p-3 bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-all border border-slate-700/50"
                      title="View Version History"
                    >
                      <History size={18} />
                    </button>
                    <button 
                      onClick={() => handleEndorse(doc.id)}
                      className="flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-800 text-slate-400 hover:bg-amber-500/10 hover:text-amber-500 transition-all border border-slate-700/50 font-bold text-xs"
                    >
                      <Star size={16} /> 
                      {doc.endorsement_count || 0} Endorsements
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-6 text-[10px] font-black uppercase tracking-widest text-slate-500">
                  <div className="flex items-center gap-2">
                    <User size={12} className="text-indigo-400" />
                    <span>Contributor: {doc.author_name || doc.author_id}</span>
                  </div>
                  
                  {doc.co_author_names && doc.co_author_names.length > 0 && (
                    <div className="flex items-center gap-3 border-l border-slate-800 pl-6">
                      <div className="flex -space-x-3 overflow-hidden">
                        {doc.co_author_names.map((name, idx) => (
                          <div 
                            key={idx} 
                            className="inline-block h-6 w-6 rounded-full ring-2 ring-slate-900 bg-indigo-500/20 flex items-center justify-center text-[8px] font-black text-indigo-400 border border-indigo-500/30"
                            title={`${name} (${doc.co_author_emails?.[idx] || ''})`}
                          >
                            {name.charAt(0)}
                          </div>
                        ))}
                      </div>
                      <span className="text-[9px] text-slate-500 font-bold lowercase">
                        + {doc.co_author_names.length} Co-authors
                      </span>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Calendar size={12} className="text-indigo-400" />
                    <span>{format(new Date(doc.created_at), 'MMM dd, yyyy')}</span>
                  </div>
                  <div className="flex items-center gap-2 ml-auto">
                    {doc.tags?.slice(0, 3).map(tag => (
                      <span key={tag} className="text-slate-600">#{tag}</span>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeRegistry;
