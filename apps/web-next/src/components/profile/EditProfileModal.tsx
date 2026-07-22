import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Save, User, FileText, Github, Linkedin, MessageSquare, Code2, Globe } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface EditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: any;
  onSuccess: (updated: any) => void;
}

export default function EditProfileModal({ isOpen, onClose, profile, onSuccess }: EditProfileModalProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    full_name: profile?.full_name || '',
    bio: profile?.bio || '',
    github_url: profile?.github_url || '',
    linkedin_url: profile?.linkedin_url || '',
    leetcode_url: profile?.leetcode_url || '',
    codolio_url: profile?.codolio_url || '',
    custom_slug: profile?.custom_slug || '',
  });

  const handleSave = async () => {
    setLoading(true);
    try {
      const res = await ApiService.updateProfile(formData);
      toast('success', 'Professional Identity Synchronized');
      onSuccess(res);
      onClose();
    } catch (err: any) {
      toast('error', `Update failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const Input = ({ label, icon: Icon, value, onChange, placeholder, type = 'text' }: any) => (
    <div className="space-y-2">
      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
        <Icon size={12} /> {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-950 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 transition-all font-medium"
      />
    </div>
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[1001] flex items-center justify-center p-6 bg-slate-950/80 backdrop-blur-md">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="w-full max-w-2xl bg-[#0a192f] border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
          >
            {/* Header */}
            <div className="p-8 border-b border-white/5 bg-[#112240]/50 shrink-0">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-2xl font-black text-white italic tracking-tight">Identity Management</h3>
                  <p className="text-xs text-slate-500 font-bold tracking-widest mt-1">UPDATE YOUR GLOBAL PROFESSIONAL PROFILE</p>
                </div>
                <button onClick={onClose} className="p-2 text-slate-500 hover:text-white transition-colors">
                  <X size={20} />
                </button>
              </div>
            </div>

            <div className="p-8 overflow-y-auto space-y-8 flex-1 custom-scrollbar">
              {/* Basic Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Input 
                  label="Full Name" 
                  icon={User} 
                  value={formData.full_name} 
                  onChange={(v: string) => setFormData({...formData, full_name: v})} 
                />
                <Input 
                  label="Custom Profile Slug" 
                  icon={Globe} 
                  value={formData.custom_slug} 
                  onChange={(v: string) => setFormData({...formData, custom_slug: v})} 
                />
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
                  <FileText size={12} /> Professional Headline / Bio
                </label>
                <textarea
                  value={formData.bio}
                  onChange={(e) => setFormData({...formData, bio: e.target.value})}
                  placeholder="Master level developer with a focus on..."
                  className="w-full h-32 bg-slate-950 border border-white/10 rounded-2xl p-4 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 transition-all font-medium resize-none"
                />
              </div>

              {/* Social Links */}
              <div className="space-y-6">
                <h4 className="text-xs font-black text-indigo-400 uppercase tracking-[0.2em] border-b border-indigo-500/10 pb-2">Verified Artifacts</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Input 
                    label="GitHub Profile" 
                    icon={Github} 
                    value={formData.github_url} 
                    placeholder="https://github.com/..."
                    onChange={(v: string) => setFormData({...formData, github_url: v})} 
                  />
                  <Input 
                    label="LinkedIn Profile" 
                    icon={Linkedin} 
                    value={formData.linkedin_url} 
                    placeholder="https://linkedin.com/in/..."
                    onChange={(v: string) => setFormData({...formData, linkedin_url: v})} 
                  />
                  <Input 
                    label="LeetCode Profile" 
                    icon={Code2} 
                    value={formData.leetcode_url} 
                    placeholder="https://leetcode.com/..."
                    onChange={(v: string) => setFormData({...formData, leetcode_url: v})} 
                  />
                  <Input 
                    label="Codolio Profile" 
                    icon={MessageSquare} 
                    value={formData.codolio_url} 
                    placeholder="https://codolio.com/..."
                    onChange={(v: string) => setFormData({...formData, codolio_url: v})} 
                  />
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-8 bg-[#112240]/30 border-t border-white/5">
              <button
                onClick={handleSave}
                disabled={loading}
                className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white rounded-2xl font-black uppercase tracking-widest transition-all shadow-xl shadow-blue-500/20 flex items-center justify-center gap-3"
              >
                {loading ? (
                   <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    Synchronize Identity <Save size={18} />
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
