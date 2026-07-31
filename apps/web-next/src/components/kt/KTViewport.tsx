'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
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
