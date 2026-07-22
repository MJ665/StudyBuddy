'use client';
import { Download, X } from 'lucide-react';

export default function KTPdfPreviewModal({ attachment, onClose }: { attachment: any, onClose: () => void }) {
  if (!attachment || attachment.file_type !== 'application/pdf') return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/90 backdrop-blur-sm p-8">
      <div className="w-full max-w-5xl h-[85vh] bg-slate-900 border border-slate-800 rounded-[2.5rem] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <h3 className="font-bold text-white">{attachment.filename}</h3>
          <div className="flex gap-2">
            <a href={attachment.download_url} download target="_blank" rel="noreferrer" className="flex items-center gap-2 text-indigo-400 hover:text-indigo-300">
              <Download size={16} /> Download
            </a>
            <button onClick={onClose} className="text-slate-400 hover:text-white p-2">
              <X size={16} />
            </button>
          </div>
        </div>
        <iframe
          src={attachment.download_url}
          className="flex-1 w-full bg-slate-800"
          title={attachment.filename}
        />
      </div>
    </div>
  );
}