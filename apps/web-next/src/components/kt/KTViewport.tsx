'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { KeyRound, Loader2 } from 'lucide-react';
import { useKTNavStore } from '@/stores/ktNavStore';
import type { KTView } from '@/stores/ktNavStore';

// View Imports
import KTCompanySelectorView from './KTCompanySelectorView';
import KTProjectsView from './KTProjectsView';
import KnowledgeRegistry from './KnowledgeRegistry';
import KnowledgeDetail from './KnowledgeDetail';
import KnowledgeExplorer from './KnowledgeExplorer';
import KnowledgeDiscovery from './KnowledgeDiscovery';
import KTAnalyticsView from './KTAnalyticsView';
import KTHandoffView from './KTHandoffView';
import KTKeysView from './KTKeysView';
import KTChatView from './KTChatView';
import KTMentorInboxView from './KTMentorInboxView';
import KTCreationWizard from './KTCreationWizard';
import KnowledgeVersionHistory from './KnowledgeVersionHistory';
import KTScopedProjectView from './KTScopedProjectView';
import UnansweredQueriesView from './UnansweredQueriesView';
import ApiService from '@/services/ApiService';
import { toast } from 'react-hot-toast';

interface KTViewportProps {
  user: any;
}

export default function KTViewport({ user }: KTViewportProps) {
  const { 
    currentView, 
    selectedCompany,
    selectedProject, 
    selectedDocId, 
    setView, 
    selectDoc 
  } = useKTNavStore();

  const [historyDocId, setHistoryDocId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // ── Access-key entry gate ────────────────────────────────────────────────
  // L&D / Owner / PlatformAdmin manage KT and bypass the gate. Everyone else is
  // a knowledge CONSUMER: they must hold an access grant (a redeemed key /
  // project membership) before the hub opens — otherwise no company knowledge is
  // shown at all. `/kt/companies` is grant-scoped, so an empty list ⇒ no access.
  const role = user?.role || 'Member';
  const isManager = ['LDAdmin', 'ld_admin', 'Owner', 'owner', 'PlatformAdmin'].includes(role);
  const [gate, setGate] = useState<'checking' | 'locked' | 'open'>(isManager ? 'open' : 'checking');
  const [keyInput, setKeyInput] = useState('');
  const [redeeming, setRedeeming] = useState(false);
  const [gateError, setGateError] = useState<string | null>(null);

  const checkAccess = React.useCallback(async () => {
    if (isManager) { setGate('open'); return; }
    try {
      const companies = await ApiService.getKTCompanies();
      setGate(Array.isArray(companies) && companies.length > 0 ? 'open' : 'locked');
    } catch {
      setGate('locked');
    }
  }, [isManager]);

  useEffect(() => { checkAccess(); }, [checkAccess]);

  const redeem = async () => {
    if (!keyInput.trim()) return;
    setRedeeming(true);
    setGateError(null);
    try {
      await ApiService.redeemKTKey(keyInput.trim());
      setKeyInput('');
      await checkAccess();
      toast.success('Access key accepted — knowledge unlocked.');
    } catch (e: any) {
      setGateError(e?.message || 'Invalid or expired access key.');
    } finally {
      setRedeeming(false);
    }
  };

  const handleEndorse = async (docId: string) => {
    try {
      await ApiService.endorseKTDocument(docId);
      toast.success('Document endorsed by peer!');
      setRefreshKey(prev => prev + 1);
    } catch (err: any) {
      toast.error(err.message || 'Failed to endorse');
    }
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case 'hub':
        return <KTCompanySelectorView user={user} />;
      
      case 'projects':
        return <KTProjectsView user={user} />;
      
      case 'documents':
        return (
          <KnowledgeRegistry
            key={`registry-${refreshKey}`}
            onViewHistory={(id) => setHistoryDocId(id)}
            onViewDocument={(id) => selectDoc(id)}
            onCreateDocument={() => setView('create')}
          />
        );
      
      case 'document':
        return selectedDocId ? (
          <KnowledgeDetail
            docId={selectedDocId}
            onBack={() => setView('documents')}
            onViewHistory={() => setHistoryDocId(selectedDocId)}
            onEndorse={() => handleEndorse(selectedDocId)}
          />
        ) : (
          <div className="p-8 text-slate-500">No document selected.</div>
        );
      
      case 'graph':
        return <KnowledgeExplorer projectId={selectedProject?.id || undefined} />;
      
      case 'discovery':
        return <KnowledgeDiscovery />;
      
      case 'analytics':
        return <KTAnalyticsView />;
      
      case 'handoff':
        return <KTHandoffView user={user} />;
      
      case 'keys':
        return <KTKeysView user={user} />;
      
      case 'chat':
        return <KTChatView />;
      
      case 'create':
        return (
          <KTCreationWizard
            user={user}
            projectId={selectedProject?.id || ''}
            onClose={() => setView('documents')}
            onComplete={() => { setRefreshKey(prev => prev + 1); setView('documents'); }}
          />
        );
      
      case 'mentor-inbox':
        return <KTMentorInboxView />;

      case 'key-scoped-projects':
        return <KTScopedProjectView />;

      case 'unanswered':
        return <UnansweredQueriesView companyId={selectedCompany?.id ? Number(selectedCompany.id) : undefined} projectId={selectedProject?.id ? Number(selectedProject.id) : undefined} />;

      default:
        return <KTCompanySelectorView user={user} />;
    }
  };

  // ── Gate screens (consumers only) ────────────────────────────────────────
  if (gate === 'checking') {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <Loader2 className="animate-spin mr-2" size={18} /> Verifying knowledge access…
      </div>
    );
  }
  if (gate === 'locked') {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-md w-full rounded-2xl bg-slate-900 border border-slate-800 p-8 text-center">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
            <KeyRound className="text-indigo-400" size={26} />
          </div>
          <h2 className="text-xl font-black text-white mb-2">Access key required</h2>
          <p className="text-slate-400 text-sm mb-6">
            The Knowledge Hub is protected. Enter the access key shared with you to
            unlock the projects and chatbot you&apos;ve been granted.
          </p>
          <input
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && redeem()}
            placeholder="sh_kt_…"
            className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2.5 text-sm font-mono text-white mb-3 focus:outline-none focus:border-indigo-500"
          />
          {gateError && <p className="text-rose-400 text-xs mb-3">{gateError}</p>}
          <button
            onClick={redeem}
            disabled={redeeming || !keyInput.trim()}
            className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 py-2.5 font-bold text-sm text-white"
          >
            {redeeming ? 'Verifying…' : 'Unlock knowledge'}
          </button>
          <p className="text-slate-600 text-[11px] mt-4">No key? Ask your L&amp;D admin to issue one for your project.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 relative overflow-hidden h-full">
      {/* Animated Route Switcher */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={currentView}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -15 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="flex-1 flex flex-col min-h-0 h-full"
        >
          {renderCurrentView()}
        </motion.div>
      </AnimatePresence>

      {/* Drawer Overlay for Version History */}
      <AnimatePresence>
        {historyDocId && (
          <>
            {/* Backdrop lock */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              onClick={() => setHistoryDocId(null)}
              className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm"
            />
            {/* Slide-out Panel */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed top-0 right-0 w-[450px] h-screen z-50 shadow-2xl bg-slate-900 border-l border-slate-800"
            >
              <KnowledgeVersionHistory
                docId={historyDocId}
                onClose={() => setHistoryDocId(null)}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
