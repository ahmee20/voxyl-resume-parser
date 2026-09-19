import React from 'react';
import { X, Sparkles } from 'lucide-react';

interface TailorNoticeModalProps {
  open: boolean;
  onClose: () => void;
}

export const TailorNoticeModal: React.FC<TailorNoticeModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-primary-600/65 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="panel-air w-full max-w-lg overflow-hidden border border-primary-600">
        <div className="flex items-start justify-between border-b border-border px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3 pr-4">
            <div className="mt-0.5 flex h-9 w-9 items-center justify-center bg-accent-rose text-white">
              <Sparkles className="h-4.5 w-4.5" />
            </div>
            <div className="space-y-1">
              <p className="section-index">PROCESS ACTIVE</p><h3 className="hero-type text-lg font-bold text-primary-600">Tailoring in progress</h3>
              <p className="text-xs text-slate-500">Your tailored application is being prepared.</p>
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

        <div className="px-5 py-5 sm:px-6">
          <div className="space-y-4 border-l-2 border-accent-rose bg-background p-5 text-sm leading-7 text-slate-700">
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
              className="border border-primary-600 bg-accent-rose px-5 py-2 text-xs font-bold text-white shadow-[2px_2px_0_#1D1C1A]"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
