'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, User, ChevronRight, History, GitBranch, ArrowLeft, Loader2 } from 'lucide-react';
import { format } from 'date-fns';
import ApiService from '@/services/ApiService';

interface Version {
  id: string;
  version: number;
  created_at: string;
  summary: string;
  author: string | number;
}

interface KnowledgeVersionHistoryProps {
  docId: string;
  onClose: () => void;
  onSelectVersion?: (version: Version) => void;
}

const KnowledgeVersionHistory = ({ docId, onClose, onSelectVersion }: KnowledgeVersionHistoryProps) => {
  const [versions, setVersions] = useState<Version[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        const data = await ApiService.getKTDocumentVersions(docId);
        setVersions(data || []);
      } catch (error) {
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchVersions();
  }, [docId]);

  return (
    <div className="flex flex-col h-full bg-slate-900/50 backdrop-blur-xl border-l border-slate-800">
      <div className="p-6 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-400 border border-amber-500/20">
            <History size={20} />
          </div>
          <div>
            <h3 className="font-bold text-white">Version History</h3>
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Document Evolution</p>
          </div>
        </div>
        <button 
          onClick={onClose}
          className="p-2 hover:bg-slate-800 rounded-lg text-slate-500 transition-colors"
        >
          <ArrowLeft size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="animate-spin text-amber-500" size={32} />
          </div>
        ) : versions.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center p-8">
            <GitBranch size={48} className="mb-4 opacity-20" />
            <p className="text-sm font-bold uppercase tracking-widest">No history found</p>
            <p className="text-xs mt-2">This document is currently at its initial version.</p>
          </div>
        ) : (
          versions.map((v, i) => (
            <motion.div
              key={v.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => onSelectVersion?.(v)}
              className="group p-5 bg-slate-900 border border-slate-800 rounded-2xl cursor-pointer hover:border-amber-500/50 transition-all relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                <GitBranch size={48} />
              </div>

              <div className="flex justify-between items-start mb-4 relative z-10">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-amber-500/10 text-amber-400 text-[10px] font-black rounded border border-amber-500/20 uppercase">
                    v{v.version}
                  </span>
                  <span className="text-[10px] font-bold text-slate-500 flex items-center gap-1">
                    <Clock size={12} />
                    {format(new Date(v.created_at), 'MMM dd, yyyy HH:mm')}
                  </span>
                </div>
                <ChevronRight size={16} className="text-slate-600 group-hover:text-amber-400 transition-colors" />
              </div>

              <p className="text-sm font-bold text-white mb-3 line-clamp-2">{v.summary || 'No summary provided'}</p>

              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-slate-500">
                <User size={12} />
                <span>Changed by ID: {v.author}</span>
              </div>
            </motion.div>
          ))
        )}
      </div>

      <div className="p-6 border-t border-slate-800 bg-slate-900/30">
        <p className="text-[10px] text-slate-500 leading-relaxed italic">
          Snapshots are automatically captured on every major update. You can revert to any previous version by selecting it above.
        </p>
      </div>
    </div>
  );
};

export default KnowledgeVersionHistory;
