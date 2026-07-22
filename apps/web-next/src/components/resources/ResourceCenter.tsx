import React, { useState, useEffect, useRef } from 'react';
import { FileText, UploadCloud, ChevronRight, Loader2, X, Trash2, Tag, AlignLeft, Link as LinkIcon, Check, MessageSquare } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

import { ConfirmationModal } from '../ui/ConfirmationModal';

export default function ResourceCenter({ group, user, onBack }: any) {
  const { toast } = useToast();
  const [categories, setCategories] = useState<string[]>([]);
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 12; // 3x4 grid fits better
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');
  const [viewingPdfUrl, setViewingPdfUrl] = useState<string | null>(null);
  const [viewingFileName, setViewingFileName] = useState<string>('');
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Upload metadata (III: description + category)
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadCategory, setUploadCategory] = useState('General');
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  // Delete confirmation
  const [deleteConfirm, setDeleteConfirm] = useState<{ visible: boolean; resourceId: number | null; fileName: string }>({
    visible: false,
    resourceId: null,
    fileName: ''
  });

  // Resource Feedback
  const [selectedResourceId, setSelectedResourceId] = useState<number | null>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState('');
  const [loadingComments, setLoadingComments] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchResources = async () => {
    setLoading(true);
    if (group.id === undefined || group.id === null) {
      setLoading(false);
      return;
    }
    try {
      const [res, config] = await Promise.all([
        ApiService.getGroupResources(group.id, currentPage, pageSize),
        ApiService.getSystemConfig()
      ]);
      
      if (res && res.items) {
        setResources(res.items);
        setTotalPages(res.pages || 1);
      } else if (Array.isArray(res)) {
        // Fallback for legacy untyped response
        setResources(res);
      }
      
      setCategories(config.resource_categories);
      if (config.resource_categories.length > 0 && !config.resource_categories.includes(uploadCategory)) {
        setUploadCategory(config.resource_categories[0]);
      }
    } catch (err: any) {
      console.error("Fetch Data Error:", err);
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, [group.id, user.id, currentPage]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      setError("Only PDF files are allowed.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("File must be 10MB or smaller.");
      return;
    }

    setPendingFile(file);
    setShowUploadForm(true);
    setError('');
    if (e.target) e.target.value = '';
  };

  const handleConfirmUpload = async () => {
    if (!pendingFile) return;

    setUploading(true);
    setUploadProgress(0);
    setError('');
    setShowUploadForm(false);

    try {
      // 1. Get pre-signed URL params from backend with metadata
      const resData = await ApiService.getPresignedUpload(
        group.id, user.id, pendingFile.name, pendingFile.type, uploadDescription, uploadCategory
      );
      
      const uploadData = resData.upload_url_data || resData;
      if (!uploadData || !uploadData.fields) {
        throw new Error("Invalid presigned URL response from server");
      }

      // 2. Upload directly to S3 with XMLHttpRequest for progress tracking (III: progress bar)
      await new Promise<void>((resolve, reject) => {
        const formData = new FormData();
        Object.keys(uploadData.fields).forEach(key => {
          formData.append(key, uploadData.fields[key]);
        });
        formData.append('file', pendingFile);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', uploadData.url, true);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const pct = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(pct);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error("AWS Upload Failed"));
          }
        };

        xhr.onerror = () => reject(new Error("Network Error"));
        xhr.send(formData);
      });

      setUploadProgress(100);
      fetchResources();
      setPendingFile(null);
      setUploadDescription('');
      setUploadCategory('General');
      toast('success', 'PDF uploaded successfully!');
    } catch (err: any) {
      console.error("Upload Error:", err);
      setError(String(err.message || err));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDeleteResource = (resourceId: number, fileName: string) => {
    setDeleteConfirm({ visible: true, resourceId, fileName });
  };

  const confirmDeleteResource = async () => {
    const { resourceId } = deleteConfirm;
    if (!resourceId) return;

    try {
      await ApiService.deleteResource(resourceId);
      setResources(prev => prev.filter(r => r.id !== resourceId));
      toast('success', 'Resource deleted.');
    } catch (err: any) {
      setError(err.message || 'Failed to delete resource.');
    } finally {
      setDeleteConfirm({ visible: false, resourceId: null, fileName: '' });
    }
  };

  const handleCopyLink = async (url: string, id: number) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      toast('success', 'Shareable link copied to clipboard!');
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      toast('error', 'Failed to copy link.');
    }
  };

  const handleOpenComments = async (resourceId: number) => {
    setSelectedResourceId(resourceId);
    setLoadingComments(true);
    try {
      const data = await ApiService.getResourceComments(resourceId);
      setComments(data);
    } catch(err) {
      toast('error', 'Failed to load feedback');
    } finally {
      setLoadingComments(false);
    }
  };

  const handleAddComment = async () => {
    if(!newComment.trim() || !selectedResourceId) return;
    try {
      await ApiService.addResourceComment(selectedResourceId, newComment);
      setNewComment('');
      handleOpenComments(selectedResourceId); // reload
      toast('success', 'Feedback added!');
    } catch(err) {
      toast('error', 'Failed to add feedback');
    }
  };


  const getCategoryStyle = (category: string) => {
    const colors: Record<string, string> = {
      'General': 'bg-slate-700 text-slate-300',
      'Lecture Notes': 'bg-blue-900/40 text-blue-300',
      'Reference': 'bg-emerald-900/40 text-emerald-300',
      'Cheat Sheet': 'bg-amber-900/40 text-amber-300',
      'Assessment': 'bg-rose-900/40 text-rose-300',
      'Other': 'bg-purple-900/40 text-purple-300',
    };
    return colors[category] || 'bg-slate-800 text-slate-400 border border-slate-700';
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 uppercase tracking-widest font-bold mb-8">
          <span className="hover:text-indigo-400 cursor-pointer transition-colors" onClick={onBack}>Dashboard</span>
          <ChevronRight size={12} />
          <span className="text-indigo-500">Resource Center</span>
        </div>

        <div className="flex justify-between items-center mb-10">
          <div>
            <h2 className="text-3xl font-bold text-white mb-2">Study Materials</h2>
            <p className="text-slate-400">Secure PDFs shared within {group.name}</p>
          </div>

          <div>
            <input ref={fileInputRef} type="file" id="pdf-upload" accept="application/pdf" className="hidden" onChange={handleFileSelect} disabled={uploading} />
            <label
              htmlFor="pdf-upload"
              aria-label="Upload PDF file"
              className={`flex items-center gap-2 px-6 py-3 rounded-2xl font-bold transition-all shadow-lg cursor-pointer ${uploading ? 'bg-indigo-600/50 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500'
                } text-white`}
            >
              {uploading ? <Loader2 size={20} className="animate-spin" /> : <UploadCloud size={20} />}
              {uploading ? 'Uploading...' : 'Upload PDF'}
            </label>
          </div>
        </div>

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-xl mb-6 flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')}><X size={16} /></button>
          </div>
        )}

        {/* III: Upload progress bar */}
        {uploading && (
          <div className="mb-6 bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-wider">Uploading to S3...</span>
              <span className="text-indigo-400 font-bold">{uploadProgress}%</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-200 ease-out"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading ? (
            <div className="col-span-2 flex items-center justify-center py-20">
              <Loader2 size={32} className="animate-spin text-indigo-500" />
            </div>
          ) : resources.length === 0 ? (
            <div className="col-span-2 py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl">
              <UploadCloud size={48} className="mx-auto text-slate-700 mb-4" />
              <p className="text-slate-400 font-bold mb-2">No study materials yet</p>
              <p className="text-slate-600 text-sm">Be the first to share a PDF with your group!</p>
            </div>
          ) : (
            resources.map(res => (
              <div key={res.id} className="bg-slate-900 border border-slate-800 p-5 rounded-2xl hover:border-slate-700 transition-colors group relative">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center shrink-0 border border-orange-500/20">
                    <FileText size={24} className="text-orange-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-bold truncate" title={res.file_name}>{res.file_name}</p>

                    {/* III: Category badge */}
                    <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md mt-1 mb-1 ${getCategoryStyle(res.category)}`}>
                      {res.category}
                    </span>

                    {/* III: Description */}
                    {res.description && (
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{res.description}</p>
                    )}

                    <div className="flex items-center gap-3 mt-2">
                      <p className="text-xs text-slate-600 uppercase tracking-wider">{res.uploaded_by}</p>
                      <span className="text-slate-700">·</span>
                      <p className="text-xs text-slate-600">{new Date(res.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => { setViewingPdfUrl(res.view_url); setViewingFileName(res.file_name); }}
                    className="flex-[2] py-2 bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors text-sm font-bold text-slate-300 flex items-center justify-center gap-2"
                    aria-label={`View ${res.file_name}`}
                  >
                    <FileText size={16} /> View
                  </button>

                  {/* Shareable Link Button */}
                  <button
                    onClick={() => handleCopyLink(res.view_url, res.id)}
                    className={`flex-1 py-2 rounded-xl transition-colors text-sm font-bold flex items-center justify-center gap-2 ${copiedId === res.id ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      }`}
                    aria-label={`Copy link for ${res.file_name}`}
                    title="Copy Shareable Link (Valid for 1 Hour)"
                  >
                    {copiedId === res.id ? <Check size={16} /> : <LinkIcon size={16} />}
                  </button>

                  <button
                    onClick={() => handleOpenComments(res.id)}
                    className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors text-sm font-bold text-slate-300 flex items-center justify-center"
                    aria-label="Feedback"
                    title="Feedback"
                  >
                    <MessageSquare size={16} />
                  </button>

                  {/* III: Delete button (owner or admin) */}
                  {(res.uploaded_by === user.full_name || user.role === 'Admin') && (
                    <button
                      onClick={() => handleDeleteResource(res.id, res.file_name)}
                      className="flex-1 py-2 bg-rose-900/20 hover:bg-rose-900/40 border border-rose-500/20 rounded-xl transition-colors text-rose-400 flex justify-center items-center"
                      aria-label={`Delete ${res.file_name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-12 flex justify-center items-center gap-4">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-3 bg-slate-900 border border-white/5 rounded-2xl text-slate-400 hover:text-white hover:border-indigo-500/50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronRight size={20} className="rotate-180" />
            </button>
            
            <div className="flex gap-2">
              {[...Array(totalPages)].map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i + 1)}
                  className={`w-10 h-10 rounded-xl font-black text-xs transition-all ${
                    currentPage === i + 1 
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                      : 'bg-slate-900 border border-white/5 text-slate-500 hover:text-white'
                  }`}
                >
                  {i + 1}
                </button>
              ))}
            </div>

            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-3 bg-slate-900 border border-white/5 rounded-2xl text-slate-400 hover:text-white hover:border-indigo-500/50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}
      </div>

      {/* Feedback Modal */}
      {selectedResourceId !== null && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 w-full max-w-md shadow-2xl flex flex-col max-h-[80vh]">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <MessageSquare size={20} className="text-indigo-400" /> Resource Feedback
              </h3>
              <button onClick={() => setSelectedResourceId(null)}>
                <X size={20} className="text-slate-500 hover:text-white transition-colors" />
              </button>
            </div>
            
            <div className="overflow-y-auto flex-1 mb-4 pr-2 space-y-3">
              {loadingComments ? (
                 <div className="flex justify-center p-4"><Loader2 className="animate-spin text-indigo-500" /></div>
              ) : comments.length === 0 ? (
                <p className="text-slate-400 text-center text-sm font-medium py-4">No feedback yet. Be the first!</p>
              ) : (
                comments.map(c => (
                  <div key={c.id} className="bg-slate-800 p-3 rounded-xl border border-slate-700">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-bold text-slate-200">{c.user_name} <span className="text-[10px] bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded-md ml-1">{c.role}</span></span>
                      <span className="text-xs text-slate-500">{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-sm text-slate-300">{c.content}</p>
                  </div>
                ))
              )}
            </div>

            <div className="mt-auto">
              <textarea
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                placeholder="Leave feedback..."
                className="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-white text-sm focus:ring-2 focus:ring-indigo-500 resize-none mb-3"
                rows={2}
              />
              <button
                onClick={handleAddComment}
                disabled={!newComment.trim()}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-bold transition-all shadow-lg"
              >
                Post Feedback
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Metadata Form Modal */}
      {showUploadForm && pendingFile && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-white">Upload Details</h3>
              <button onClick={() => { setShowUploadForm(false); setPendingFile(null); }}>
                <X size={20} className="text-slate-500 hover:text-white transition-colors" />
              </button>
            </div>

            <div className="mb-4">
              <div className="bg-slate-800 rounded-xl p-3 flex items-center gap-3 mb-4">
                <FileText size={20} className="text-orange-400 shrink-0" />
                <span className="text-white font-medium truncate text-sm">{pendingFile.name}</span>
                <span className="text-slate-500 text-xs shrink-0">{(pendingFile.size / 1024 / 1024).toFixed(1)} MB</span>
              </div>

              <label className="block text-xs text-slate-400 font-bold uppercase mb-1.5">
                <Tag size={12} className="inline mr-1" /> Category
              </label>
              <select
                value={uploadCategory}
                onChange={e => setUploadCategory(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-white mb-4 focus:ring-2 focus:ring-indigo-500"
              >
                {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
              </select>

              <label className="block text-xs text-slate-400 font-bold uppercase mb-1.5">
                <AlignLeft size={12} className="inline mr-1" /> Description (Optional)
              </label>
              <textarea
                value={uploadDescription}
                onChange={e => setUploadDescription(e.target.value)}
                maxLength={300}
                rows={3}
                placeholder="Brief description of this document..."
                className="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-white text-sm focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => { setShowUploadForm(false); setPendingFile(null); }}
                className="flex-1 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-bold transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmUpload}
                className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30"
              >
                Upload PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Secure PDF Viewer — open in new tab to bypass Chrome's cross-origin iframe block */}
      {viewingPdfUrl && (
        <div
          className="fixed inset-0 bg-slate-950/95 backdrop-blur-sm z-[100] flex flex-col p-4 md:p-8"
          onContextMenu={(e) => e.preventDefault()}
        >
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <h3 className="text-white font-bold truncate max-w-xs">{viewingFileName}</h3>
            <div className="flex items-center gap-3">
              <a
                href={viewingPdfUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl transition-colors font-bold text-sm shadow-lg"
              >
                <FileText size={16} /> Open PDF in New Tab
              </a>
              <button
                onClick={() => setViewingPdfUrl(null)}
                className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl transition-colors font-bold shadow-lg"
              >
                <X size={20} /> Close
              </button>
            </div>
          </div>
          {/* Google Docs Viewer works with any public URL and is not blocked by Chrome */}
          <div
            className="flex-1 w-full bg-slate-900 rounded-2xl overflow-hidden shadow-2xl relative select-none"
            onContextMenu={(e) => e.preventDefault()}
          >
            <iframe
              src={`https://docs.google.com/viewer?url=${encodeURIComponent(viewingPdfUrl)}&embedded=true`}
              className="w-full h-full border-0 select-none"
              title="PDF Viewer"
              allow="fullscreen"
            />
          </div>
          <p className="text-center text-xs text-slate-600 mt-3">View-only via Google Docs Viewer. Use "Open PDF in New Tab" for best experience.</p>
        </div>
      )}

      <ConfirmationModal
        isOpen={deleteConfirm.visible}
        title="Confirm Deletion"
        message={`Are you sure you want to delete "${deleteConfirm.fileName}"? This action is permanent and cannot be undone.`}
        confirmText="Delete Resource"
        onConfirm={confirmDeleteResource}
        onCancel={() => setDeleteConfirm({ visible: false, resourceId: null, fileName: '' })}
        type="danger"
      />
    </div>
  );
}
