'use client';

import React, { useState } from 'react';
import { Edit3, Eye, Save, Loader2 } from 'lucide-react';
import Editor from '@monaco-editor/react';
import ApiService from '@/services/ApiService';
import { toast } from 'react-hot-toast';

export default function KTDocumentEditor({ doc, onSave, onCancel }: { doc: any, onSave: (d: any) => void, onCancel: () => void }) {
  const [formData, setFormData] = useState({
    title: doc.title,
    body_markdown: doc.body_markdown,
    problem_statement: doc.problem_statement || '',
    outcome: doc.outcome || '',
    conclusion: doc.conclusion || '',
    lessons_learned: doc.lessons_learned || [],
    open_questions: doc.open_questions || [],
    tags: doc.tags || [],
    sprint: doc.sprint || '',
    milestone: doc.milestone || '',
    change_summary: '',
  });
  const [saving, setSaving] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await ApiService.request(`/kt/documents/${doc.id}`, {
        method: 'PATCH',
        body: JSON.stringify(formData)
      });
      toast.success('Document saved successfully');
      onSave(updated);
    } catch (err: any) {
      toast.error(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full">
      {/* Edit header bar */}
      <div className="flex items-center justify-between p-4 bg-amber-950/20 border border-amber-500/30 rounded-2xl">
        <div className="flex items-center gap-3">
          <Edit3 size={16} className="text-amber-400" />
          <span className="text-amber-400 font-bold text-sm">Editing Mode</span>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Change summary (e.g. Fixed deployment steps)..."
            className="bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-white w-72 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            value={formData.change_summary}
            onChange={e => setFormData({...formData, change_summary: e.target.value})}
          />
          <button onClick={() => setPreviewMode(!previewMode)} className="text-slate-400 flex items-center gap-2 hover:text-white px-3">
            {previewMode ? <Edit3 size={14} /> : <Eye size={14} />}
            {previewMode ? 'Edit' : 'Preview'}
          </button>
          <button onClick={onCancel} className="text-slate-400 px-3">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="bg-indigo-600 px-4 py-2 rounded-xl text-white flex items-center gap-2">
            {saving ? <Loader2 className="animate-spin" size={14} /> : <Save size={14} />}
            Save Changes
          </button>
        </div>
      </div>
      
      {/* Title edit */}
      <input
        type="text"
        value={formData.title}
        onChange={e => setFormData({...formData, title: e.target.value})}
        className="text-3xl font-black bg-transparent border-b border-slate-800 pb-2 text-white focus:outline-none focus:border-indigo-500 w-full"
      />
      
      {/* Monaco Editor for body */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[600px]">
        <div className={previewMode ? 'hidden lg:block' : 'block col-span-2'}>
          <Editor
            height="600px"
            defaultLanguage="markdown"
            theme="vs-dark"
            value={formData.body_markdown}
            onChange={val => setFormData({...formData, body_markdown: val || ''})}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: 'JetBrains Mono, monospace',
              wordWrap: 'on',
              lineNumbers: 'on',
              padding: { top: 20 },
            }}
          />
        </div>
      </div>
      
      {/* Structured fields edit */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <label className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2 block">Problem Statement</label>
          <textarea
            value={formData.problem_statement}
            onChange={e => setFormData({...formData, problem_statement: e.target.value})}
            rows={4}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-white text-sm flex-1"
          />
        </div>
        <div>
          <label className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2 block">Outcome & Results</label>
          <textarea
            value={formData.outcome}
            onChange={e => setFormData({...formData, outcome: e.target.value})}
            rows={4}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-white text-sm flex-1"
          />
        </div>
      </div>
    </div>
  );
}
