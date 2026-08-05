'use client';

import React, { useState } from 'react';
import { isGroupAdminPlus, isMentorPlus, isLDAdminPlus } from '../../lib/kt/permissions';

interface NavItem { icon: string; label: string; view?: string; href?: string }

interface BottomNavProps {
  currentView?: string;
  onChangeView: (view: any) => void;
  user: any;
  onLogout?: () => void;
}

/**
 * Mobile + tablet bottom navigation: 5 primary destinations + a "More" sheet
 * holding everything else (role-gated). Shown below the `lg` breakpoint; the
 * desktop left sidebar takes over at `lg+`. Nothing is skipped — the More sheet
 * scrolls and lists every remaining feature.
 */
export function BottomNav({ currentView, onChangeView, user, onLogout }: BottomNavProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const role = user?.role || 'Member';
  const isLdAdmin = isLDAdminPlus(role);
  const isMentor = isMentorPlus(role);
  const isGroupAdmin = isGroupAdminPlus(role);
  const isPlatformAdmin = role === 'PlatformAdmin';

  // 5 primary (most-used); the rest go into "More".
  const primary: NavItem[] = [
    { icon: 'dashboard', label: 'Home', view: 'DASHBOARD' },
    { icon: 'hub', label: 'Knowledge', view: 'KNOWLEDGE_HUB' },
    { icon: 'quiz', label: 'Exams', href: '/exams' },
    { icon: 'assignment', label: 'Tasks', view: 'ASSIGNMENTS' },
  ];

  const more: NavItem[] = [
    { icon: 'history', label: 'Attempt History', view: 'ATTEMPT_HISTORY' },
    { icon: 'library_books', label: 'Library', view: 'LIBRARY' },
    { icon: 'forum', label: 'Discussions', view: 'DISCUSSIONS' },
    { icon: 'folder_open', label: 'Resources', view: 'RESOURCES' },
    { icon: 'person', label: 'My Profile', view: 'PROFILE' },
    ...(isGroupAdmin ? [{ icon: 'settings', label: 'Group Admin', view: 'ADMIN' }] : []),
    ...(isMentor ? [{ icon: 'school', label: 'Mentor Hub', view: 'MENTOR' }] : []),
    ...(isLdAdmin ? [{ icon: 'shield', label: 'L&D Ecosystem', view: 'LD_ADMIN' }] : []),
    ...(isPlatformAdmin ? [{ icon: 'shield', label: 'Platform Admin', href: '/platform' }] : []),
  ];

  const go = (item: NavItem) => {
    setMoreOpen(false);
    if (item.href) window.location.href = item.href;
    else if (item.view) onChangeView(item.view);
  };

  const Btn = ({ item, active }: { item: NavItem; active: boolean }) => (
    <button
      onClick={() => go(item)}
      className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-1.5 min-w-0 ${active ? 'text-brand-primary' : 'text-slate-400'}`}
    >
      <span className="material-symbols-outlined" style={{ fontSize: '22px' }}>{item.icon}</span>
      <span className="text-[10px] font-semibold truncate max-w-full">{item.label}</span>
    </button>
  );

  return (
    <>
      {/* More sheet */}
      {moreOpen && (
        <div className="lg:hidden fixed inset-0 z-[60]" onClick={() => setMoreOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="absolute bottom-0 inset-x-0 max-h-[70vh] overflow-y-auto rounded-t-3xl bg-[var(--color-surface-container-low)] border-t border-[var(--color-surface-bright)] p-4 pb-24"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-10 h-1 bg-slate-600 rounded-full mx-auto mb-4" />
            <div className="grid grid-cols-3 gap-3">
              {more.map((item) => (
                <button
                  key={item.label}
                  onClick={() => go(item)}
                  className={`flex flex-col items-center gap-1.5 p-3 rounded-2xl border ${currentView === item.view ? 'border-brand-primary/40 bg-brand-primary/10 text-brand-primary' : 'border-white/5 bg-white/5 text-slate-300'}`}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '24px' }}>{item.icon}</span>
                  <span className="text-[11px] font-semibold text-center leading-tight">{item.label}</span>
                </button>
              ))}
              {onLogout && (
                <button
                  onClick={() => { setMoreOpen(false); onLogout(); }}
                  className="flex flex-col items-center gap-1.5 p-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 text-rose-300"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '24px' }}>logout</span>
                  <span className="text-[11px] font-semibold text-center leading-tight">Log out</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Fixed bottom bar (mobile + tablet only) */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-50 flex items-stretch bg-[var(--color-surface-container-low)]/95 backdrop-blur border-t border-[var(--color-surface-bright)] pb-[env(safe-area-inset-bottom)] print:hidden">
        {primary.map((item) => (
          <Btn key={item.label} item={item} active={item.view ? currentView === item.view : false} />
        ))}
        <button
          onClick={() => setMoreOpen((o) => !o)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-1.5 ${moreOpen ? 'text-brand-primary' : 'text-slate-400'}`}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '22px' }}>apps</span>
          <span className="text-[10px] font-semibold">More</span>
        </button>
      </nav>
    </>
  );
}
