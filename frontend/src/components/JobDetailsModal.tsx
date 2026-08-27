import React, { useState } from 'react';
import type { Job, Resume } from '../types/api';
import { applicationsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  X,
  Building2,
  ExternalLink,
  Loader2,
  Mail,
  Users,
  CheckCircle2,
  Layers,
  FileText,
  Percent,
} from 'lucide-react';

interface JobDetailsModalProps {
  job: Job | null;
  activeResume: Resume | null;
  onClose: () => void;
  onTailorStarted: (applicationId: number) => void;
  onViewTailored: (applicationId: number) => void;
}

const hasTailoredAssets = (app: Job['application']) =>
  Boolean(app?.tailored_html || app?.pdf_url || app?.email_draft);

export const JobDetailsModal: React.FC<JobDetailsModalProps> = ({
  job,
  activeResume,
  onClose,
  onTailorStarted,
  onViewTailored,
}) => {
  const [isStarting, setIsStarting] = useState(false);
  const { user } = useAuth();

  if (!job) return null;

  const app = job.application;
  const isTailored = !!app && (app.status === 'saved' || app.status === 'pending_approval' || app.status === 'sent' || hasTailoredAssets(app));
  const isTailoring = !!app && app.status === 'tailoring' && !hasTailoredAssets(app);
  const apollo = job.apollo_enrichment;

  const handleStartTailoring = async () => {
    if (!activeResume || !user) return;
    try {
      setIsStarting(true);
      const res = await applicationsApi.runSingleJob(job.id, activeResume.id, user.id);
      onTailorStarted(res.application_id);
    } catch {
      // ignore
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#07110d]/30 p-4 backdrop-blur-md">
      <div
        className="panel-air flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-[32px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div className="space-y-2 pr-6">
            <div className="flex flex-wrap items-center gap-2">
              {isTailored ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Tailored and ready
                </span>
              ) : isTailoring ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Tailoring in progress
                </span>
              ) : (
                <span className="rounded-full border border-border bg-surface/60 px-2.5 py-1 text-xs font-medium text-slate-500">
                  Discovered
                </span>
              )}

              {job.match_score && (
                <span className="inline-flex items-center gap-1 rounded-full border border-primary-200 bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-600">
                  <Percent className="h-3.5 w-3.5" />
                  {job.match_score}% Match
                </span>
              )}
            </div>

            <h2 className="hero-type text-xl font-semibold tracking-tight text-primary-600">{job.title}</h2>

            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5 text-slate-400" />
                {job.company}
              </span>
              {(apollo?.location || apollo?.country) && (
                <>
                  <span className="text-slate-300">|</span>
                  <span className="text-slate-500">{apollo.location || apollo.country}</span>
                </>
              )}
              <span className="text-slate-300">|</span>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary-600 hover:underline"
              >
                View original posting
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-full border border-border bg-white p-2 text-slate-500 transition hover:border-primary-200 hover:text-primary-600"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="space-y-6">
            {apollo && (
              <div className="rounded-[24px] border border-border bg-white/85 p-4">
                <div className="mb-3 flex items-center justify-between text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <Layers className="h-4 w-4 text-primary-500" />
                    Company insights
                  </span>
                  {apollo.verified && <span className="text-emerald-600">Verified</span>}
                </div>

                <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                  {apollo.recruiter_name && (
                    <div className="flex items-center gap-2 text-slate-600">
                      <Users className="h-4 w-4 text-slate-400" />
                      <span>
                        Recruiter: <strong className="text-primary-600">{apollo.recruiter_name}</strong>
                        {apollo.recruiter_title ? ` (${apollo.recruiter_title})` : ''}
                      </span>
                    </div>
                  )}
                  {job.recruiter_email && (
                    <div className="flex items-center gap-2 text-slate-600">
                      <Mail className="h-4 w-4 text-primary-500" />
                      <span>
                        Email: <strong className="font-mono text-primary-600">{job.recruiter_email}</strong>
                      </span>
                    </div>
                  )}
                {apollo.domain && (
                  <div className="text-slate-600">
                    Website: <span className="font-mono text-primary-600">{apollo.domain}</span>
                  </div>
                )}
                {(apollo.location || apollo.country) && (
                  <div className="text-slate-600">
                    Location: <span className="text-primary-600">{apollo.location || apollo.country}</span>
                  </div>
                )}
                {apollo.industry && (
                  <div className="text-slate-600">
                    Industry: <span className="text-primary-600">{apollo.industry}</span>
                  </div>
                  )}
                </div>
              </div>
            )}

            {job.filter_reason && (
              <div className="rounded-[24px] border border-border bg-white/80 p-4 text-sm leading-7 text-slate-600">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Candidate match assessment
                </div>
                {job.filter_reason}
              </div>
            )}

            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Full job description
              </h4>
              <div className="max-h-[320px] overflow-y-auto rounded-[24px] border border-border bg-white/85 p-5 text-sm leading-7 text-slate-700 whitespace-pre-wrap soft-scrollbar">
                {job.description || 'No detailed description provided.'}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-full border border-border bg-white/90 px-4 py-2 text-xs font-medium text-slate-600 transition hover:border-primary-200 hover:text-primary-600"
          >
            Close
          </button>

          <div className="flex items-center gap-3">
            {isTailored && app ? (
              <button
                onClick={() => {
                  onClose();
                  onViewTailored(app.id);
                }}
                className="inline-flex items-center gap-2 rounded-full bg-accent-rose px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#e36457]"
              >
                <FileText className="h-4 w-4" />
                View resume and letter
              </button>
            ) : isTailoring ? (
              <button
                disabled
                className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-5 py-2.5 text-xs font-semibold text-amber-700"
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                Tailoring in progress
              </button>
            ) : (
              <button
                onClick={handleStartTailoring}
                disabled={!activeResume || !user || isStarting}
                className="inline-flex items-center gap-2 rounded-full bg-primary-600 px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#20352e] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Preparing your match...
                  </>
                ) : (
                  <>Generate tailored resume and letter</>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
