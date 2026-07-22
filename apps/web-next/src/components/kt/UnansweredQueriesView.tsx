'use client';

import React, { useState } from 'react';
import { HelpCircle, Reply, Check, Clock, Search, X } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../ui/Toast';

export default function UnansweredQueriesView({ companyId, projectId }: { companyId?: number, projectId?: number }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedQuery, setSelectedQuery] = useState<any>(null);
  const [answer, setAnswer] = useState('');

  const { data: queries, isLoading } = useQuery({
    queryKey: ['kt-unanswered-queries', companyId, projectId],
    queryFn: async () => {
      // Stub endpoint for frontend alignment
      // return ApiService.getUnansweredQueries(companyId, projectId);
      return [];
    }
  });

  const answerMutation = useMutation({
    mutationFn: async (payload: { id: number, answer: string }) => {
      // return ApiService.answerKTQuery(payload.id, payload.answer);
    },
    onSuccess: () => {
      toast('success', 'Answer provided and embedded into knowledge graph.');
      queryClient.invalidateQueries({ queryKey: ['kt-unanswered-queries'] });
      setSelectedQuery(null);
      setAnswer('');
    },
    onError: (err: any) => {
      toast('error', err.message || 'Failed to submit answer.');
    }
  });

  if (isLoading) {
    return <div className="animate-pulse flex space-x-4">
      <div className="flex-1 space-y-4 py-1">
        <div className="h-4 bg-zinc-800 rounded w-3/4"></div>
        <div className="space-y-2">
          <div className="h-4 bg-zinc-800 rounded"></div>
          <div className="h-4 bg-zinc-800 rounded w-5/6"></div>
        </div>
      </div>
    </div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <HelpCircle className="w-6 h-6 text-indigo-400" />
            Unanswered Queries Queue
          </h2>
          <p className="text-zinc-400 text-sm mt-1">Review questions the RAG AI failed to answer and train the graph.</p>
        </div>
      </div>

      {!queries || queries.length === 0 ? (
        <div className="text-center py-12 bg-zinc-900 border border-zinc-800 rounded-xl">
          <Check className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-white">Queue is Empty</h3>
          <p className="text-zinc-400 text-sm mt-1">All user questions have been successfully answered by the AI.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {queries.map((q: any) => (
            <div key={q.id} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex gap-4 items-start">
              <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                <HelpCircle className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <p className="text-white font-medium">{q.query_text}</p>
                <div className="flex items-center gap-4 mt-2 text-xs text-zinc-500">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(q.created_at).toLocaleDateString()}</span>
                  <span>User: {q.user_name}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedQuery(q)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white text-sm rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                <Reply className="w-4 h-4" /> Provide Answer
              </button>
            </div>
          ))}
        </div>
      )}

      {selectedQuery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-zinc-800 flex justify-between items-start">
              <div>
                <h3 className="text-xl font-bold text-white">Provide Answer</h3>
                <p className="text-sm text-zinc-400 mt-1">This answer will be embedded and stored in the RAG knowledge graph.</p>
              </div>
              <button onClick={() => setSelectedQuery(null)} className="text-zinc-500 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <p className="text-xs text-zinc-500 uppercase font-bold tracking-widest mb-1">User Question</p>
                <p className="text-white">{selectedQuery.query_text}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Your Answer</label>
                <textarea
                  value={answer}
                  onChange={e => setAnswer(e.target.value)}
                  placeholder="Provide a detailed answer. This will train the AI for future questions..."
                  className="w-full h-40 bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-none"
                />
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3 bg-zinc-900/50">
              <button
                onClick={() => setSelectedQuery(null)}
                className="px-5 py-2.5 text-sm font-medium text-zinc-300 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!answer.trim() || answerMutation.isPending}
                onClick={() => answerMutation.mutate({ id: selectedQuery.id, answer })}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2 shadow-lg shadow-indigo-500/20"
              >
                {answerMutation.isPending ? 'Saving...' : 'Submit & Train Graph'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
