/**
 * NotificationCenter.tsx
 * Full slide-out notification panel with read/unread management.
 * Replaces single NotificationBell icon - becomes a proper inbox center.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import * as LucideIcons from 'lucide-react';
import {
  Bell, X, CheckCheck, Trash2, Filter, RefreshCw,
  Sparkles, BookOpen, Star, AlertTriangle, Trophy, Code2,
  MessageSquare, Info, Loader2
} from 'lucide-react';
import ApiService from '../../services/ApiService';

function DynamicIcon({ name, size = 12, className = '' }: { name: string; size?: number; className?: string }) {
  const IconComponent = (LucideIcons as any)[name];
  if (!IconComponent) return <LucideIcons.Info size={size} className={className} />;
  return <IconComponent size={size} className={className} />;
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return 'just now';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface NotificationCenterProps {
  compact?: boolean;  // If compact, show just the bell icon
}

export default function NotificationCenter({ compact = false }: NotificationCenterProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [typeConfig, setTypeConfig] = useState<any[]>([]);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ApiService.getSystemConfig().then(config => {
      setTypeConfig(config.notification_types || []);
    }).catch(err => console.error("Failed to load notif config", err));
  }, []);

  const getNotifStyle = (type: string) => {
    const config = typeConfig.find(c => c.id === type) || typeConfig.find(c => c.id === 'system');
    if (!config) return { icon: 'Info', color: 'text-slate-400', bg: 'bg-slate-500/10' };
    return config;
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await ApiService.request('/auth/notifications');
      setNotifications(Array.isArray(data) ? data : data.notifications || []);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const markRead = async (id: number) => {
    try {
      await ApiService.request(`/auth/notifications/${id}/read`, {
        method: 'PATCH'
      });
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      );
    } catch (err) {
      console.error('Mark read failed', err);
    }
  };

  const markAllRead = async () => {
    try {
      await ApiService.request('/auth/notifications/read-all', {
        method: 'POST'
      });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Mark all read failed', err);
    }
  };

  const deleteNotification = async (id: number) => {
    try {
      await ApiService.request(`/auth/notifications/${id}`, {
        method: 'DELETE'
      });
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  // Stream unread count via Server-Sent Events (SSE)
  useEffect(() => {
    const token = localStorage.getItem('study_token');
    if (!token) return;

    // Use environment variable for API base, fallback to '/api'
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || '/api';
    const sseUrl = `${apiBase}/auth/notifications/stream?token=${token}`;
    
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.unread_count !== undefined) {
          // If the server reports a different unread count than we have locally,
          // it means there's a new notification. We trigger a background refresh.
          setNotifications(prev => {
            const localUnread = prev.filter(n => !n.is_read).length;
            if (data.unread_count > localUnread) {
              // Only fetch if count increases to avoid unnecessary fetches
              fetchNotifications();
            }
            return prev;
          });
        }
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE connection error", error);
      eventSource.close();
      // Simple backoff could be added here, but the browser often auto-reconnects
    };

    return () => {
      eventSource.close();
    };
  }, [fetchNotifications]);

  const filtered = filter === 'unread' ? notifications.filter(n => !n.is_read) : notifications;

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell Button */}
      <button
        onClick={() => setOpen(!open)}
        id="notification-bell-btn"
        className="relative p-2 text-slate-500 hover:text-white transition-colors group"
      >
        <Bell size={20} className={open ? 'text-indigo-400' : ''} />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-rose-500 rounded-full text-[8px] font-black text-white flex items-center justify-center"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </motion.span>
        )}
      </button>

      {/* Slide-Out Panel */}
      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, x: 16, scale: 0.98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 16, scale: 0.98 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="absolute right-0 top-10 z-50 w-96 max-w-[92vw] bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <Bell size={16} className="text-indigo-400" />
                  <span className="text-sm font-black text-white">Notifications</span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.5 bg-rose-500/20 border border-rose-500/30 rounded-md text-[9px] font-black text-rose-400">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={fetchNotifications}
                    className="p-1.5 text-slate-500 hover:text-white transition-colors rounded-lg hover:bg-white/5"
                    title="Refresh"
                  >
                    <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                  </button>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllRead}
                      className="p-1.5 text-slate-500 hover:text-emerald-400 transition-colors rounded-lg hover:bg-white/5"
                      title="Mark all read"
                    >
                      <CheckCheck size={13} />
                    </button>
                  )}
                  <button
                    onClick={() => setOpen(false)}
                    className="p-1.5 text-slate-500 hover:text-white transition-colors rounded-lg hover:bg-white/5"
                  >
                    <X size={13} />
                  </button>
                </div>
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center gap-1 px-5 pt-3 pb-2">
                {(['all', 'unread'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
                      filter === f
                        ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                        : 'text-slate-500 hover:text-white'
                    }`}
                  >
                    {f === 'all' ? `All (${notifications.length})` : `Unread (${unreadCount})`}
                  </button>
                ))}
              </div>

              {/* Notification List */}
              <div className="max-h-[480px] overflow-y-auto">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 size={24} className="text-indigo-400 animate-spin" />
                  </div>
                ) : filtered.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 gap-3">
                    <Bell size={28} className="text-slate-700" />
                    <p className="text-xs text-slate-600 font-bold">
                      {filter === 'unread' ? 'All caught up!' : 'No notifications yet'}
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-800/60">
                    {filtered.map(n => {
                      const config = getNotifStyle(n.notification_type);
                      return (
                        <motion.div
                          key={n.id}
                          layout
                          className={`group relative flex items-start gap-3 px-5 py-4 transition-colors hover:bg-white/[0.02] cursor-pointer ${
                            !n.is_read ? 'bg-indigo-500/[0.03]' : ''
                          }`}
                          onClick={() => !n.is_read && markRead(n.id)}
                        >
                          {/* unread dot */}
                          {!n.is_read && (
                            <div className="absolute left-2 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-indigo-500 rounded-full" />
                          )}

                          {/* Icon */}
                          <div className={`w-7 h-7 rounded-xl ${config.bg} border border-white/5 flex items-center justify-center shrink-0 ${config.color} mt-0.5`}>
                            <DynamicIcon name={config.icon} />
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <p className={`text-xs font-bold leading-relaxed ${n.is_read ? 'text-slate-400' : 'text-white'}`}>
                              {n.message}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <span className={`text-[9px] font-black uppercase tracking-widest ${config.color}`}>
                                {n.notification_type?.replace(/_/g, ' ')}
                              </span>
                              <span className="text-[9px] text-slate-600">{timeAgo(n.created_at)}</span>
                            </div>
                          </div>

                          {/* Actions (on hover) */}
                          <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                            {!n.is_read && (
                              <button
                                onClick={e => { e.stopPropagation(); markRead(n.id); }}
                                className="p-1 text-slate-600 hover:text-emerald-400 transition-colors"
                                title="Mark read"
                              >
                                <CheckCheck size={11} />
                              </button>
                            )}
                            <button
                              onClick={e => { e.stopPropagation(); deleteNotification(n.id); }}
                              className="p-1 text-slate-600 hover:text-rose-400 transition-colors"
                              title="Delete"
                            >
                              <Trash2 size={11} />
                            </button>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="px-5 py-3 border-t border-slate-800 flex justify-between items-center">
                  <p className="text-[9px] text-slate-600 font-bold">{notifications.length} total notifications</p>
                  <button
                    onClick={markAllRead}
                    className="text-[9px] text-indigo-400 hover:text-indigo-300 font-black uppercase tracking-widest transition-colors"
                  >
                    Mark all read
                  </button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
