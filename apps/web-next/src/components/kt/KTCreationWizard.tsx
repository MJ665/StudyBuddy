'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ChevronRight, ChevronLeft, Save, Sparkles, 
  AlertCircle, CheckCircle2, Type, Hash, 
  Terminal, Globe, Shield, Calendar, X, Plus, Eye, Edit3
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-hot-toast';
import Editor from '@monaco-editor/react';

interface WizardProps {
  user: any;
  projectId?: string;
  onClose: () => void;
  onComplete?: (data: any) => void;
}

const STEPS = [
  { id: 'identity', title: 'Identity', icon: Type },
  { id: 'people_time', title: 'People & Time', icon: Calendar },
  { id: 'intelligence', title: 'Intelligence', icon: Sparkles },
  { id: 'context', title: 'Context', icon: Globe },
  { id: 'learnings', title: 'Learnings', icon: Sparkles },
  { id: 'body', title: 'Body', icon: Terminal }
];

export default function KTCreationWizard({ user, projectId, onClose, onComplete }: WizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [projects, setProjects] = useState<any[]>([]);
  const [mentors, setMentors] = useState<any[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [tagInput, setTagInput] = useState('');
  const [coAuthorInput, setCoAuthorInput] = useState('');
  const [isNewProject, setIsNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [editorMode, setEditorMode] = useState<'edit' | 'preview'>('edit');
  const [isSaving, setIsSaving] = useState(false);
  
  const [registries, setRegistries] = useState({
    docTypes: [] as any[],
    complexities: [] as any[],
    accessLevels: [] as any[],
    sensitivities: [] as any[]
  });
  
  const [formData, setFormData] = useState({
    title: '',
    project_id: '',
    doc_type: 'architecture_decision',
    knowledge_domain: 'backend',
    client_name: '',
    department: '',
    domain_tags: [] as string[],
    
    co_author_names: [] as string[],
    co_author_emails: [] as string[],
    co_author_ids: [] as number[],
    mentor_id: null as number | null,
    date_range_start: '',
    date_range_end: '',
    sprint: '',
    milestone: '',
    
    tech_stack: [] as string[],
    tags: [] as string[],
    complexity: 'intermediate',
    access_level: 'project_only',
    sensitivity: 'medium',
    language: 'en',
    is_evergreen: false,
    
    problem_statement: '',
    decisions_made: '',
    outcome: '',
    conclusion: '',
    open_questions: '',
    lessons_learned: '',
    body_markdown: '',
  });

  const [coAuthorSearch, setCoAuthorSearch] = useState('');
  const [coAuthorResults, setCoAuthorResults] = useState<any[]>([]);
  const [isSearchingCoAuthors, setIsSearchingCoAuthors] = useState(false);
  const [isAILoading, setIsAILoading] = useState(false);

  useEffect(() => {
    // Load from local cache if exists
    const cached = localStorage.getItem('kt_draft_cache');
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setFormData(prev => ({ ...prev, ...parsed }));
      } catch (e) {
        console.warn('Failed to parse cached draft');
      }
    }

    Promise.all([
      ApiService.getKTProjects(),
      ApiService.getUsers({ role: 'Mentor' }).catch(() => ApiService.getUsers({ role: 'GroupAdmin' })),
      ApiService.getDocTypes(),
      ApiService.getComplexities(),
      ApiService.getAccessLevels(),
      ApiService.getSensitivities()
    ]).then(([projRes, mentorRes, docTypes, complexities, accessLevels, sensitivities]) => {
      setProjects(projRes || []);
      setMentors(Array.isArray(mentorRes) ? mentorRes : (mentorRes?.items || []));
      setRegistries({ docTypes, complexities, accessLevels, sensitivities });
      setFormData(prev => ({
        ...prev,
        project_id: projectId || prev.project_id || (projRes?.length > 0 ? projRes[0].id : '')
      }));
      setLoadingInitial(false);
    }).catch(err => {
      console.error('Failed to load initial data:', err);
      setLoadingInitial(false);
    });
  }, [projectId]);

  useEffect(() => {
    if (coAuthorSearch.length > 1) {
      setIsSearchingCoAuthors(true);
      const timer = setTimeout(() => {
        ApiService.searchCoAuthors(coAuthorSearch)
          .then(res => setCoAuthorResults(res || []))
          .finally(() => setIsSearchingCoAuthors(false));
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setCoAuthorResults([]);
    }
  }, [coAuthorSearch]);

  const next = () => currentStep < STEPS.length - 1 && setCurrentStep(currentStep + 1);
  const back = () => currentStep > 0 && setCurrentStep(currentStep - 1);

  const addListItem = (field: 'tech_stack' | 'tags', val: string, setInput: (v: string) => void) => {
    if (!val.trim() || (formData[field] as string[]).includes(val.trim())) return;
    
    setFormData({ ...formData, [field]: [...(formData[field] as string[]), val.trim()] });
    setInput('');
  };

  const calculateCompleteness = () => {
    const fieldsToTrack = [
      formData.title, formData.project_id, formData.doc_type,
      formData.problem_statement, formData.decisions_made, formData.outcome,
      formData.mentor_id, formData.tech_stack.length > 0
    ];
    const filledFields = fieldsToTrack.filter(f => !!f).length;
    return (filledFields / fieldsToTrack.length) * 100;
  };

  const handleFinalize = async () => {
    if (!isNewProject && !formData.project_id) {
      alert("Please select a project.");
      return;
    }
    if (isNewProject && !newProjectName.trim()) {
      alert("Please enter a project name.");
      return;
    }
    if (formData.title.trim().length < 3) {
      toast.error("Document title must be at least 3 characters.");
      return;
    }
    setIsSaving(true);
    try {
      let finalProjectId = formData.project_id;
      
      if (isNewProject && newProjectName) {
        const newProj = await ApiService.createKTProject({ name: newProjectName });
        finalProjectId = newProj.id;
        setFormData(prev => ({ ...prev, project_id: finalProjectId }));
        setIsNewProject(false);
      }

      const submissionData = {
        project_id: finalProjectId,
        title: formData.title.trim(),
        doc_type: formData.doc_type,
        knowledge_domain: formData.knowledge_domain,
        tech_stack: formData.tech_stack,
        tags: formData.tags,
        complexity: formData.complexity,
        is_evergreen: formData.is_evergreen,
        access_level: formData.access_level,
        sensitivity: formData.sensitivity,
        co_author_ids: formData.co_author_ids,
        client_name: formData.client_name || null,
        date_range_start: formData.date_range_start || null,
        date_range_end: formData.date_range_end || null,
        sprint: formData.sprint || null,
        milestone: formData.milestone || null,
        problem_statement: formData.problem_statement || null,
        decisions_made: formData.decisions_made ? [{ description: formData.decisions_made }] : [],
        outcome: formData.outcome || null,
        conclusion: formData.conclusion || null,
        open_questions: formData.open_questions ? [formData.open_questions] : [],
        lessons_learned: formData.lessons_learned ? [formData.lessons_learned] : [],
        body_markdown: formData.body_markdown || "",
        mentor_id: formData.mentor_id ? Number(formData.mentor_id) : null
      };
      
      toast.loading('Finalizing document...', { id: 'finalize-doc' });
      const doc = await ApiService.createKTDocument(submissionData);
      await ApiService.submitKTDocument(doc.id, { 
        mentor_id: formData.mentor_id ? Number(formData.mentor_id) : undefined 
      });
      toast.success('Document submitted for review!', { id: 'finalize-doc' });
      onComplete?.(doc);
    } catch (err: any) {
      console.error('Failed to finalize KT document:', err);
      toast.error(`Finalize failed: ${err.message || 'Check connection'}`, { id: 'finalize-doc' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!isNewProject && !formData.project_id) {
      toast.error("Please select a project.");
      return;
    }
    if (isNewProject && !newProjectName.trim()) {
      toast.error("Please enter a project name.");
      return;
    }
    if (!formData.title.trim()) {
      toast.error("Please enter a document title.");
      return;
    }
    if (formData.title.trim().length < 3) {
      toast.error("Document title must be at least 3 characters.");
      return;
    }
    setIsSaving(true);
    try {
      let finalProjectId = formData.project_id;
      if (isNewProject && newProjectName) {
        const newProj = await ApiService.createKTProject({ name: newProjectName });
        finalProjectId = newProj.id;
        // Update local state to avoid re-creating
        setFormData(prev => ({ ...prev, project_id: finalProjectId }));
        setIsNewProject(false);
      }

      const submissionData = {
        project_id: finalProjectId,
        title: formData.title.trim() || "Untitled Draft",
        doc_type: formData.doc_type,
        knowledge_domain: formData.knowledge_domain,
        tech_stack: formData.tech_stack,
        tags: formData.tags,
        complexity: formData.complexity,
        is_evergreen: formData.is_evergreen,
        access_level: formData.access_level,
        sensitivity: formData.sensitivity,
        language: formData.language || 'en',
        co_author_ids: formData.co_author_ids,
        client_name: formData.client_name || null,
        date_range_start: formData.date_range_start || null,
        date_range_end: formData.date_range_end || null,
        sprint: formData.sprint || null,
        milestone: formData.milestone || null,
        problem_statement: formData.problem_statement || null,
        decisions_made: formData.decisions_made ? [{ description: formData.decisions_made }] : [],
        outcome: formData.outcome || null,
        conclusion: formData.conclusion || null,
        open_questions: formData.open_questions ? [formData.open_questions] : [],
        lessons_learned: formData.lessons_learned ? [formData.lessons_learned] : [],
        body_markdown: formData.body_markdown || "",
        mentor_id: formData.mentor_id ? Number(formData.mentor_id) : null
      };

      toast.loading('Saving draft...', { id: 'save-draft' });
      const response = await ApiService.createKTDocument(submissionData);
      toast.success('Draft saved successfully! You can now request review.', { id: 'save-draft' });
      
      // Clear cache on success
      localStorage.removeItem('kt_draft_cache');
      
      if (onComplete) {
        onComplete(response);
      }
    } catch (err: any) {
      console.error('Failed to save draft:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error occurred';
      toast.error(`Draft save failed: ${errorMsg}`, { id: 'save-draft' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleLocalCache = async () => {
    try {
      toast.loading('Saving draft to server...', { id: 'save-draft' });
      await ApiService.saveKTDraft(formData);
      toast.success('Draft saved securely to server cache.', { id: 'save-draft' });
    } catch (err: any) {
      console.error('Failed to save draft:', err);
      toast.error(`Failed to save draft: ${err.message}`, { id: 'save-draft' });
      // Fallback to local storage if network fails
      localStorage.setItem('kt_draft_cache', JSON.stringify(formData));
    }
  };

  const handleAIAssistant = async () => {
    if (!formData.body_markdown.trim()) {
      alert('Please write some content first so the AI can assist you.');
      return;
    }
    
    setIsAILoading(true);
    try {
      const res = await ApiService.request('/ai/summarize', {
        method: 'POST',
        body: JSON.stringify({
          content: formData.body_markdown,
          summary_type: 'study_notes'
        })
      });
      
      if (res.ai_generated) {
        if (confirm('AI has generated suggestions for your engineering log. Would you like to append them?')) {
          setFormData(prev => ({
            ...prev,
            body_markdown: prev.body_markdown + '\n\n## AI Suggestions\n' + res.data.content
          }));
        }
      } else {
        alert(res.fallback_reason || 'AI Assistant could not generate suggestions at this time.');
      }
    } catch (err: any) {
      console.error('AI Assistant failed:', err);
      alert('AI Assistant is currently unavailable: ' + (err.message || ''));
    } finally {
      setIsAILoading(false);
    }
  };

  const removeListItem = (field: 'tech_stack' | 'tags', val: string) => {
    setFormData({ ...formData, [field]: (formData[field] as string[]).filter(v => v !== val) });
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/95 backdrop-blur-3xl">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9, y: 40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-[3rem] shadow-[0_32px_64px_-12px_rgba(0,0,0,0.8)] overflow-hidden flex flex-col h-[92vh]"
      >
        {/* ─── Wizard Header ─── */}
        <div className="p-10 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
          <div className="flex items-center gap-6">
            <div className="w-16 h-16 rounded-[2rem] bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shadow-inner">
              <Sparkles size={32} className="text-indigo-400" />
            </div>
            <div>
              <h2 className="text-3xl font-black text-white tracking-tight">Organization Memory Creator</h2>
              <div className="flex items-center gap-3 mt-1">
                <p className="text-indigo-400 text-xs font-black uppercase tracking-[0.2em]">Step {currentStep + 1} of {STEPS.length}</p>
                <div className="w-1.5 h-1.5 rounded-full bg-slate-700" />
                <p className="text-slate-400 text-sm font-bold">{STEPS[currentStep].title}</p>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white p-4 hover:bg-white/5 rounded-full transition-all group">
            <X size={28} className="group-hover:rotate-90 transition-transform duration-300" />
          </button>
        </div>

        {/* ─── Progress Bar ─── */}
        <div className="flex w-full h-1.5 bg-slate-800">
          {STEPS.map((step, i) => (
            <div 
              key={step.id}
              className={`flex-1 transition-all duration-1000 ease-out ${
                i <= currentStep ? 'bg-gradient-to-r from-indigo-500 to-fuchsia-500 shadow-[0_0_20px_rgba(99,102,241,0.6)]' : 'bg-transparent'
              }`}
            />
          ))}
        </div>

        {/* ─── Step Content ─── */}
        <div className="flex-1 overflow-y-auto p-12 custom-scrollbar">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 30, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: -30, scale: 0.98 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            >
              {currentStep === 0 && (
                <div className="space-y-12 max-w-3xl mx-auto">
                  <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">Define the Identity</h3>
                     <p className="text-slate-500 font-medium text-lg">Every document is a structured contract for organizational intelligence.</p>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Document Title</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Migration to Temporal IO for Ingestion"
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-3xl font-black tracking-tight text-white placeholder:text-slate-800 transition-all"
                      value={formData.title}
                      onChange={e => setFormData({...formData, title: e.target.value})}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between ml-1">
                        <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500">Target Project</label>
                        <button 
                          onClick={() => setIsNewProject(!isNewProject)}
                          className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          {isNewProject ? <X size={12} /> : <Plus size={12} />}
                          {isNewProject ? 'Cancel' : 'Add New'}
                        </button>
                      </div>
                      {isNewProject ? (
                        <input 
                          type="text"
                          placeholder="Project Name..."
                          className="w-full bg-slate-950/50 border border-indigo-500/30 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white"
                          value={newProjectName}
                          onChange={e => setNewProjectName(e.target.value)}
                        />
                      ) : (
                        <select 
                          className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                          value={formData.project_id}
                          onChange={e => setFormData({...formData, project_id: e.target.value})}
                        >
                          {loadingInitial ? <option>Loading projects...</option> : projects.map(p => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                      )}
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Document Type</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                        value={formData.doc_type}
                        onChange={e => setFormData({...formData, doc_type: e.target.value})}
                      >
                        {registries.docTypes.map(dt => (
                          <option key={dt.id} value={dt.id}>{dt.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Client Name</label>
                      <input 
                        type="text" 
                        placeholder="e.g. FinBank Ltd"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.client_name}
                        onChange={e => setFormData({...formData, client_name: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Department</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Backend Platform"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.department}
                        onChange={e => setFormData({...formData, department: e.target.value})}
                      />
                    </div>
                  </div>
                </div>
              )}

              {currentStep === 1 && (
                <div className="space-y-12 max-w-3xl mx-auto">
                   <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">People & Time</h3>
                     <p className="text-slate-500 font-medium text-lg">Knowledge is temporal. Defining when it was created and who verified it is crucial.</p>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="col-span-2 p-6 bg-indigo-500/5 border border-indigo-500/10 rounded-[2rem] flex items-center justify-between mb-2">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-black">
                          {user?.full_name?.charAt(0) || user?.name?.charAt(0) || 'A'}
                        </div>
                        <div>
                          <p className="text-white font-black">{user?.full_name || user?.name || 'Document Author'}</p>
                          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">You are the primary owner</p>
                        </div>
                      </div>
                      <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-4 py-2 rounded-full border border-indigo-500/20">
                        Owner
                      </span>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Assigned Mentor (Reviewer)</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                        value={formData.mentor_id || ''}
                        onChange={e => setFormData({...formData, mentor_id: e.target.value ? parseInt(e.target.value) : null})}
                      >
                        <option value="">Select a Mentor...</option>
                        {mentors.map(m => (
                          <option key={m.id} value={m.id}>{m.full_name || m.name || m.email}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Co-Authors</label>
                      <div className="relative">
                        <div className="relative">
                          <input 
                            type="text" 
                            placeholder="Search colleagues by name or email..."
                            className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                            value={coAuthorSearch}
                            onChange={e => setCoAuthorSearch(e.target.value)}
                          />
                          {isSearchingCoAuthors && (
                            <div className="absolute right-6 top-1/2 -translate-y-1/2">
                              <Sparkles className="animate-spin text-indigo-400" size={20} />
                            </div>
                          )}
                        </div>

                        {coAuthorResults.length > 0 && (
                          <div className="absolute z-10 w-full mt-2 bg-slate-900 border border-slate-800 rounded-[1.5rem] shadow-2xl overflow-hidden">
                            {coAuthorResults.map(user => (
                              <button
                                key={user.user_id}
                                onClick={() => {
                                  if (!formData.co_author_ids.includes(user.user_id)) {
                                    setFormData({
                                      ...formData,
                                      co_author_ids: [...formData.co_author_ids, user.user_id],
                                      co_author_names: [...formData.co_author_names, user.name],
                                      co_author_emails: [...formData.co_author_emails, user.email]
                                    });
                                  }
                                  setCoAuthorSearch('');
                                  setCoAuthorResults([]);
                                }}
                                className="w-full p-6 text-left hover:bg-indigo-500/10 border-b border-slate-800 last:border-0 flex justify-between items-center transition-colors group"
                              >
                                <div>
                                  <p className="text-white font-black">{user.name}</p>
                                  <p className="text-slate-500 text-xs font-bold">{user.email}</p>
                                </div>
                                {user.group_name && (
                                  <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-3 py-1 rounded-full group-hover:bg-indigo-500 group-hover:text-white transition-all">
                                    {user.group_name}
                                  </span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                        {coAuthorSearch && !isSearchingCoAuthors && coAuthorResults.length === 0 && (
                          <div className="mt-4 p-4 bg-rose-500/5 border border-rose-500/10 rounded-2xl">
                            <p className="text-rose-400 text-xs font-bold">No users found in your organization. Co-authors must be registered members.</p>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex flex-wrap gap-3 mt-6">
                        {formData.co_author_ids.map((id, i) => (
                          <div key={id} className="bg-indigo-500/10 border border-indigo-500/20 px-6 py-3 rounded-2xl flex items-center gap-3 text-indigo-400 font-black text-sm group hover:border-indigo-500 transition-all">
                            <div className="flex flex-col">
                              <span>{formData.co_author_names[i]}</span>
                              <span className="text-[10px] opacity-60">{formData.co_author_emails[i]}</span>
                            </div>
                            <button 
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  co_author_ids: formData.co_author_ids.filter((_, idx) => idx !== i),
                                  co_author_names: formData.co_author_names.filter((_, idx) => idx !== i),
                                  co_author_emails: formData.co_author_emails.filter((_, idx) => idx !== i)
                                });
                              }}
                              className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-slate-500 hover:bg-rose-500 hover:text-white transition-all"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        ))}
                        {formData.co_author_ids.length === 0 && !coAuthorSearch && (
                          <p className="text-slate-600 text-xs font-bold italic ml-2">No co-authors added yet. They will be notified via email.</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Start Date</label>
                      <input 
                        type="date" 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white cursor-pointer"
                        value={formData.date_range_start}
                        onChange={e => setFormData({...formData, date_range_start: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">End Date</label>
                      <input 
                        type="date" 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white cursor-pointer"
                        value={formData.date_range_end}
                        onChange={e => setFormData({...formData, date_range_end: e.target.value})}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Sprint</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Sprint 14-17"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.sprint}
                        onChange={e => setFormData({...formData, sprint: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Milestone</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Phase 2 Go-Live"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.milestone}
                        onChange={e => setFormData({...formData, milestone: e.target.value})}
                      />
                    </div>
                  </div>
                </div>
              )}

              {currentStep === 2 && (
                <div className="space-y-12 max-w-3xl mx-auto">
                   <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">Technicals & Intelligence</h3>
                     <p className="text-slate-500 font-medium text-lg">Tag the specific stack and access levels to ensure safe, precise retrieval.</p>
                  </div>
                  
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Technical Stack</label>
                    <div className="flex gap-4">
                      <input 
                        type="text"
                        placeholder="Add technology (e.g. Neo4j, Redis, FastAPI)..."
                        className="flex-1 bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={tagInput}
                        onChange={e => setTagInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && addListItem('tech_stack', tagInput, setTagInput)}
                      />
                      <button 
                        onClick={() => addListItem('tech_stack', tagInput, setTagInput)}
                        className="px-10 bg-indigo-600 hover:bg-indigo-500 text-white rounded-[1.5rem] font-black tracking-tight transition-all shadow-lg shadow-indigo-500/20"
                      >
                        ADD
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-3 p-8 bg-slate-950/30 border border-slate-800 rounded-[2rem] min-h-[140px] items-start content-start">
                      {formData.tech_stack.length === 0 ? (
                        <div className="m-auto text-center space-y-2 opacity-30">
                          <Terminal size={32} className="mx-auto text-slate-500" />
                          <p className="text-slate-500 text-xs font-black uppercase tracking-widest">No technologies added</p>
                        </div>
                      ) : (
                        formData.tech_stack.map(tag => (
                          <motion.span 
                            layout
                            key={tag}
                            className="px-6 py-3 bg-slate-800 border border-slate-700 rounded-2xl text-sm font-black text-slate-300 flex items-center gap-3 group hover:border-indigo-500/50 transition-all shadow-sm"
                          >
                            {tag}
                            <button onClick={() => removeListItem('tech_stack', tag)} className="text-slate-500 hover:text-rose-400 transition-colors">
                              <X size={16} />
                            </button>
                          </motion.span>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-8">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Complexity</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.complexity}
                        onChange={e => setFormData({...formData, complexity: e.target.value})}
                      >
                        {registries.complexities.map(c => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Access Level</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.access_level}
                        onChange={e => setFormData({...formData, access_level: e.target.value})}
                      >
                        {registries.accessLevels.map(a => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Sensitivity</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.sensitivity}
                        onChange={e => setFormData({...formData, sensitivity: e.target.value})}
                      >
                        {registries.sensitivities.map(s => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-8 bg-indigo-500/5 border border-indigo-500/10 rounded-[2rem]">
                    <div>
                      <h4 className="text-lg font-black text-white">Evergreen Knowledge?</h4>
                      <p className="text-slate-500 text-sm font-medium mt-1">Is this information timeless (Architecture) or time-bound (Sprint Notes)?</p>
                    </div>
                    <button 
                      onClick={() => setFormData({...formData, is_evergreen: !formData.is_evergreen})}
                      className={`w-16 h-8 rounded-full transition-all relative ${formData.is_evergreen ? 'bg-indigo-600' : 'bg-slate-800'}`}
                    >
                      <div className={`absolute top-1 w-6 h-6 rounded-full bg-white transition-all ${formData.is_evergreen ? 'left-9' : 'left-1'}`} />
                    </button>
                  </div>
                </div>
              )}

              {currentStep === 3 && (
                <div className="space-y-12 max-w-3xl mx-auto">
                   <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">Business Context</h3>
                     <p className="text-slate-500 font-medium text-lg">Summarize the 'Why', the 'What', and the 'Verdict' for quick consumption.</p>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Problem Statement</label>
                    <textarea 
                      placeholder="What were we trying to solve? e.g. Payment webhook failures during high traffic..."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.problem_statement}
                      onChange={e => setFormData({...formData, problem_statement: e.target.value})}
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Decisions Made</label>
                    <textarea 
                      placeholder="What was specifically decided? e.g. Chose Redis over Memcached because..."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.decisions_made}
                      onChange={e => setFormData({...formData, decisions_made: e.target.value})}
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Outcome & Results</label>
                    <textarea 
                      placeholder="What was built? What were the results? e.g. Reduced failure rate from 3.2% to 0.01%."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.outcome}
                      onChange={e => setFormData({...formData, outcome: e.target.value})}
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Conclusion & Verdict</label>
                    <textarea 
                      placeholder="Final takeaway for future developers..."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.conclusion}
                      onChange={e => setFormData({...formData, conclusion: e.target.value})}
                    />
                  </div>
                </div>
              )}

              {currentStep === 4 && (
                <div className="space-y-12 max-w-3xl mx-auto">
                   <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">Lessons & Open Items</h3>
                     <p className="text-slate-500 font-medium text-lg">Knowledge transfer isn't just about what worked, but what didn't and what's next.</p>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Lessons Learned</label>
                    <textarea 
                      placeholder="e.g. Always verify webhook signatures before processing. Retries must be exponential..."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.lessons_learned}
                      onChange={e => setFormData({...formData, lessons_learned: e.target.value})}
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Open Questions</label>
                    <textarea 
                      placeholder="What remains unsolved? e.g. Scaling to 10k RPS might require Sharding..."
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 h-40 font-medium text-lg leading-relaxed text-white placeholder:text-slate-800"
                      value={formData.open_questions}
                      onChange={e => setFormData({...formData, open_questions: e.target.value})}
                    />
                  </div>
                </div>
              )}

              {currentStep === 5 && (
                <div className="h-full flex flex-col space-y-6">
                  <div className="flex justify-between items-center px-4">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                        <Terminal size={20} className="text-indigo-400" />
                      </div>
                      <h4 className="text-xl font-black text-white uppercase tracking-wider">Engineering Log</h4>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex bg-slate-900/50 p-1 rounded-2xl border border-slate-800 mr-4">
                        <button 
                          onClick={() => setEditorMode('edit')}
                          className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center gap-2 ${editorMode === 'edit' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:text-white'}`}
                        >
                          <Edit3 size={14} /> WRITE
                        </button>
                        <button 
                          onClick={() => setEditorMode('preview')}
                          className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center gap-2 ${editorMode === 'preview' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:text-white'}`}
                        >
                          <Eye size={14} /> PREVIEW
                        </button>
                      </div>
                      <button 
                        onClick={handleLocalCache}
                        className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-full text-[10px] font-black border border-slate-700 transition-all flex items-center gap-2"
                      >
                        <Save size={14} /> LOCAL CACHE
                      </button>
                      <button 
                        onClick={handleAIAssistant}
                        disabled={isAILoading}
                        className={`px-6 py-2 rounded-full text-[10px] font-black transition-all flex items-center gap-2 shadow-lg ${isAILoading ? 'bg-indigo-600/50 text-white/50 cursor-not-allowed shadow-none' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20'}`}
                      >
                        {isAILoading ? (
                          <>
                            <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ANALYZING...
                          </>
                        ) : (
                          <>
                            <Sparkles size={14} /> AI ASSISTANT
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  
                    <div className="flex-1 min-h-[500px] flex gap-6">
                      {editorMode === 'edit' ? (
                        <div className="flex-1 group relative rounded-[3rem] overflow-hidden border border-slate-800 shadow-inner">
                          <Editor
                            height="100%"
                            defaultLanguage="markdown"
                            theme="vs-dark"
                            value={formData.body_markdown}
                            onChange={(val) => setFormData({ ...formData, body_markdown: val || '' })}
                            options={{
                              minimap: { enabled: false },
                              fontSize: 16,
                              fontFamily: 'JetBrains Mono, Menlo, Monaco, Courier New, monospace',
                              padding: { top: 40, bottom: 40 },
                              lineNumbers: 'on',
                              roundedSelection: true,
                              scrollBeyondLastLine: false,
                              readOnly: false,
                              cursorStyle: 'line',
                              automaticLayout: true,
                              wordWrap: 'on',
                            }}
                          />
                          <div className="absolute bottom-10 right-10 flex gap-4 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                            <div className="bg-slate-900/90 backdrop-blur-md border border-slate-800 px-6 py-3 rounded-2xl flex items-center gap-6 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                              <span className="flex items-center gap-2 text-indigo-400"><Terminal size={12} /> MONACO ENGINE</span>
                              <div className="w-1 h-1 rounded-full bg-slate-700" />
                              <span>{formData.body_markdown.split(/\s+/).filter(Boolean).length} Words</span>
                            </div>
                          </div>
                        </div>
                    ) : (
                      <div className="flex-1 bg-slate-950/80 border border-slate-800 rounded-[3rem] p-12 overflow-y-auto scrollbar-hide shadow-inner">
                        <article className="prose prose-invert prose-slate max-w-none 
                          prose-headings:font-black prose-headings:tracking-tighter prose-headings:text-white
                          prose-h1:text-5xl prose-h1:mb-8 prose-h1:bg-gradient-to-r prose-h1:from-white prose-h1:to-slate-500 prose-h1:bg-clip-text prose-h1:text-transparent
                          prose-h2:text-3xl prose-h2:mt-12 prose-h2:pb-4 prose-h2:border-b prose-h2:border-slate-800
                          prose-p:text-slate-300 prose-p:leading-relaxed prose-p:text-lg
                          prose-strong:text-white prose-strong:font-black
                          prose-code:text-indigo-400 prose-code:bg-indigo-500/10 prose-code:px-2 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none
                          prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
                          prose-img:rounded-[2rem] prose-img:border prose-img:border-slate-800
                          prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-800 prose-pre:rounded-[2rem] prose-pre:p-8
                          prose-li:text-slate-300 prose-li:marker:text-indigo-500
                          prose-blockquote:border-l-4 prose-blockquote:border-indigo-500 prose-blockquote:bg-indigo-500/5 prose-blockquote:px-8 prose-blockquote:py-1 prose-blockquote:rounded-r-2xl
                        ">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {formData.body_markdown || '*No content yet. Start writing in the editor to see it here.*'}
                          </ReactMarkdown>
                        </article>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ─── Wizard Footer ─── */}
        <div className="p-10 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center px-16">
          <button 
            onClick={back}
            disabled={currentStep === 0}
            className={`px-10 py-5 rounded-[1.5rem] font-black text-sm flex items-center gap-3 transition-all ${
              currentStep === 0 ? 'opacity-0 pointer-events-none' : 'text-slate-400 hover:text-white hover:bg-white/10 active:scale-95'
            }`}
          >
            <ChevronLeft size={22} /> PREVIOUS
          </button>
          
          <div className="flex gap-6">
            <button 
              onClick={handleSaveDraft}
              disabled={isSaving}
              className="px-10 py-5 bg-slate-800/50 hover:bg-slate-800 text-white rounded-[1.5rem] font-black text-sm flex items-center gap-3 transition-all border border-slate-700 active:scale-95 disabled:opacity-50"
            >
              {isSaving ? <Sparkles className="animate-spin" size={20} /> : <Save size={20} />} SAVE DRAFT
            </button>
            {currentStep === STEPS.length - 1 ? (
              <button 
                onClick={handleFinalize}
                disabled={isSaving}
                className="px-12 py-5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-[1.5rem] font-black text-sm flex items-center gap-3 transition-all shadow-2xl shadow-emerald-500/30 active:scale-95 ring-2 ring-emerald-500/20 disabled:opacity-50"
              >
                {isSaving ? 'FINALIZING...' : 'FINALIZE & SUBMIT'} <CheckCircle2 size={22} />
              </button>
            ) : (
              <button 
                onClick={next}
                className="px-12 py-5 bg-gradient-to-r from-indigo-600 to-fuchsia-600 hover:from-indigo-500 hover:to-fuchsia-500 text-white rounded-[1.5rem] font-black text-sm flex items-center gap-3 transition-all shadow-2xl shadow-indigo-500/30 active:scale-95 ring-2 ring-indigo-500/20"
              >
                CONTINUE <ChevronRight size={22} />
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}


