import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ShieldCheck, 
  Users, 
  Settings, 
  LayoutDashboard, 
  TrendingUp,
  ShieldAlert,
  Terminal,
  Activity,
  Layers,
  Search,
  Plus,
  ArrowLeft
} from 'lucide-react';
import LDAdminDashboard from './LDAdminDashboard';
import MentorDashboard from './MentorDashboard';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

type AdminView = 'EXECUTIVE' | 'MENTOR' | 'OPS' | 'ANALYTICS';

export default function AdministrationEngine({ 
  user,
  onBack,
  onViewReport,
  onViewPremium,
  onViewForum
}: { 
  user: any,
  onBack: () => void,
  onViewReport?: (batchId: number) => void,
  onViewPremium?: (slugOrId: string | number) => void,
  onViewForum?: () => void
}) {
  const { toast } = useToast();
  const [activeView, setActiveView] = useState<AdminView>('EXECUTIVE');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Auto-route based on role
  useEffect(() => {
    if (user.role === 'Mentor') setActiveView('MENTOR');
    else if (user.role === 'GroupAdmin') setActiveView('OPS');
    else setActiveView('EXECUTIVE');
  }, [user.role]);

  const renderView = () => {
    switch (activeView) {
      case 'EXECUTIVE':
        return <LDAdminDashboard user={user} onViewReport={onViewReport || (() => {})} onViewPremium={onViewPremium || (() => {})} />;
      case 'MENTOR':
        return <MentorDashboard user={user} onBack={onBack} onViewPremium={onViewPremium || (() => {})} />;
      case 'OPS':
        return <LDAdminDashboard user={user} onViewReport={onViewReport || (() => {})} onViewPremium={onViewPremium || (() => {})} isOpsView={true} />;
      case 'ANALYTICS':
        return (
           <div className="flex-1 p-10">
              <h2 className="text-3xl font-black text-white mb-8">Strategic Analytics Engine</h2>
              {/* This would be the dedicated analytics tab from LDAdminDashboard but standalone */}
              <div className="bg-slate-900/50 border border-white/5 rounded-[3rem] p-20 text-center">
                 <TrendingUp size={48} className="mx-auto text-brand-primary mb-6" />
                 <p className="text-slate-400 font-bold">Deep learning analytics visualization is active. Select a sector from the Executive dashboard.</p>
              </div>
           </div>
        );
      default:
        return <LDAdminDashboard user={user} onViewReport={onViewReport} onViewPremium={onViewPremium} />;
    }
  };

  return (
    <div className="flex h-full w-full bg-slate-950 overflow-hidden font-sans">
      {/* Sidebar - Strategic Navigation */}
      <motion.aside 
        initial={false}
        animate={{ width: isSidebarOpen ? '280px' : '80px' }}
        className="h-full bg-slate-900 border-r border-white/5 flex flex-col z-20"
      >
        <div className="p-6 flex items-center gap-3 border-b border-white/5">
          <div className="w-10 h-10 rounded-xl bg-brand-primary flex items-center justify-center text-slate-950">
            <ShieldCheck size={24} />
          </div>
          {isSidebarOpen && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-brand-primary">L&D Engine</p>
              <p className="text-sm font-black text-white">Administration</p>
            </motion.div>
          )}
        </div>

        <nav className="flex-1 p-4 space-y-2 mt-4">
          <NavItem 
            active={activeView === 'EXECUTIVE'} 
            onClick={() => setActiveView('EXECUTIVE')}
            icon={<LayoutDashboard size={20} />}
            label="Executive"
            isOpen={isSidebarOpen}
          />
          {(user.role === 'LDAdmin' || user.role === 'Mentor') && (
            <NavItem 
              active={activeView === 'MENTOR'} 
              onClick={() => setActiveView('MENTOR')}
              icon={<Users size={20} />}
              label="Mentorship"
              isOpen={isSidebarOpen}
            />
          )}
          <NavItem 
            active={activeView === 'ANALYTICS'} 
            onClick={() => setActiveView('ANALYTICS')}
            icon={<TrendingUp size={20} />}
            label="Analytics"
            isOpen={isSidebarOpen}
          />
          <NavItem 
            active={false} 
            onClick={onViewForum || (() => {})}
            icon={<Users size={20} />}
            label="Community"
            isOpen={isSidebarOpen}
          />
          <NavItem 
            active={activeView === 'OPS'} 
            onClick={() => setActiveView('OPS')}
            icon={<Activity size={20} />}
            label="Operations"
            isOpen={isSidebarOpen}
          />
        </nav>

        <div className="p-4 border-t border-white/5 space-y-2">
          <NavItem 
            active={false} 
            onClick={onBack}
            icon={<ArrowLeft size={20} />}
            label="Exit Admin"
            isOpen={isSidebarOpen}
            variant="danger"
          />
          <div 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-500 hover:text-white hover:bg-white/5 cursor-pointer transition-all"
          >
            <Settings size={20} />
            {isSidebarOpen && <span className="text-xs font-black uppercase tracking-widest">Collapse</span>}
          </div>
        </div>
      </motion.aside>

      {/* Main Content Area */}
      <main className="flex-1 h-full overflow-hidden flex flex-col relative">
        {/* Global Search / Context Bar */}
        <header className="h-20 bg-slate-900/50 backdrop-blur-xl border-b border-white/5 px-8 flex items-center justify-between z-10">
          <div className="flex items-center gap-4 flex-1 max-w-xl">
             <div className="relative w-full">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
                <input 
                   type="text" 
                   placeholder="Search registry, entities, or protocols..."
                   className="w-full bg-slate-950 border border-white/10 rounded-2xl pl-12 pr-4 py-3 text-xs text-white focus:outline-none focus:ring-2 focus:ring-brand-primary/20 transition-all"
                />
             </div>
          </div>

          <div className="flex items-center gap-6">
             <div className="text-right">
                <p className="text-xs font-black text-white">{user.full_name}</p>
                <p className="text-[10px] font-black text-brand-primary uppercase tracking-widest">{user.role}</p>
             </div>
             <div className="w-10 h-10 rounded-full bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center text-brand-primary font-black">
                {user.full_name?.[0]}
             </div>
          </div>
        </header>

        {/* View Port */}
        <div className="flex-1 overflow-hidden flex">
          {renderView()}
        </div>
      </main>
    </div>
  );
}

function NavItem({ 
  active, 
  onClick, 
  icon, 
  label, 
  isOpen,
  variant = 'default' 
}: { 
  active: boolean, 
  onClick: () => void, 
  icon: any, 
  label: string, 
  isOpen: boolean,
  variant?: 'default' | 'danger'
}) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all group ${
        active 
          ? 'bg-brand-primary text-slate-950 shadow-lg shadow-brand-primary/20' 
          : variant === 'danger'
            ? 'text-rose-500 hover:bg-rose-500/10'
            : 'text-slate-400 hover:text-white hover:bg-white/5'
      }`}
    >
      <div className={`${active ? '' : 'group-hover:scale-110'} transition-transform`}>
        {icon}
      </div>
      {isOpen && (
        <span className="text-xs font-black uppercase tracking-widest">
          {label}
        </span>
      )}
    </button>
  );
}
