"use client";
import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle } from 'lucide-react';

interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  onClose?: () => void;
  confirmText?: string;
  cancelText?: string;
  type?: 'warning' | 'danger';
  variant?: 'warning' | 'danger';
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  onClose,
  confirmText = "Confirm",
  cancelText = "Cancel",
  type = "warning",
  variant
}) => {
  const actualType = variant || type;
  const actualCancel = onClose || onCancel;
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCancel}
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
          />
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="relative bg-slate-900 border border-white/10 p-8 rounded-[2rem] max-w-md w-full shadow-2xl"
          >
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-6 ${
              actualType === 'danger' ? 'bg-rose-500/10 text-rose-400' : 'bg-amber-500/10 text-amber-400'
            }`}>
              <AlertTriangle size={24} />
            </div>
            <h3 className="text-xl font-black text-white mb-2">{title}</h3>
            <p className="text-sm text-slate-400 mb-8 leading-relaxed">{message}</p>
            <div className="flex gap-3">
              <button
                onClick={actualCancel}
                className="flex-1 py-3 px-4 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-black text-xs uppercase tracking-widest transition-all"
              >
                {cancelText}
              </button>
              <button
                onClick={onConfirm}
                className={`flex-1 py-3 px-4 rounded-xl font-black text-xs uppercase tracking-widest transition-all text-white shadow-lg ${
                  actualType === 'danger' ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-600/20' : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/20'
                }`}
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
