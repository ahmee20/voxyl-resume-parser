import React from 'react';
import { X, AlertCircle } from 'lucide-react';

interface BatchUnavailableModalProps {
  open: boolean;
  onClose: () => void;
}

export const BatchUnavailableModal: React.FC<BatchUnavailableModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-primary-600/65 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="panel-air w-full max-w-lg overflow-hidden border border-primary-600 shadow-[6px_6px_0_#1D1C1A]">
        <div className="flex items-start justify-between border-b border-border px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3 pr-4">
            <div className="mt-0.5 flex h-9 w-9 items-center justify-center bg-amber-500 text-white shrink-0">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <p className="section-index text-amber-700">SERVICE NOTICE</p>
              <h3 className="hero-type text-lg font-bold text-primary-600">Batch Tailoring Notice</h3>
              <p className="text-xs text-slate-500">Multiple generation feature update</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="border border-primary-600 bg-surface p-2 text-slate-500 transition hover:bg-primary-600 hover:text-white"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-5 sm:px-6 space-y-4">
          <div className="space-y-3 border-l-2 border-amber-500 bg-background p-4 text-sm leading-relaxed text-slate-700">
            <p className="font-semibold text-primary-700">
              The multiple generations feature is currently facing a technical issue.
            </p>
            <p className="text-slate-600 text-xs sm:text-sm">
              Please tailor jobs individually by clicking <strong className="text-primary-700">Tailor Now</strong> on each job card at the moment.
            </p>
            <p className="text-slate-500 text-xs italic">
              We know this is not the optimal experience and our team is actively working on restoring full parallel generation. Thank you for your patience!
            </p>
          </div>

          <div className="flex justify-end pt-2">
            <button
              onClick={onClose}
              className="border border-primary-600 bg-primary-600 px-5 py-2 text-xs font-bold text-white shadow-[2px_2px_0_#1D1C1A] hover:bg-primary-700 transition"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
