import React from 'react';
import { X, Sparkles } from 'lucide-react';

interface TailorNoticeModalProps {
  open: boolean;
  onClose: () => void;
}

export const TailorNoticeModal: React.FC<TailorNoticeModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#07110d]/45 p-4 backdrop-blur-md animate-in fade-in duration-200">
      <div className="panel-air w-full max-w-lg overflow-hidden rounded-[30px] border border-white/60 shadow-2xl">
        <div className="flex items-start justify-between border-b border-border px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3 pr-4">
            <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-2xl bg-accent-emerald/15 text-accent-emerald">
              <Sparkles className="h-4.5 w-4.5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold tracking-tight text-primary-600">Tailoring in progress</h3>
              <p className="text-xs text-slate-500">Your tailored application is being prepared.</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-full border border-border bg-white p-2 text-slate-500 transition hover:border-primary-200 hover:text-primary-600"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-5 sm:px-6">
          <div className="space-y-4 rounded-[24px] bg-white/70 p-5 text-sm leading-7 text-slate-700 border border-border/50">
            <p className="text-base leading-relaxed text-slate-800">
              Job will appear in{' '}
              <span className="font-bold underline decoration-accent-emerald decoration-2 underline-offset-4 text-primary-700">
                Applications
              </span>{' '}
              section once the resume is ready.
            </p>
          </div>

          <div className="mt-5 flex justify-end">
            <button
              onClick={onClose}
              className="rounded-full bg-primary-600 px-5 py-2 text-xs font-semibold text-white transition hover:bg-[#20352e]"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
