'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Zap, AlertCircle, Lightbulb, ArrowRight, Loader2, Compass } from 'lucide-react';
import ApiService from '@/services/ApiService';
import { useKTNavStore } from '@/stores/ktNavStore';

interface Suggestion {
  type: 'GAP_DETECTED' | 'COVERAGE_ALERT';
  title: string;
  description: string;
  action_label: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

const KnowledgeDiscovery = () => {
  const { selectedCompany } = useKTNavStore();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const fetchDiscovery = async () => {
      try {
        const data = await ApiService.getKTDiscoverySuggestions(selectedCompany?.id);
        // Handle both direct array and paginated object responses
        const rawItems = Array.isArray(data) ? data : (data?.items || []);
        
        if (!Array.isArray(rawItems)) {
          console.warn('Discovery API returned non-array items:', rawItems);
          setSuggestions([]);
          return;
        }

        // Transform backend gaps into frontend suggestions
        const mappedSuggestions: Suggestion[] = rawItems.map((item: any) => ({
          type: 'GAP_DETECTED',
          title: item.query_text || 'Missing Documentation',
          description: `Detected ${item.occurrence_count || 1} queries about this topic with no matching knowledge base entries.`,
          action_label: 'Document Now',
          priority: (item.occurrence_count || 1) > 5 ? 'CRITICAL' : (item.occurrence_count || 1) > 2 ? 'HIGH' : 'MEDIUM'
        }));
        
        setSuggestions(mappedSuggestions);
      } catch (err) {
        console.error('Discovery fetch failed:', err);
        setSuggestions([]); 
      } finally {
        setLoading(false);
      }
    };
    fetchDiscovery();
  }, []);

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center bg-slate-900/50 rounded-[2rem] border border-slate-800">
        <Loader2 className="animate-spin text-indigo-500" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 border border-indigo-500/20">
            <Compass size={20} />
          </div>
          <div>
            <h3 className="font-bold text-white">AI Knowledge Discovery</h3>
            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Intelligent Gap Detection</p>
          </div>
        </div>
        <div className="px-3 py-1 bg-indigo-500/10 text-indigo-400 text-[10px] font-black rounded-full border border-indigo-500/20 uppercase">
          {suggestions.length} Signals
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {suggestions.length === 0 ? (
          <div className="col-span-full p-12 text-center bg-slate-900/30 rounded-[2.5rem] border border-slate-800/50">
            <Zap size={48} className="mx-auto mb-4 text-slate-700 opacity-20" />
            <p className="text-sm font-bold text-slate-500">No knowledge gaps detected.</p>
            <p className="text-xs text-slate-600 mt-2">Your organizational memory is currently high-fidelity.</p>
          </div>
        ) : (
          suggestions.map((s, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="group p-6 bg-slate-900 border border-slate-800 rounded-[2rem] hover:border-indigo-500/50 transition-all relative overflow-hidden"
            >
              <div className={`absolute top-0 right-0 w-1 h-full ${
                s.priority === 'CRITICAL' ? 'bg-red-500' : s.priority === 'HIGH' ? 'bg-amber-500' : 'bg-indigo-500'
              }`} />
              
              <div className="flex items-center gap-2 mb-4">
                {s.type === 'GAP_DETECTED' ? (
                  <div className="p-2 bg-amber-500/10 text-amber-500 rounded-lg">
                    <Lightbulb size={16} />
                  </div>
                ) : (
                  <div className="p-2 bg-red-500/10 text-red-500 rounded-lg">
                    <AlertCircle size={16} />
                  </div>
                )}
                <span className={`text-[9px] font-black uppercase tracking-widest ${
                  s.priority === 'CRITICAL' ? 'text-red-400' : s.priority === 'HIGH' ? 'text-amber-400' : 'text-indigo-400'
                }`}>
                  {s.priority} Priority
                </span>
              </div>

              <h4 className="text-sm font-bold text-white mb-2">{s.title}</h4>
              <p className="text-xs text-slate-400 leading-relaxed mb-6 line-clamp-3">
                {s.description}
              </p>

              <button className="w-full py-3 bg-slate-800 rounded-xl text-[10px] font-black uppercase tracking-widest text-white hover:bg-indigo-500 transition-all flex items-center justify-center gap-2 group-hover:bg-indigo-600">
                {s.action_label}
                <ArrowRight size={14} />
              </button>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
};

export default KnowledgeDiscovery;
