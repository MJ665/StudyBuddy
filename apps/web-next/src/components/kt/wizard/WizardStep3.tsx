'use client';
/* Extracted verbatim from KTCreationWizard.tsx (5b decomposition). State
   and handlers arrive via the ctx object assembled in the wizard shell. */
/* eslint-disable @typescript-eslint/no-unused-vars */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ChevronRight, ChevronLeft, Save, Sparkles, 
  AlertCircle, CheckCircle2, Type, Hash, 
  Terminal, Globe, Shield, Calendar, X, Plus, Eye, Edit3
} from 'lucide-react';
import ApiService from '../../../services/ApiService';
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

import type { WizardCtx } from './types';

export default function WizardStep3({ ctx }: { ctx: WizardCtx }) {
  const { currentStep, setCurrentStep, projects, mentors, loadingInitial, tagInput,
    setTagInput, coAuthorInput, setCoAuthorInput, isNewProject, setIsNewProject,
    newProjectName, setNewProjectName, editorMode, setEditorMode, isSaving,
    registries, formData, setFormData, coAuthorSearch, setCoAuthorSearch,
    coAuthorResults, setCoAuthorResults, isSearchingCoAuthors, isAILoading, next, back,
    addListItem, removeListItem, calculateCompleteness, handleFinalize,
    handleSaveDraft, handleLocalCache, handleAIAssistant,
    user, projectId, onClose, onComplete } = ctx;
  return (
<>
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
</>
  );
}
