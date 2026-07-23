'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  BookOpen, MessageSquare, Compass, Layers, UserMinus, Shield, 
  TrendingUp, Mail, ChevronDown, Bell, LogOut, LayoutGrid, Award, HelpCircle
} from 'lucide-react';
import { useKTNavStore, KTView } from '@/stores/ktNavStore';
import ApiService from '@/services/ApiService';
import type { KTCompany } from '@/types/kt';
import KTBreadcrumb from './KTBreadcrumb';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'react-hot-toast';

interface KTNavShellProps {
  user: any;
  onBack: () => void;
  children: React.ReactNode;
}

export default function KTNavShell({ user, onBack, children }: KTNavShellProps) {
  const router = useRouter();
  const {
    selectedCompany,
    selectedProject, 
    currentView, 
    selectCompany, 
    selectProject,
    setView,
    clearCompany,
    clearProject
  } = useKTNavStore();

  const [companies, setCompanies] = useState<KTCompany[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [notificationsCount, setNotificationsCount] = useState(0);

  useEffect(() => {
    // Fetch companies
    ApiService.listKTCompanies()
      .then((res: any) => {
        const fetchedCompanies = res || [];
        setCompanies(fetchedCompanies);

        // Parse initial URL to sync state from direct links
        if (typeof window !== 'undefined') {
          const path = window.location.pathname;
          if (path.startsWith('/kt/company/')) {
            const parts = path.split('/').filter(Boolean);
            const companyId = parts[2];
            const company = fetchedCompanies.find((c: any) => c.id.toString() === companyId);
            if (company && (!selectedCompany || selectedCompany.id.toString() !== companyId)) {
              selectCompany(company);
              
              if (parts.length >= 5 && parts[3] === 'project') {
                const projectId = parts[4];
                // We need to fetch projects for this company to select the right one
                ApiService.getKTProjects(company.id.toString()).then((projRes: any) => {
                  const project = (projRes || []).find((p: any) => p.id.toString() === projectId);
                  if (project) selectProject(project);
                }).catch(console.error);
              }
            }
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load KT companies:', err);
      });

    // Poll notifications
    const fetchNotifCount = async () => {
      try {
        const notifs = await ApiService.getKTNotifications(true); // unread only
        setNotificationsCount(notifs?.length || 0);
      } catch (err) {
        // Silent catch
      }
    };
    
    fetchNotifCount();
    const interval = setInterval(fetchNotifCount, 15000);
    return () => clearInterval(interval);
  }, []);

  // Sync state to URL for dynamic forwardable URLs
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let path = '/kt';
    if (selectedCompany) {
      path += `/company/${selectedCompany.id}`;
      if (selectedProject) {
        path += `/project/${selectedProject.id}`;
      }
    }
    
    // Only push if the path actually changed to avoid infinite loops with popstate.
    // Uses the App Router (not raw pushState) so Next's history stays in sync;
    // the /kt/[[...path]] catch-all serves every variant without a remount.
    if (window.location.pathname !== path && window.location.pathname.startsWith('/kt')) {
      router.replace(path, { scroll: false });
    }
  }, [selectedCompany, selectedProject, router]);

  const navItems = [
    { id: 'projects', label: 'Projects Registry', icon: <BookOpen size={18} />, roles: ['LDAdmin', 'Mentor', 'Member', 'GroupAdmin'] },
    { id: 'chat', label: 'AI Intelligence', icon: <MessageSquare size={18} />, roles: ['LDAdmin', 'Mentor', 'Member', 'GroupAdmin'] },
    { id: 'discovery', label: 'Knowledge Gap Discovery', icon: <Compass size={18} />, roles: ['LDAdmin', 'Mentor', 'Member', 'GroupAdmin'] },
    { id: 'graph', label: 'Graph Explorer', icon: <Layers size={18} />, roles: ['LDAdmin', 'Mentor', 'Member', 'GroupAdmin'] },
    { id: 'handoff', label: 'Handoff Engine', icon: <UserMinus size={18} />, roles: ['LDAdmin', 'Mentor', 'GroupAdmin'] },
    { id: 'keys', label: 'Access Keys', icon: <Shield size={18} />, roles: ['LDAdmin', 'Mentor', 'GroupAdmin'] },
    { id: 'analytics', label: 'Executive Analytics', icon: <TrendingUp size={18} />, roles: ['LDAdmin', 'Mentor', 'GroupAdmin'] },
    { id: 'mentor-inbox', label: 'Mentor Inbox', icon: <Mail size={18} />, roles: ['LDAdmin', 'Mentor', 'GroupAdmin'] },
    { id: 'unanswered', label: 'Unanswered AI Queries', icon: <HelpCircle size={18} />, roles: ['LDAdmin', 'Mentor'] },
  ];

  // Compute effective user roles (global + kt_roles)
  const effectiveUserRoles = [user?.role]
    .concat((user?.kt_roles || []).map((r: any) => r.role_name))
    .filter(Boolean as any);

  const visibleNavItems = navItems.filter(item =>
    (item.roles || []).some((r: string) => effectiveUserRoles.includes(r))
  );

  const handleNavClick = (viewId: string) => {
    if (viewId === 'projects') {
      if (selectedProject) {
        setView('documents');
      } else if (selectedCompany) {
        setView('projects');
      } else {
        setView('hub');
      }
    } else {
      setView(viewId as KTView);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-80 border-r border-slate-800 bg-slate-900/60 backdrop-blur-xl flex flex-col h-full relative z-10">
        
        {/* Sidebar Header & Company Selector */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Award className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-lg font-black bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent tracking-tight">StudyBuddy KT</h1>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Enterprise Intel</p>
            </div>
          </div>

          {/* Company Selector Dropdown */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="w-full bg-slate-950 border border-slate-800 rounded-2xl p-4 flex items-center justify-between hover:border-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              <div className="flex items-center gap-3 text-left">
                <LayoutGrid size={16} className="text-indigo-400" />
                <div>
                  <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Selected Company</p>
                  <p className="text-xs font-bold text-white truncate max-w-[150px]">
                    {selectedCompany ? selectedCompany.name : 'Select Company...'}
                  </p>
                </div>
              </div>
              <ChevronDown size={16} className={`text-slate-500 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {dropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute left-0 right-0 mt-2 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden max-h-60 overflow-y-auto z-50 custom-scrollbar"
                >
                  <div className="p-2 border-b border-slate-800 bg-slate-950/50">
                    <button
                      onClick={() => {
                        clearCompany();
                        setDropdownOpen(false);
                      }}
                      className="w-full text-left p-3 rounded-xl hover:bg-slate-800 text-xs font-bold uppercase tracking-widest text-indigo-400 flex items-center gap-2 transition-colors"
                    >
                      <LayoutGrid size={12} />
                      All Companies (Hub)
                    </button>
                  </div>
                  <div className="p-2 space-y-1">
                    {companies.map((company) => (
                      <button
                        key={company.id}
                        onClick={() => {
                          selectCompany(company);
                          setDropdownOpen(false);
                          toast.success(`Switched to ${company.name}`);
                        }}
                        className={`w-full text-left px-4 py-3 rounded-xl text-sm font-semibold transition-all flex items-center justify-between ${
                          selectedCompany?.id === company.id
                            ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20'
                            : 'text-slate-400 hover:bg-slate-800 hover:text-white border border-transparent'
                        }`}
                      >
                        <span>{company.name}</span>
                        {company.domain && (
                          <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-500">
                            {company.domain}
                          </span>
                        )}
                      </button>
                    ))}
                    {companies.length === 0 && (
                      <p className="text-xs text-slate-500 p-4 text-center">No companies found</p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Sidebar Nav Items */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto custom-scrollbar">
          {navItems.map((item) => {
            const isActive = 
              currentView === item.id || 
              (item.id === 'projects' && (currentView === 'documents' || currentView === 'projects' || currentView === 'hub' || currentView === 'document'));

            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all border ${
                  isActive
                    ? 'bg-indigo-600/10 border-indigo-500/25 text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.05)]'
                    : 'bg-transparent border-transparent text-slate-400 hover:bg-slate-800/30 hover:text-slate-200'
                }`}
              >
                <div className={`p-1.5 rounded-lg ${isActive ? 'bg-indigo-500/10 text-indigo-400' : 'text-slate-500'}`}>
                  {item.icon}
                </div>
                <span className="text-xs font-black uppercase tracking-widest flex-1 text-left">
                  {item.label}
                </span>

                {item.id === 'mentor-inbox' && notificationsCount > 0 && (
                  <span className="w-5 h-5 rounded-full bg-indigo-600 text-[10px] font-bold flex items-center justify-center text-white animate-pulse">
                    {notificationsCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="p-6 border-t border-slate-800 space-y-3">
          <div className="flex items-center gap-3 bg-slate-950/40 p-3 rounded-2xl border border-slate-850">
            <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-sm font-bold uppercase text-indigo-400 border border-slate-700">
              {user?.full_name?.charAt(0) || 'U'}
            </div>
            <div className="truncate flex-1">
              <p className="text-xs font-bold text-white truncate">{user?.full_name || 'User Profile'}</p>
              <p className="text-[9px] font-bold text-indigo-400 uppercase tracking-widest">{user?.role || 'Member'}</p>
            </div>
          </div>

          <button
            onClick={onBack}
            className="w-full bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white py-3 px-4 rounded-2xl font-bold text-xs uppercase tracking-widest transition-all flex items-center justify-center gap-2"
          >
            <LogOut size={14} />
            Back to Dashboard
          </button>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col h-full bg-slate-950 relative overflow-hidden z-10">
        {/* Subtle radial background glows for premium visual aesthetic */}
        <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-500/5 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[400px] h-[400px] rounded-full bg-indigo-600/3 blur-[100px] pointer-events-none" />
        
        <KTBreadcrumb />
        
        <div className="flex-1 min-h-0 overflow-hidden relative">
          {children}
        </div>
      </main>
    </div>
  );
}
