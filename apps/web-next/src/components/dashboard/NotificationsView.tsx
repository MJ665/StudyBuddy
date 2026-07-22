import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Bell, 
  CheckCircle2, 
  AlertCircle, 
  Info, 
  Trash2, 
  MailOpen, 
  ChevronRight,
  Sparkles,
  ClipboardList,
  Trophy,
  Loader2,
  BellRing
} from 'lucide-react';
import ApiService from '../../services/ApiService';

interface Notification {
  id: number;
  notification_type: 'new_assignment' | 'performance_report' | 'system_alert' | 'streak_milestone' | 'quiz_graded';
  title: string;
  body: string;
  is_read: boolean;
  link_type?: string;
  link_id?: number;
  created_at: string;
}

interface NotificationsViewProps {
  user: any;
  onBack: () => void;
  onNavigate: (type: string, id: number) => void;
}

export default function NotificationsView({ user, onBack, onNavigate }: NotificationsViewProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      const data = await ApiService.getNotifications();
      setNotifications(data);
    } catch (err) {
      console.error("Failed to fetch notifications", err);
    } finally {
      setLoading(false);
    }
  };

  const markRead = async (id: number) => {
    try {
      await ApiService.markNotificationRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    } catch (err) {
      console.error("Failed to mark as read", err);
    }
  };

  const markAllRead = async () => {
    try {
      await ApiService.markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error("Failed to mark all as read", err);
    }
  };

  const deleteNotif = async (id: number) => {
    try {
      await ApiService.deleteNotification(id);
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (err) {
      console.error("Failed to delete notification", err);
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'new_assignment': return <ClipboardList className="text-indigo-400" size={20} />;
      case 'performance_report': return <Sparkles className="text-purple-400" size={20} />;
      case 'streak_milestone': return <Trophy className="text-amber-400" size={20} />;
      case 'quiz_graded': return <CheckCircle2 className="text-emerald-400" size={20} />;
      default: return <Info className="text-slate-400" size={20} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8 font-plus-jakarta">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-6">
          <div>
            <h1 className="text-4xl font-black text-white mb-2 tracking-tight flex items-center gap-4">
              <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl text-indigo-400">
                <BellRing size={32} />
              </div>
              Intelligence Alerts
            </h1>
            <p className="text-slate-500 font-bold uppercase tracking-[0.2em] text-[10px]">Real-time Operational Dispatches & Updates</p>
          </div>

          <div className="flex items-center gap-3">
             <button 
               onClick={markAllRead}
               className="px-4 py-2 bg-slate-900 border border-white/5 rounded-xl text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white transition-all flex items-center gap-2"
             >
                <MailOpen size={14} /> Mark All Read
             </button>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 space-y-4">
            <Loader2 className="animate-spin text-indigo-500" size={48} />
            <p className="text-slate-500 font-black uppercase tracking-widest text-xs">Accessing Communication Channel...</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="py-32 text-center bg-slate-900/20 rounded-[3rem] border border-dashed border-white/5">
            <Bell size={64} className="mx-auto text-slate-800 mb-6" />
            <h3 className="text-2xl font-black text-white mb-2">Silence Detected</h3>
            <p className="text-slate-500 font-medium">No intelligence alerts are currently queued for your profile.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <AnimatePresence mode="popLayout">
              {notifications.map((notif, idx) => (
                <motion.div
                  key={notif.id}
                  layout
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ delay: idx * 0.03 }}
                  className={`group relative bg-slate-900/40 backdrop-blur-xl border ${notif.is_read ? 'border-white/5' : 'border-indigo-500/20'} rounded-[2rem] p-6 flex gap-6 items-start hover:bg-slate-900/60 transition-all cursor-pointer`}
                  onClick={() => {
                    if (!notif.is_read) markRead(notif.id);
                    if (notif.link_type && notif.link_id) onNavigate(notif.link_type, notif.link_id);
                  }}
                >
                  <div className={`p-4 rounded-2xl ${notif.is_read ? 'bg-slate-950' : 'bg-indigo-500/10 shadow-[0_0_20px_rgba(99,102,241,0.1)]'} transition-all`}>
                     {getIcon(notif.notification_type)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                       <h4 className={`text-sm font-black tracking-tight ${notif.is_read ? 'text-slate-300' : 'text-white'}`}>{notif.title}</h4>
                       <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">{new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <p className="text-xs text-slate-500 font-medium leading-relaxed line-clamp-2 mb-3">{notif.body}</p>
                    
                    <div className="flex items-center gap-4">
                       {!notif.is_read && <span className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />}
                       <span className="text-[10px] text-slate-600 font-bold uppercase tracking-[0.15em]">{new Date(notif.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button 
                       onClick={(e) => { e.stopPropagation(); deleteNotif(notif.id); }}
                       className="p-2 hover:bg-rose-500/10 text-slate-500 hover:text-rose-500 rounded-lg transition-all"
                     >
                        <Trash2 size={16} />
                     </button>
                     <button className="p-2 hover:bg-indigo-500/10 text-slate-500 hover:text-indigo-400 rounded-lg transition-all">
                        <ChevronRight size={16} />
                     </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
