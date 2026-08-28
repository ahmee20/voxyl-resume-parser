import React, { useEffect, useMemo, useState } from 'react';
import type { ApplicationDetail } from '../types/api';
import { applicationsApi } from '../services/api';
import {
  X,
  CheckCircle2,
  FileText,
  Download,
  Mail,
  ShieldCheck,
  Loader2,
  RefreshCw,
  Copy,
  Check,
  TrendingUp,
  Building2,
  ExternalLink,
} from 'lucide-react';

interface ApplicationTimelineModalProps {
  applicationId: number | null;
  userId?: number | null;
  onRefreshJobs?: () => void;
  onClose: () => void;
}

type ModalTab = 'changes' | 'resume' | 'email' | 'job';

type GapChanges = {
  added_keywords?: Array<string | { keyword: string; evidence?: string }>;
  removed_keywords?: string[];
  summary?: string;
  notes?: string[];
};

const hasTailoredAssets = (detail: ApplicationDetail | null) =>
  !!detail && Boolean(detail.tailored_html || detail.rendered_pdf_url || detail.email_draft);

export const ApplicationTimelineModal: React.FC<ApplicationTimelineModalProps> = ({
  applicationId,
  userId: _userId,
  onRefreshJobs,
  onClose,
}) => {
  const resolvedApplicationId =
    typeof applicationId === 'number' && Number.isFinite(applicationId) && applicationId > 0
      ? applicationId
      : null;

  const cacheKey = resolvedApplicationId ? `voxyl.app_detail.${resolvedApplicationId}` : null;

  const [detail, setDetail] = useState<ApplicationDetail | null>(() => {
    if (!resolvedApplicationId) return null;
    try {
      const raw = sessionStorage.getItem(`voxyl.app_detail.${resolvedApplicationId}`);
      if (!raw) return null;
      return JSON.parse(raw) as ApplicationDetail;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (!resolvedApplicationId) return false;
    try {
      return !sessionStorage.getItem(`voxyl.app_detail.${resolvedApplicationId}`);
    } catch {
      return true;
    }
  });
  const [activeTab, setActiveTab] = useState<ModalTab>('changes');
  const [copiedEmail, setCopiedEmail] = useState(false);

  const fetchDetail = async (force = false) => {
    if (!resolvedApplicationId) return;
    if (!force && cacheKey) {
      try {
        const raw = sessionStorage.getItem(cacheKey);
        if (raw) {
          const parsed = JSON.parse(raw) as ApplicationDetail;
          setDetail(parsed);
          setIsLoading(false);
          return;
        }
      } catch {
        // ignore
      }
    }
    try {
      setIsLoading(true);
      const data = await applicationsApi.getApplication(resolvedApplicationId);
      setDetail(data);
      if (cacheKey) {
        sessionStorage.setItem(cacheKey, JSON.stringify(data));
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!resolvedApplicationId) {
      setDetail(null);
      setIsLoading(false);
      return;
    }
    void fetchDetail(true);
  }, [resolvedApplicationId]);

  useEffect(() => {
    if (
      !resolvedApplicationId ||
      !detail ||
      detail.ats_score != null ||
      !['tailoring', 'saved', 'pending_approval'].includes(detail.status)
    ) return;
    const interval = setInterval(async () => {
      try {
        const data = await applicationsApi.getApplication(resolvedApplicationId);
        setDetail(data);
        if (cacheKey) {
          sessionStorage.setItem(cacheKey, JSON.stringify(data));
        }
      } catch {
        // ignore
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [detail?.status, resolvedApplicationId, cacheKey]);

  const handleCopyEmail = () => {
    if (detail?.email_draft) {
      navigator.clipboard.writeText(detail.email_draft);
      setCopiedEmail(true);
      setTimeout(() => setCopiedEmail(false), 2000);
    }
  };

  const jobLocation = useMemo(
    () =>
      detail?.job_apollo_enrichment?.location ||
      detail?.job_apollo_enrichment?.country ||
      'Location not specified',
    [detail?.job_apollo_enrichment]
  );

  const parsedChanges = useMemo<GapChanges | null>(() => {
    if (!detail?.gap_analysis) return null;
    try {
      const parsed = JSON.parse(detail.gap_analysis) as GapChanges;
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
      return null;
    }
  }, [detail?.gap_analysis]);

  const renderAddedKeywords = (items?: Array<string | { keyword: string; evidence?: string }>) => {
    if (!items?.length) return null;

    return (
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={typeof item === 'string' ? item : item.keyword}
            className="rounded-[16px] border border-emerald-200 bg-emerald-50 px-3 py-2 text-[11px] text-emerald-800"
          >
            <div className="font-semibold">{typeof item === 'string' ? item : item.keyword}</div>
            {typeof item !== 'string' && item.evidence ? (
              <div className="mt-1 text-[10px] leading-5 text-emerald-700">
                Evidence: {item.evidence}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    );
  };

  const renderKeywordChips = (items?: string[], tone: 'added' | 'removed' = 'added') => {
    if (!items?.length) return null;
    const toneClasses =
      tone === 'added'
        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
        : 'bg-rose-50 text-rose-700 border-rose-200';

    return (
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={`${tone}-${item}`}
            className={`rounded-full border px-3 py-1 text-[11px] font-medium ${toneClasses}`}
          >
            {item}
          </span>
        ))}
      </div>
    );
  };

  if (!resolvedApplicationId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#07110d]/30 p-4 backdrop-blur-md">
      <div className="panel-air flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-[32px]">
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div className="space-y-2 pr-6">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="hero-type text-lg font-semibold tracking-tight text-primary-600">
                Application assets
              </h3>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-mono uppercase text-emerald-700">
                App #{resolvedApplicationId}
              </span>
              {detail?.status === 'tailoring' && !hasTailoredAssets(detail) ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Tailoring active
                </span>
              ) : detail?.status === 'saved' || detail?.status === 'pending_approval' || hasTailoredAssets(detail) ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-medium text-emerald-700">
                  <CheckCircle2 className="h-3 w-3" />
                  Ready
                </span>
              ) : null}
            </div>
            <p className="text-sm text-slate-500">
              Review the tailored resume, email draft, and job description.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                void fetchDetail(true);
              }}
              className="rounded-full border border-border bg-white p-2 text-slate-500 transition hover:border-primary-200 hover:text-primary-600"
              title="Refresh application status"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            {onRefreshJobs ? (
              <button
                onClick={() => {
                  onRefreshJobs();
                  void fetchDetail();
                }}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-primary-200 hover:text-primary-600"
                title="Load jobs"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                Load jobs
              </button>
            ) : null}
            <button
              onClick={onClose}
              className="rounded-full border border-border bg-white p-2 text-slate-500 transition hover:border-primary-200 hover:text-primary-600"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="nav-pill mx-4 mt-3 flex items-center gap-1 overflow-x-auto rounded-full px-2 py-2 text-xs">
          <button
            onClick={() => setActiveTab('changes')}
            className={`rounded-full px-3 py-2 font-semibold transition ${
              activeTab === 'changes'
                ? 'bg-primary-600 text-white'
                : 'text-slate-500 hover:text-primary-600'
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5" />
              Changes
            </span>
          </button>

          <button
            onClick={() => setActiveTab('resume')}
            className={`rounded-full px-3 py-2 font-semibold transition ${
              activeTab === 'resume'
                ? 'bg-primary-600 text-white'
                : 'text-slate-500 hover:text-primary-600'
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              Resume
            </span>
          </button>

          <button
            onClick={() => setActiveTab('email')}
            className={`rounded-full px-3 py-2 font-semibold transition ${
              activeTab === 'email'
                ? 'bg-primary-600 text-white'
                : 'text-slate-500 hover:text-primary-600'
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5" />
              Email
            </span>
          </button>

          <button
            onClick={() => setActiveTab('job')}
            className={`rounded-full px-3 py-2 font-semibold transition ${
              activeTab === 'job'
                ? 'bg-primary-600 text-white'
                : 'text-slate-500 hover:text-primary-600'
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" />
              Job description
            </span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {isLoading && !detail ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="mb-3 h-8 w-8 animate-spin text-primary-500" />
              <p className="text-xs text-slate-500">Loading application details...</p>
            </div>
          ) : detail?.status === 'tailoring' && !hasTailoredAssets(detail) ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="mb-4 h-12 w-12 animate-spin text-primary-500" />
              <h4 className="text-base font-semibold text-primary-600">Preparing your match</h4>
              <p className="mt-2 max-w-sm text-center text-sm text-slate-500">
                Your tailored version is being prepared, checked, and packaged for review.
              </p>
            </div>
          ) : detail ? (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-[24px] bg-white/70 p-4">
                  <span className="mb-1 block text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">
                    Applied status
                  </span>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-primary-600">
                      {detail.applied_status === 'yes' ? 'Auto-applied' : 'Ready for manual apply'}
                    </span>
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  </div>
                </div>

                <div className="rounded-[24px] bg-white/70 p-4">
                  <span className="mb-1 block text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">
                    ATS alignment score
                  </span>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-primary-600">
                      {detail.ats_score != null ? `${detail.ats_score} / 100` : 'Pending review'}
                    </span>
                    <ShieldCheck className="h-5 w-5 text-emerald-500" />
                  </div>
                </div>
              </div>

              {activeTab === 'changes' && (
                <div className="rounded-[24px] bg-white/70 p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-primary-500" />
                    <h4 className="text-sm font-semibold text-primary-600">Resume changes and keywords</h4>
                  </div>
                  {parsedChanges ? (
                    <div className="space-y-4 rounded-[20px] bg-white/80 p-4 text-sm leading-7 text-slate-600">
                      {parsedChanges.summary ? (
                        <p className="text-slate-600">{parsedChanges.summary}</p>
                      ) : null}

                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
                          Added keywords
                        </div>
                        {renderAddedKeywords(parsedChanges.added_keywords) || (
                          <div className="text-xs text-slate-500">No added keywords were recorded.</div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                          Removed keywords
                        </div>
                        {renderKeywordChips(parsedChanges.removed_keywords, 'removed') || (
                          <div className="text-xs text-slate-500">No removed keywords were recorded.</div>
                        )}
                      </div>

                      {parsedChanges.notes?.length ? (
                        <div className="space-y-2">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                            Notes
                          </div>
                          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-500">
                            {parsedChanges.notes.map((note) => (
                              <li key={note}>{note}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : detail.gap_analysis ? (
                    <div className="rounded-[20px] bg-white/80 p-4 text-sm leading-7 text-slate-600 whitespace-pre-wrap">
                      {detail.gap_analysis}
                    </div>
                  ) : (
                    <div className="rounded-[20px] bg-white/80 p-4 text-sm text-slate-500">
                      No explicit gap analysis was recorded for this application.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'resume' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-primary-600">Tailored resume</h4>
                    {detail.rendered_pdf_url && (
                      <a
                        href={detail.rendered_pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-full bg-accent-rose px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#e36457]"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download PDF
                      </a>
                    )}
                  </div>

                  {detail.tailored_html ? (
                    <div className="rounded-[24px] bg-white/70 p-4">
                      <div className="mb-3 flex items-center justify-between border-b border-white/60 pb-2 text-[11px] text-slate-500">
                        <span>HTML preview</span>
                        <span className="font-mono text-slate-400">
                          {detail.tailored_html.length} characters
                        </span>
                      </div>
                      <div
                        className="max-h-[500px] overflow-y-auto rounded-[20px] bg-white p-5 text-xs leading-relaxed text-slate-800 soft-scrollbar"
                        dangerouslySetInnerHTML={{ __html: detail.tailored_html }}
                      />
                    </div>
                  ) : (
                    <div className="rounded-[24px] bg-white/70 p-8 text-center text-sm text-slate-500">
                      No tailored preview generated yet.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'email' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-primary-600">Email draft</h4>
                    {detail.email_draft && (
                      <button
                        onClick={handleCopyEmail}
                        className="inline-flex items-center gap-2 rounded-full border border-border bg-white/90 px-4 py-2 text-xs font-medium text-slate-600 transition hover:border-primary-200 hover:text-primary-600"
                      >
                        {copiedEmail ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-emerald-500" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            Copy email
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {detail.email_draft ? (
                    <div className="rounded-[24px] bg-white/70 p-5 text-sm leading-7 text-slate-700 whitespace-pre-wrap">
                      {detail.email_draft}
                    </div>
                  ) : (
                    <div className="rounded-[24px] bg-white/70 p-8 text-center text-sm text-slate-500">
                      No email draft available yet.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'job' && (
                <div className="space-y-4">
                  <div className="rounded-[24px] bg-white/70 p-5">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                      <span className="inline-flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-slate-400" />
                        {detail?.job_company || 'Company not available'}
                      </span>
                      {detail?.job_url ? <span className="text-slate-300">•</span> : null}
                      {detail?.job_url ? (
                        <a
                          href={detail.job_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary-600 hover:underline"
                        >
                          Open posting
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : null}
                    </div>
                    <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                      {jobLocation}
                    </p>
                  </div>

                  <div className="rounded-[24px] bg-white/70 p-5 text-sm leading-7 text-slate-700 whitespace-pre-wrap">
                    {detail?.job_description || 'No detailed description available for this job.'}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          <span className="text-[11px] text-slate-500">Saved in your workspace</span>
          <button
            onClick={onClose}
            className="rounded-full bg-primary-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#20352e]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
