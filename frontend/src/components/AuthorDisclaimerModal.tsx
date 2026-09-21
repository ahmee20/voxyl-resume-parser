import React from 'react';
import { X, ExternalLink, Coins } from 'lucide-react';

interface AuthorDisclaimerModalProps {
  open: boolean;
  onClose: () => void;
}

export const AuthorDisclaimerModal: React.FC<AuthorDisclaimerModalProps> = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-primary-600/70 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="panel-air w-full max-w-lg overflow-hidden border border-primary-600 shadow-[8px_8px_0_#1D1C1A]">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border bg-surface px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3 pr-4">
            <div className="mt-0.5 flex h-10 w-10 items-center justify-center bg-amber-500 text-white shadow-[2px_2px_0_#1D1C1A] shrink-0">
              <Coins className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <p className="section-index text-amber-700 font-mono text-[10px] tracking-wider uppercase">
                HONEST DISCLAIMER
              </p>
              <h3 className="hero-type text-xl font-bold text-primary-600">
                The Author is Poor
              </h3>
              <p className="text-xs text-slate-500">A quick message regarding free API quotas</p>
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

        {/* Content */}
        <div className="px-5 py-5 sm:px-6 space-y-4 bg-background">
          <div className="space-y-3 border-l-2 border-amber-500 bg-surface p-4 text-sm leading-relaxed text-slate-700">
            <p className="font-semibold text-primary-700">
              Welcome to Voxyl. Please keep the following in mind:
            </p>
            <p className="text-slate-600 text-xs sm:text-sm">
              This application uses a pipeline of <strong>multiple free-tier APIs</strong> (LLMs, scrapers, search engines, and PDF converters), as the author cannot afford dedicated enterprise GPU infrastructure.
            </p>
            <p className="text-slate-600 text-xs sm:text-sm">
              If the system fails, stalls, or behaves unexpectedly, it usually means the <strong>daily free API credits have reached their limit</strong>.
            </p>
            <div className="bg-amber-500/10 p-3 border border-amber-500/30 text-xs text-slate-700 leading-relaxed">
              <strong>Recommended Setup:</strong> For the best experience without rate limits, visit the GitHub repository, clone the project, and run it locally with your own API keys.
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-2.5 pt-2">
            <a
              href="https://github.com/ahmee20/voxyl-resume-parser"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 border border-primary-600 bg-surface px-4 py-2.5 text-xs font-bold text-primary-700 shadow-[2px_2px_0_#1D1C1A] hover:bg-primary-600 hover:text-white transition"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View GitHub Repo
            </a>

            <button
              onClick={onClose}
              className="border border-primary-600 bg-accent-rose px-5 py-2.5 text-xs font-bold text-white shadow-[2px_2px_0_#1D1C1A] hover:-translate-y-0.5 transition"
            >
              I Understand, Continue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
