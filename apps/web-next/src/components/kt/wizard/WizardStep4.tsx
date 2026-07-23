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

export default function WizardStep4({ ctx }: { ctx: WizardCtx }) {
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
</>
  );
}
