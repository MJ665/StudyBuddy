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
import WizardStep0 from './wizard/WizardStep0';
import WizardStep1 from './wizard/WizardStep1';
import WizardStep2 from './wizard/WizardStep2';
import WizardStep3 from './wizard/WizardStep3';
import WizardStep4 from './wizard/WizardStep4';
import WizardStep5 from './wizard/WizardStep5';

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

  // Context handed to the extracted step components (5b decomposition).
  const wizardCtx = { currentStep, setCurrentStep, projects, mentors, loadingInitial, tagInput,
    setTagInput, coAuthorInput, setCoAuthorInput, isNewProject, setIsNewProject,
    newProjectName, setNewProjectName, editorMode, setEditorMode, isSaving,
    registries, formData, setFormData, coAuthorSearch, setCoAuthorSearch,
    coAuthorResults, setCoAuthorResults, isSearchingCoAuthors, isAILoading, next, back,
    addListItem, removeListItem, calculateCompleteness, handleFinalize,
    handleSaveDraft, handleLocalCache, handleAIAssistant,
    user, projectId, onClose, onComplete };

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
              {currentStep === 0 && <WizardStep0 ctx={wizardCtx} />}

              {currentStep === 1 && <WizardStep1 ctx={wizardCtx} />}

              {currentStep === 2 && <WizardStep2 ctx={wizardCtx} />}

              {currentStep === 3 && <WizardStep3 ctx={wizardCtx} />}

              {currentStep === 4 && <WizardStep4 ctx={wizardCtx} />}

              {currentStep === 5 && <WizardStep5 ctx={wizardCtx} />}
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



