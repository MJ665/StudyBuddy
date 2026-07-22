'use client';
// ============================================================
// KT Chat Store — Zustand (session-scoped, not persisted)
// ============================================================

import { create } from 'zustand';
import type { KTChatMessage, KTSourceMetadata } from '@/types/kt';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: KTSourceMetadata[];
  confidence_score?: number;
  was_answered?: boolean;
  latency_ms?: number;
  feedback?: 1 | -1 | null;
  isError?: boolean;
  created_at: string;
}

type ChatStatus = 'idle' | 'sending' | 'error';

interface KTChatStore {
  // Messages keyed by session_id — survives tab switches
  messagesBySession: Record<string, ChatMessage[]>;
  isTyping: boolean;
  chatStatus: ChatStatus;
  errorMessage: string;

  addMessage: (sessionId: string, message: ChatMessage) => void;
  addUserMessage: (sessionId: string, content: string) => string;
  addAssistantMessage: (sessionId: string, response: any) => void;
  setTyping: (typing: boolean) => void;
  setChatStatus: (status: ChatStatus) => void;
  setError: (msg: string) => void;
  clearChat: (sessionId: string) => void;
  clearAllChats: () => void;
  setFeedback: (sessionId: string, messageId: string, feedback: 1 | -1) => void;
  getMessages: (sessionId: string) => ChatMessage[];
}

export const useKTChatStore = create<KTChatStore>()((set, get) => ({
  messagesBySession: {},
  isTyping: false,
  chatStatus: 'idle',
  errorMessage: '',

  addMessage: (sessionId, message) =>
    set(state => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [...(state.messagesBySession[sessionId] || []), message],
      },
    })),

  addUserMessage: (sessionId, content) => {
    const tempId = `user-${Date.now()}`;
    const message: ChatMessage = {
      id: tempId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    set(state => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [...(state.messagesBySession[sessionId] || []), message],
      },
      isTyping: true,
      chatStatus: 'sending',
    }));
    return tempId;
  },

  addAssistantMessage: (sessionId, response) => {
    const message: ChatMessage = {
      id: response.id || `asst-${Date.now()}`,
      role: 'assistant',
      content: response.content || response.answer || 'No response.',
      sources: response.sources || [],
      confidence_score: response.confidence_score,
      was_answered: response.was_answered,
      latency_ms: response.latency_ms,
      isError: response.isError || false,
      created_at: new Date().toISOString(),
    };
    set(state => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [...(state.messagesBySession[sessionId] || []), message],
      },
      isTyping: false,
      chatStatus: 'idle',
    }));
  },

  setTyping: (typing) => set({ isTyping: typing }),
  setChatStatus: (status) => set({ chatStatus: status }),
  setError: (msg) => set({ errorMessage: msg, chatStatus: 'error', isTyping: false }),

  clearChat: (sessionId) =>
    set(state => ({
      messagesBySession: { ...state.messagesBySession, [sessionId]: [] },
    })),

  clearAllChats: () => set({ messagesBySession: {}, isTyping: false }),

  setFeedback: (sessionId, messageId, feedback) =>
    set(state => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: (state.messagesBySession[sessionId] || []).map(m =>
          m.id === messageId ? { ...m, feedback } : m
        ),
      },
    })),

  getMessages: (sessionId) => get().messagesBySession[sessionId] || [],
}));
