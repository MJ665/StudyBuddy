'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { 
  UserMinus, Loader2, Sparkles, BookOpen, Clock, Calendar, CheckSquare, 
  Square, AlertTriangle, ArrowRight, UserCheck, MessageSquare, ClipboardList, HelpCircle
} from 'lucide-react';
import ApiService from '@/services/ApiService';
import { useKTNavStore } from '@/stores/ktNavStore';
import { toast } from 'react-hot-toast';

interface KTHandoffViewProps {
  user: any;
}

export default function KTHandoffView({ user }: KTHandoffViewProps) {
  const { selectedCompany } = useKTNavStore();
  const [loading, setLoading] = useState(true);
  const [handoffs, setHandoffs] = useState<any[]>([]);
  const [handoffGaps, setHandoffGaps] = useState<string[]>([]);
  const [handoffAnalytics, setHandoffAnalytics] = useState<any>(null);

  // Form states
  const [searchQuery, setSearchQuery] = useState('');
  const [coAuthors, setCoAuthors] = useState<any[]>([]);
  const [selectedRecipient, setSelectedRecipient] = useState<any | null>(null);
  const [selectedMentor, setSelectedMentor] = useState<any | null>(null);
  
  // Manager-led Handoff additions
  const [isSelfHandoff, setIsSelfHandoff] = useState(true);
  const [selectedDepartingUser, setSelectedDepartingUser] = useState<any | null>(null);
  const [departingUsersList, setDepartingUsersList] = useState<any[]>([]);

  const [handoffType, setHandoffType] = useState('senior_to_junior');
  const [departureDate, setDepartureDate] = useState('');
  const [notes, setNotes] = useState('');
  const [initiating, setInitiating] = useState(false);

  const fetchHandoffGaps = async () => {
    if (!selectedCompany) return;
    try {
      const res = await ApiService.analyze_handoff_pre(user.id, selectedCompany.id);
      setHandoffGaps(res.gaps || []);
      setHandoffAnalytics(res);
    } catch (err) {
      console.error('Failed to load handoff gaps:', err);
    }
  };

  const fetchHandoffList = async () => {
    setLoading(true);
    try {
      const res = await ApiService.listKTHandoffs();
      setHandoffs(res || []);
    } catch (err) {
      console.error('Failed to load handoffs list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedCompany) {
      fetchHandoffGaps();
      fetchHandoffList();
    }
  }, [selectedCompany]);

  // Search co-authors for recipient or mentor selection
  const handleUserSearch = async (query: string, type: 'recipient' | 'mentor' | 'departing') => {
    setSearchQuery(query);
    if (query.trim().length < 2) {
      if (type === 'departing') setDepartingUsersList([]);
      else setCoAuthors([]);
      return;
    }
    try {
      const res = await ApiService.searchCoAuthors(query, user.group_id);
      const normalized = (res || []).map((u: any) => ({
        id: u.user_id,
        full_name: u.name,
        email: u.email,
        role: u.group_name || 'Member',
      }));
      if (type === 'departing') {
        setDepartingUsersList(normalized);
      } else {
        setCoAuthors(normalized);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleInitiateHandoff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCompany) return;
    
    const departingId = isSelfHandoff ? user.id : selectedDepartingUser?.id;
    if (!departingId) {
      toast.error('Select a departing user');
      return;
    }

    if (!selectedRecipient) {
      toast.error('Select a knowledge recipient co-author');
      return;
    }

    setInitiating(true);
    try {
      await ApiService.initiateKTHandoff({
        departing_user_id: departingId,
        company_id: selectedCompany.id,
        receiving_user_id: selectedRecipient.id,
        mentor_id: selectedMentor?.id || undefined,
        departure_date: departureDate || undefined,
        handoff_type: handoffType,
        notes: notes || undefined
      });

      toast.success('Knowledge Handoff initiated successfully!');
      setSelectedRecipient(null);
      setSelectedMentor(null);
      setDepartureDate('');
      setNotes('');
      fetchHandoffList();
    } catch (err: any) {
      toast.error(err.message || 'Failed to initiate handoff');
    } finally {
      setInitiating(false);
    }
  };

  const handleToggleChecklist = async (handoffId: string, itemIndex: number, done: boolean) => {
    try {
      // NOTE: Checking list items marks tasks as completed but NEVER triggers database user deletion!
      await ApiService.updateHandoffChecklist(handoffId, itemIndex, done);
      toast.success('Handoff progress updated!');
      fetchHandoffList();
    } catch (err: any) {
      toast.error(err.message || 'Failed to update checklist item');
    }
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar relative z-10 max-w-7xl mx-auto w-full">
      <header className="mb-12">
        <div className="flex items-center gap-2 mb-2 text-indigo-400">
          <Sparkles size={16} />
          <span className="text-xs font-black uppercase tracking-widest">Team Transition Engine</span>
        </div>
        <h1 className="text-4xl font-black text-white tracking-tight">Knowledge Sharing & Handoff</h1>
        <p className="text-slate-400 text-sm mt-1 max-w-xl">
          Coordinate seamless conceptual knowledge transition between outgoing leaders and incoming engineers. 
          Audit structural knowledge gaps and assign peer mentorship.
        </p>
      </header>

      {/* Critical Conceptual Warning Banner */}
      <div className="bg-indigo-950/20 border border-indigo-500/20 rounded-[2rem] p-6 mb-10 flex gap-4 items-start">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400 shrink-0">
          <HelpCircle size={20} />
        </div>
        <div>
          <h3 className="font-bold text-white text-sm">Conceptual Knowledge Sharing Protocol</h3>
          <p className="text-slate-400 text-xs mt-1 leading-relaxed">
            The handoff protocol transfers vital domain expertise, system architecture context, and sprint history. 
            Initiating a handoff delegates document authorship permissions and sets up checklist tracking. 
            This protocol **never** deletes employee database accounts.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Form Column */}
        <div className="lg:col-span-2 space-y-8">
          
          <div className="bg-slate-900 border border-slate-850 rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-indigo-500/5 rounded-full blur-[60px] pointer-events-none" />
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
              <ClipboardList className="text-indigo-400" size={20} />
              <span>Initiate Handoff Package</span>
            </h2>

            <form onSubmit={handleInitiateHandoff} className="space-y-6">
              
              {/* Manager Toggle */}
              <div className="flex items-center justify-between bg-slate-950 p-4 rounded-2xl border border-slate-800">
                <div>
                  <h4 className="text-sm font-bold text-white">I am the departing user</h4>
                  <p className="text-xs text-slate-500 mt-1">Turn off if you are a manager initiating a handoff for someone else</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsSelfHandoff(!isSelfHandoff)}
                  className={`w-12 h-6 rounded-full p-1 transition-colors ${isSelfHandoff ? 'bg-indigo-500' : 'bg-slate-700'}`}
                >
                  <div className={`w-4 h-4 rounded-full bg-white transition-transform ${isSelfHandoff ? 'translate-x-6' : 'translate-x-0'}`} />
                </button>
              </div>

              {/* Departing User Selector (if Manager-led) */}
              {!isSelfHandoff && (
                <div className="space-y-2 relative">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">
                    Select Departing User
                  </label>
                  <input
                    type="text"
                    placeholder="Search departing user by name or email..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                    onChange={(e) => handleUserSearch(e.target.value, 'departing')}
                  />
                  {departingUsersList.length > 0 && (
                    <div className="absolute left-0 right-0 mt-2 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden max-h-48 overflow-y-auto z-50">
                      {departingUsersList.map((u) => (
                        <button
                          key={u.id}
                          type="button"
                          onClick={() => {
                            setSelectedDepartingUser(u);
                            setDepartingUsersList([]);
                          }}
                          className="w-full text-left px-4 py-3 hover:bg-slate-800 text-xs font-bold text-slate-300 flex items-center justify-between"
                        >
                          <span>{u.full_name} ({u.email})</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedDepartingUser && (
                    <div className="mt-2 bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-3 flex items-center justify-between">
                      <span className="text-sm font-bold text-indigo-400">{selectedDepartingUser.full_name}</span>
                      <button type="button" onClick={() => setSelectedDepartingUser(null)} className="text-xs text-rose-400 font-bold uppercase tracking-wider">Remove</button>
                    </div>
                  )}
                </div>
              )}

              {/* Recipient Co-author Search input */}
              <div className="space-y-2 relative">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">
                  Select Knowledge Recipient (Incoming Engineer)
                </label>
                <input
                  type="text"
                  placeholder="Search co-authors by name or email..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                  onChange={(e) => handleUserSearch(e.target.value, 'recipient')}
                />
                
                {/* Autocomplete Dropdown */}
                {coAuthors.length > 0 && (
                  <div className="absolute left-0 right-0 mt-2 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden max-h-48 overflow-y-auto z-50">
                    {coAuthors.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => {
                          setSelectedRecipient(u);
                          setCoAuthors([]);
                        }}
                        className="w-full text-left px-4 py-3 rounded-lg hover:bg-slate-800 text-xs font-bold text-slate-300 flex items-center justify-between"
                      >
                        <span>{u.full_name} ({u.email})</span>
                        <span className="text-[9px] bg-slate-950 text-indigo-400 px-2 py-0.5 rounded uppercase tracking-wider">{u.role}</span>
                      </button>
                    ))}
                  </div>
                )}

                {selectedRecipient && (
                  <div className="flex items-center justify-between bg-slate-950/80 p-3 rounded-xl border border-indigo-500/20 mt-2">
                    <div className="flex items-center gap-2">
                      <UserCheck size={16} className="text-indigo-400" />
                      <span className="text-xs font-bold text-slate-200">
                        Assigned Recipient: {selectedRecipient.full_name} ({selectedRecipient.email})
                      </span>
                    </div>
                    <button 
                      type="button" 
                      onClick={() => setSelectedRecipient(null)}
                      className="text-xs text-rose-400 font-bold hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              {/* Mentor Search Input */}
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">
                  Assign Transition Mentor (Optional verification peer)
                </label>
                <input
                  type="text"
                  placeholder="Search mentors by name..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                  onChange={(e) => handleUserSearch(e.target.value, 'mentor')}
                />
                {selectedMentor && (
                  <div className="flex items-center justify-between bg-slate-950/80 p-3 rounded-xl border border-indigo-500/20 mt-2">
                    <div className="flex items-center gap-2">
                      <UserCheck size={16} className="text-indigo-400" />
                      <span className="text-xs font-bold text-slate-200">
                        Assigned Mentor: {selectedMentor.full_name}
                      </span>
                    </div>
                    <button 
                      type="button" 
                      onClick={() => setSelectedMentor(null)}
                      className="text-xs text-rose-400 font-bold hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Transition Type</label>
                  <select
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                    value={handoffType}
                    onChange={(e) => setHandoffType(e.target.value)}
                  >
                    <option value="senior_to_junior">Senior → Junior Knowledge Share</option>
                    <option value="departure">Voluntary Knowledge Transfer</option>
                    <option value="cross_team">Cross-Team Knowledge Share</option>
                    <option value="project_reassignment">Project Reassignment</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Handoff Completion Target Date</label>
                  <input
                    type="date"
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm"
                    value={departureDate}
                    onChange={(e) => setDepartureDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Handoff Strategy Notes</label>
                <textarea
                  placeholder="Enter strategic handover plans, repository coordinates, or key systems documentation references..."
                  rows={4}
                  className="w-full bg-slate-950 border border-slate-800 rounded-2xl py-3.5 px-4 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-white text-sm resize-none"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={initiating}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white py-4 rounded-2xl font-bold transition-all shadow-xl shadow-indigo-500/25 flex items-center justify-center gap-2 text-sm"
              >
                {initiating ? <Loader2 className="animate-spin" size={18} /> : 'Initiate Transfer Package'}
              </button>
            </form>
          </div>

          {/* Handoff List / Progress audit */}
          <div className="space-y-4">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Active Handoff Audits</h3>
            
            {loading ? (
              <div className="h-20 flex items-center justify-center">
                <Loader2 className="animate-spin text-indigo-500" size={24} />
              </div>
            ) : (
              <div className="space-y-4">
                {handoffs.map((h) => (
                  <div key={h.id} className="bg-slate-900/40 border border-slate-850 rounded-[2rem] p-6 space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <span className="text-[9px] font-black uppercase tracking-widest px-2.5 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full">
                          {h.handoff_type || 'Mentorship'}
                        </span>
                        <h4 className="text-white font-bold text-base mt-2">
                          Knowledge transition: {h.departing_user_name || 'Outgoing'} → {h.receiving_user_name || 'Incoming'}
                        </h4>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span className="flex items-center gap-1.5">
                          <Calendar size={14} />
                          Target: {h.departure_date ? new Date(h.departure_date).toLocaleDateString() : 'TBD'}
                        </span>
                      </div>
                    </div>

                    {h.notes && (
                      <p className="text-slate-400 text-xs italic bg-slate-950 p-4 rounded-xl border border-slate-850">
                        {h.notes}
                      </p>
                    )}

                    {/* Checklist items */}
                    {h.checklist && h.checklist.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-850">
                        <p className="text-[9px] font-black uppercase tracking-widest text-slate-500">Transition Checklist Tasks</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {h.checklist.map((item: any, idx: number) => (
                            <button
                              key={idx}
                              onClick={() => handleToggleChecklist(h.id, idx, !item.done)}
                              className={`flex items-center gap-3 p-3 rounded-xl border text-left text-xs transition-all ${
                                item.done 
                                  ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-400' 
                                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                              }`}
                            >
                              {item.done ? <CheckSquare size={14} /> : <Square size={14} />}
                              <span className="truncate">{item.item || item.task}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {handoffs.length === 0 && (
                  <div className="bg-slate-900/10 border border-slate-850 rounded-2xl p-12 text-center">
                    <ClipboardList className="mx-auto text-slate-700 mb-3" size={32} />
                    <p className="text-slate-400 font-bold">No Transition Packages Registered</p>
                    <p className="text-xs text-slate-500 mt-1">Handoffs track progress to secure team handovers safely without deleting accounts.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right analytics Sidebar */}
        <div className="space-y-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-[2.5rem] p-6 space-y-6 backdrop-blur-xl">
            <h3 className="text-sm font-black uppercase tracking-widest text-white flex items-center gap-2">
              <AlertTriangle className="text-indigo-400" size={16} />
              <span>Domain Knowledge Gap Audit</span>
            </h3>

            <p className="text-slate-400 text-xs leading-relaxed">
              Real-time semantic trace comparing departures expertise against corporate coverage indices. 
              The following gap areas lack coverage:
            </p>

            <div className="space-y-3">
              {handoffGaps.map((gap, i) => (
                <div key={i} className="bg-slate-950 border border-slate-850 rounded-xl p-3.5 flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0" />
                  <p className="text-xs text-slate-300 font-semibold">{gap}</p>
                </div>
              ))}

              {handoffGaps.length === 0 && (
                <div className="text-center p-4 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
                  Domain coverage is fully stable. No immediate gaps flagged.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
