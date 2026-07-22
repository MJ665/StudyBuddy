'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, ArrowLeft, Download, Paperclip, 
  Trash2, Plus, Loader2, Calendar, User, 
  History, Star, Shield, Info
} from 'lucide-react';
import ApiService from '@/services/ApiService';
import { format } from 'date-fns';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-hot-toast';
import KTDocumentEditor from './KTDocumentEditor';
import EnterpriseMarkdownPreview from './EnterpriseMarkdownPreview';
import KTPdfPreviewModal from './KTPdfPreviewModal';

interface Attachment {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  download_url?: string;
  created_at: string;
}

interface Document {
  id: string;
  title: string;
  body_markdown: string;
  doc_type: string;
  author_id: string | number;
  author_name?: string;
  created_at: string;
  version: number;
  endorsement_count?: number;
  metadata_json?: Record<string, any>;
}

interface KnowledgeDetailProps {
  docId: string;
  onBack: () => void;
  onViewHistory?: () => void;
  onEndorse?: () => void;
  accessKey?: string;
}

const KnowledgeDetail = ({ docId, onBack, onViewHistory, onEndorse, accessKey }: KnowledgeDetailProps) => {
  const [doc, setDoc] = useState<Document | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [previewPdf, setPreviewPdf] = useState<Attachment | null>(null);

  useEffect(() => {
    try {
      if (!accessKey) {
        const userStr = localStorage.getItem('study_user');
        if (userStr) {
          const userObj = JSON.parse(userStr);
          if (userObj.role === 'LDAdmin' || userObj.role === 'Mentor') {
            setIsAdmin(true);
          }
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [accessKey]);

  const handleDeprecate = async () => {
    if (!window.confirm("Are you absolutely sure you want to deprecate this document? It will be removed from active semantic queries and the knowledge graph.")) return;
    try {
      await ApiService.deprecateKTDocument(docId);
      toast.success("Document deprecated and removed from knowledge graph");
      onBack();
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Failed to deprecate document");
    }
  };


  useEffect(() => {
    fetchData();
  }, [docId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [docData, attData] = await Promise.all([
        ApiService.getKTDocument(docId, accessKey),
        ApiService.getKTDocumentAttachments(docId, accessKey)
      ]);
      setDoc(docData);
      setAttachments(attData || []);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load document details');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 50 * 1024 * 1024) {
      return toast.error('File too large (max 50MB)');
    }

    setUploading(true);
    try {
      // 1. Get pre-signed URL
      const presign = await ApiService.getKTAttachmentUploadUrl(docId, file.name, file.type);
      
      // 2. Upload to S3 (Direct PUT)
      const uploadRes = await fetch(presign.url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type,
        },
      });

      if (!uploadRes.ok) throw new Error('Upload to storage failed');

      // 3. Register with backend
      await ApiService.registerKTAttachment(docId, {
        filename: file.name,
        s3_key: presign.fields.key,
        file_type: file.type,
        file_size: file.size
      });

      toast.success('File attached successfully');
      fetchData();
    } catch (err: any) {
      console.error(err);
      toast.error(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteAttachment = async (id: string) => {
    if (!confirm('Are you sure you want to remove this attachment?')) return;
    try {
      await ApiService.request(`/kt/attachments/${id}`, { method: 'DELETE' });
      toast.success('Attachment removed');
      setAttachments(prev => prev.filter(a => a.id !== id));
    } catch (err) {
      toast.error('Failed to delete attachment');
    }
  };

  if (loading) {
    return (
      <div className="h-[600px] flex items-center justify-center">
        <Loader2 className="animate-spin text-indigo-500" size={48} />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="h-[600px] flex flex-col items-center justify-center text-slate-500">
        <Info size={48} className="mb-4 opacity-20" />
        <p className="font-bold uppercase tracking-widest">Document not found</p>
        <button onClick={onBack} className="mt-4 text-indigo-400 hover:underline">Go back</button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-12 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Left Column: Content */}
      <div className="col-span-8 space-y-6">
        <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-10">
          <div className="flex items-center gap-4 mb-8">
            <button 
              onClick={onBack}
              className="p-3 bg-slate-800 rounded-2xl text-slate-400 hover:text-white transition-all hover:bg-slate-700"
            >
              <ArrowLeft size={20} />
            </button>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] font-black rounded border border-indigo-500/20 uppercase tracking-widest">
                  {doc.doc_type}
                </span>
                <span className="px-2 py-0.5 bg-slate-800 text-slate-500 text-[10px] font-black rounded border border-slate-700 uppercase tracking-widest">
                  v{doc.version}
                </span>
              </div>
              <h1 className="text-3xl font-black text-white tracking-tight">{doc.title}</h1>
            </div>
          </div>

          {isEditing ? (
            <KTDocumentEditor doc={doc} onSave={(d) => { setDoc(d); setIsEditing(false); }} onCancel={() => setIsEditing(false)} />
          ) : (
            <div className="mt-6">
              {((doc as any).can_edit) && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="mb-6 flex items-center gap-2 px-4 py-2 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-400 border border-indigo-500/30 rounded-xl font-bold text-xs transition-all"
                >
                  <FileText size={14} /> Edit Document
                </button>
              )}
              <EnterpriseMarkdownPreview content={doc.body_markdown || '*No content provided.*'} />
              
              {/* Structured Metadata Rendering */}
              {doc.metadata_json && (doc.metadata_json.problem_statement || doc.metadata_json.outcome) && (
                <div className="mt-12 pt-8 border-t border-slate-800 space-y-6">
                  {doc.metadata_json.problem_statement && (
                    <div className="bg-slate-950/50 rounded-2xl p-6 border border-slate-800/50">
                      <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3">Problem Statement</h4>
                      <p className="text-sm text-slate-300 leading-relaxed">{doc.metadata_json.problem_statement}</p>
                    </div>
                  )}
                  {doc.metadata_json.outcome && (
                    <div className="bg-slate-950/50 rounded-2xl p-6 border border-slate-800/50">
                      <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-3">Outcome</h4>
                      <p className="text-sm text-slate-300 leading-relaxed">{doc.metadata_json.outcome}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Metadata & Attachments */}
      <div className="col-span-4 space-y-6">
        {/* Actions Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-[2rem] p-8">
          <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
            <Shield size={12} className="text-indigo-400" /> Administrative Actions
          </h3>
          <div className="space-y-3">
            <button 
              onClick={onEndorse}
              className="w-full flex items-center justify-between px-6 py-4 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-all group"
            >
              <div className="flex items-center gap-3">
                <Star size={18} className="group-hover:fill-amber-400 transition-all" />
                <span className="font-bold">Endorse Document</span>
              </div>
              <span className="text-xs opacity-60 font-black">{doc.endorsement_count || 0}</span>
            </button>
            <button 
              onClick={onViewHistory}
              className="w-full flex items-center gap-3 px-6 py-4 rounded-2xl bg-slate-800 text-slate-300 border border-slate-700/50 hover:bg-slate-700 transition-all"
            >
              <History size={18} />
              <span className="font-bold">Revision History</span>
            </button>
            {isAdmin && (
              <button 
                onClick={handleDeprecate}
                className="w-full flex items-center gap-3 px-6 py-4 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 hover:bg-rose-500/20 transition-all"
              >
                <Trash2 size={18} />
                <span className="font-bold">Deprecate Document</span>
              </button>
            )}
          </div>

          <div className="mt-8 pt-8 border-t border-slate-800/50 space-y-4">
            <div className="flex items-center gap-3 text-xs">
              <User size={14} className="text-slate-500" />
              <span className="text-slate-400">Author:</span>
              <span className="text-white font-bold">{doc.author_name || doc.author_id}</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <Calendar size={14} className="text-slate-500" />
              <span className="text-slate-400">Created:</span>
              <span className="text-white font-bold">{format(new Date(doc.created_at), 'MMM dd, yyyy')}</span>
            </div>
          </div>
        </div>

        {/* Attachments Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-[2rem] p-8 overflow-hidden">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-[10px] font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
              <Paperclip size={12} className="text-indigo-400" /> Attachments
            </h3>
            <label className="cursor-pointer p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 hover:bg-indigo-500/20 transition-all">
              <Plus size={16} />
              <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
            </label>
          </div>

          {uploading && (
            <div className="flex items-center gap-3 p-4 bg-indigo-500/5 border border-indigo-500/20 rounded-2xl mb-4 animate-pulse">
              <Loader2 className="animate-spin text-indigo-400" size={16} />
              <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-widest">Uploading to Cloud...</span>
            </div>
          )}

          <div className="space-y-3">
            {attachments.length === 0 ? (
              <div className="py-10 text-center text-slate-600 border-2 border-dashed border-slate-800 rounded-3xl">
                <Paperclip size={24} className="mx-auto mb-2 opacity-10" />
                <p className="text-[10px] font-bold uppercase tracking-widest">No attachments</p>
              </div>
            ) : (
              attachments.map((att) => (
                <div key={att.id} className="group p-4 bg-slate-950 border border-slate-800 rounded-2xl hover:border-slate-700 transition-all">
                  <div className="flex justify-between items-start mb-2">
                    <p className="text-xs font-bold text-slate-200 truncate pr-4" title={att.filename}>{att.filename}</p>
                    <button 
                      onClick={() => handleDeleteAttachment(att.id)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-500 hover:text-rose-400 transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">
                      {(att.file_size / 1024 / 1024).toFixed(2)} MB
                    </span>
                    {att.download_url && (
                      <div className="flex gap-3 items-center">
                        {att.file_type === 'application/pdf' || att.filename.toLowerCase().endsWith('.pdf') ? (
                          <button 
                            onClick={() => setPreviewPdf(att)}
                            className="flex items-center gap-1.5 text-[9px] font-black text-rose-400 uppercase tracking-widest hover:text-rose-300"
                          >
                            <FileText size={12} /> Preview
                          </button>
                        ) : null}
                        <a 
                          href={att.download_url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1.5 text-[9px] font-black text-indigo-400 uppercase tracking-widest hover:text-indigo-300"
                        >
                          <Download size={12} /> Download
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {previewPdf && (
        <KTPdfPreviewModal attachment={previewPdf} onClose={() => setPreviewPdf(null)} />
      )}
    </div>
  );
};

export default KnowledgeDetail;
