import React, { useState, useEffect } from 'react';
import type { Job, Resume } from '../types/api';
import { jobsApi, applicationsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { JobDetailsModal } from './JobDetailsModal';
import {
  Briefcase,
  Compass,
  Building2,
  Mail,
  ExternalLink,
  Loader2,
  Users,
  Layers,
  CheckCircle2,
  RefreshCw,
  FileText,
  CheckSquare,
  Square
} from 'lucide-react';

const JOBS_CACHE_TTL_MS = 30 * 60 * 1000;

interface JobDiscoveryBoardProps {
  activeResume: Resume | null;
  onApplicationStarted: (applicationId: number) => void;
  latestOnly?: boolean;
  showLatestBatch?: boolean;
  showLoadJobsButton?: boolean;
  onDiscoverySuccess?: () => void;
}

const AVAILABLE_COUNTRIES = [
  { code: 'REMOTE', name: 'Worldwide / Remote' },
  { code: 'US', name: 'United States' },
  { code: 'CA', name: 'Canada' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'AU', name: 'Australia' },
  { code: 'IN', name: 'India' },
  { code: 'PK', name: 'Pakistan' },
  { code: 'SG', name: 'Singapore' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'AE', name: 'United Arab Emirates' },
  { code: 'SA', name: 'Saudi Arabia' },
  { code: 'IE', name: 'Ireland' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'JP', name: 'Japan' },
];

const hasTailoredAssets = (app?: Job['application']) =>
  Boolean(app?.tailored_html || app?.pdf_url || app?.email_draft);

export const JobDiscoveryBoard: React.FC<JobDiscoveryBoardProps> = ({
  activeResume,
  onApplicationStarted,
  latestOnly = false,
  showLatestBatch = true,
  showLoadJobsButton = true,
  onDiscoverySuccess,
}) => {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([]);
  const [inspectingJob, setInspectingJob] = useState<Job | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState<boolean>(false);

  const [selectedCountries, setSelectedCountries] = useState<string[]>(
    user?.preferred_countries?.length ? user.preferred_countries : ['REMOTE', 'US']
  );

  const [discoveryStats, setDiscoveryStats] = useState<{
    queries?: string[];
    countries?: string[];
    scraped?: number;
    persisted?: number;
  } | null>(null);
  const [runningJobId, setRunningJobId] = useState<number | null>(null);
  const preferredRoles = user?.preferred_roles?.slice(0, 3) ?? [];
  const allJobsCacheKey = `voxyl.jobs.cache.${user?.id ?? 'guest'}.all`;
  const latestJobsCacheKey = `voxyl.jobs.cache.${user?.id ?? 'guest'}.latest`;
  const cacheKey = latestOnly ? latestJobsCacheKey : allJobsCacheKey;
  const defaultCountries = user?.preferred_countries?.length ? user.preferred_countries.slice(0, 3) : ['REMOTE', 'US'];

  const persistCache = (nextJobs: Job[], nextStats: typeof discoveryStats, nextCountries: string[]) => {
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({
        jobs: nextJobs,
        discoveryStats: nextStats,
        selectedCountries: nextCountries,
        cachedAt: Date.now(),
      })
    );
  };

  const fetchJobs = async (force = false, statsOverride?: typeof discoveryStats) => {
    try {
      setIsLoading(true);
      if (latestOnly && !showLatestBatch && !force) {
        setJobs([]);
        return;
      }
      if (latestOnly) {
        const cachedValue = sessionStorage.getItem(cacheKey);
        if (cachedValue) {
          try {
            const parsed = JSON.parse(cachedValue) as {
              jobs?: Job[];
              discoveryStats?: typeof discoveryStats;
              selectedCountries?: string[];
              cachedAt?: number;
            };
            if (parsed.cachedAt && Date.now() - parsed.cachedAt < JOBS_CACHE_TTL_MS) {
              setJobs(parsed.jobs ?? []);
              setDiscoveryStats(parsed.discoveryStats ?? null);
              if (parsed.selectedCountries?.length) {
                setSelectedCountries(parsed.selectedCountries.slice(0, 3));
              }
              return;
            }
          } catch {
            sessionStorage.removeItem(cacheKey);
          }
        }
        setJobs([]);
        return;
      }
      const limit = 100;
      const data = await jobsApi.listJobs(undefined, limit, 0, latestOnly, user?.id);
      setJobs(data);
      persistCache(data, statsOverride ?? discoveryStats, selectedCountries);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const nextCountries = user?.preferred_countries?.length ? user.preferred_countries.slice(0, 3) : defaultCountries;
    setSelectedCountries(nextCountries);

    if (latestOnly && !showLatestBatch) {
      setJobs([]);
      setDiscoveryStats(null);
      setIsLoading(false);
      return;
    }

    const cachedValue = sessionStorage.getItem(cacheKey);
    if (latestOnly) {
      if (cachedValue) {
        try {
          const parsed = JSON.parse(cachedValue) as {
            jobs?: Job[];
            discoveryStats?: typeof discoveryStats;
            selectedCountries?: string[];
            cachedAt?: number;
          };
          if (parsed.cachedAt && Date.now() - parsed.cachedAt < JOBS_CACHE_TTL_MS) {
            setJobs(parsed.jobs ?? []);
            setDiscoveryStats(parsed.discoveryStats ?? null);
            if (parsed.selectedCountries?.length) {
              setSelectedCountries(parsed.selectedCountries.slice(0, 3));
            }
            setIsLoading(false);
            return;
          }
        } catch {
          sessionStorage.removeItem(cacheKey);
        }
      }
      setJobs([]);
      setDiscoveryStats(null);
      setIsLoading(false);
      return;
    }

    if (cachedValue) {
      try {
        const parsed = JSON.parse(cachedValue) as {
          jobs?: Job[];
          discoveryStats?: typeof discoveryStats;
          selectedCountries?: string[];
          cachedAt?: number;
        };
        if (parsed.cachedAt && Date.now() - parsed.cachedAt < JOBS_CACHE_TTL_MS) {
          setJobs(parsed.jobs ?? []);
          setDiscoveryStats(parsed.discoveryStats ?? null);
          if (parsed.selectedCountries?.length) {
            setSelectedCountries(parsed.selectedCountries.slice(0, 3));
          }
          setIsLoading(false);
          return;
        }
      } catch {
        sessionStorage.removeItem(cacheKey);
      }
    }

    void fetchJobs();
  }, [cacheKey, user?.id, latestOnly, showLatestBatch]);

  useEffect(() => {
    persistCache(jobs, discoveryStats, selectedCountries);
  }, [jobs, discoveryStats, selectedCountries, cacheKey]);

  const startPolling = (durationSec = 30, intervalMs = 2500) => {
    const startTime = Date.now();
    const interval = setInterval(async () => {
      if (Date.now() - startTime > durationSec * 1000) {
        clearInterval(interval);
        return;
      }
      await fetchJobs(true);
    }, intervalMs);
  };

  const toggleJobSelection = (jobId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedJobIds((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  const selectAllUntailored = () => {
    const untailoredIds = jobs
      .filter((j) => {
        const app = j.application;
        return !app || (!(app.status === 'saved' || app.status === 'pending_approval' || app.status === 'sent') && !hasTailoredAssets(app));
      })
      .map((j) => j.id);
    setSelectedJobIds(untailoredIds);
  };

  const clearSelection = () => {
    setSelectedJobIds([]);
  };

  const handleDiscover = async () => {
    if (!user || !activeResume) return;

    try {
      setIsDiscovering(true);
      setDiscoveryStats(null);
      const res = await jobsApi.discoverJobs(user.id, {
        preferredRoles: user.preferred_roles?.slice(0, 3),
        countries: selectedCountries,
        resumeId: activeResume.id,
      });
      const nextStats = {
        queries: res.search_queries,
        countries: res.preferred_countries,
        scraped: res.scraped_count,
        persisted: res.persisted_job_ids.length,
      };
      setDiscoveryStats(nextStats);
      setSelectedJobIds([]);
      setJobs(res.jobs ?? []);
      persistCache(res.jobs ?? [], nextStats, selectedCountries);
      onDiscoverySuccess?.();
    } catch {
      // ignore
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleBatchTailor = async () => {
    if (!user || !activeResume || selectedJobIds.length === 0) return;

    try {
      setIsBatchRunning(true);
      await applicationsApi.runBatch(selectedJobIds, activeResume.id, user.id);
      setSelectedJobIds([]);
      await fetchJobs(true);
      startPolling(45, 2500);
    } catch {
      // ignore
    } finally {
      setIsBatchRunning(false);
    }
  };

  const handleCardClick = (job: Job) => {
    const app = job.application;
    const isTailored = !!app && (app.status === 'saved' || app.status === 'pending_approval' || app.status === 'sent' || hasTailoredAssets(app));

    if (isTailored && app) {
      onApplicationStarted(app.id);
    } else {
      // Open Job Details Modal to inspect full description, recruiter info, and trigger tailoring
      setInspectingJob(job);
    }
  };

  const handleSingleJobTailor = async (job: Job, e: React.MouseEvent) => {
    e.stopPropagation();
    const app = job.application;
    const isTailored = !!app && (app.status === 'saved' || app.status === 'pending_approval' || app.status === 'sent' || hasTailoredAssets(app));

    if (isTailored && app) {
      onApplicationStarted(app.id);
      return;
    }

    if (!activeResume) return;
    try {
      setRunningJobId(job.id);
      const res = await applicationsApi.runSingleJob(job.id, activeResume.id, user?.id);
      onApplicationStarted(res.application_id);
      await fetchJobs();
      startPolling(25, 2000);
    } catch {
      // ignore
    } finally {
      setRunningJobId(null);
    }
  };

  const currentCountryLabel = (code?: string | null) =>
    AVAILABLE_COUNTRIES.find((item) => item.code === code)?.name || code || 'Country not specified';

  return (
    <div className="relative space-y-6 pb-20">
      <div className="rounded-[34px] px-6 py-5 sm:px-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-white/60 px-3 py-1 text-xs text-slate-500">
                Saved preferences
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {preferredRoles.length > 0 ? (
                preferredRoles.map((role) => (
                  <span
                    key={role}
                    className="inline-flex items-center rounded-full bg-white/70 px-3 py-1 text-xs font-medium text-primary-600"
                  >
                    {role}
                  </span>
                ))
              ) : (
                <span className="rounded-full bg-white/70 px-3 py-1 text-xs text-slate-500">
                  Add preferred roles in Profile
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {selectedCountries.map((country) => (
                <div
                  key={country}
                  className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-2 text-xs text-slate-600"
                >
                  <span>{currentCountryLabel(country)}</span>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:min-w-[240px]">
            {showLoadJobsButton && (
              <button
                onClick={() => fetchJobs()}
                disabled={isLoading}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-white/70 px-4 py-2.5 text-xs font-medium text-slate-600 transition hover:bg-white/90 hover:text-primary-600"
                title="Load job listings"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                Load jobs
              </button>
            )}
            {latestOnly && (
              <button
                onClick={handleDiscover}
                disabled={!activeResume || isDiscovering}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-accent-rose px-4 py-3 text-xs font-semibold text-white transition hover:bg-[#e36457] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isDiscovering ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Finding matches...
                  </>
                ) : (
                  <>
                    <Compass className="w-4 h-4" />
                    Discover jobs
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {discoveryStats && (
          <div className="mt-4 text-sm text-slate-600">
            Found <strong className="font-semibold text-primary-600">{discoveryStats.scraped}</strong> matching opportunities.
          </div>
        )}
      </div>

      {/* Discovered Jobs List Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-primary-600">
            <Briefcase className="w-4 h-4 text-primary-500" />
            <span>{latestOnly ? 'Latest discovered opportunities' : 'All discovered jobs'}</span>
            <span className="rounded-full border border-border bg-white/90 px-2 py-0.5 font-mono text-xs text-slate-500">
              {jobs.length} {latestOnly ? 'in Latest Batch' : 'Total'}
            </span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Click a card to open the full job details, or select checkboxes to tailor several jobs at once.
          </p>
        </div>

        {jobs.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={selectAllUntailored}
              className="rounded-full border border-border bg-white/90 px-3 py-1.5 text-xs text-slate-600 transition-colors hover:border-primary-200 hover:text-primary-600"
            >
              Select All Untailored
            </button>
            {selectedJobIds.length > 0 && (
              <button
                onClick={clearSelection}
                className="rounded-full px-2.5 py-1.5 text-xs text-slate-500 hover:text-primary-600"
              >
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      {/* Loading / Empty States */}
      {latestOnly && !showLatestBatch ? (
        <div className="rounded-[28px] bg-white/45 p-10 text-center space-y-3">
          <Compass className="w-10 h-10 text-slate-400 mx-auto" />
          <h4 className="text-sm font-semibold text-primary-600">No batch loaded yet</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Use the dashboard discovery action to load the latest batch from your saved roles and countries.
          </p>
        </div>
      ) : isLoading && jobs.length === 0 ? (
        <div className="rounded-[28px] bg-white/45 p-10 text-center space-y-3">
          <Loader2 className="w-8 h-8 text-primary-500 animate-spin mx-auto" />
          <p className="text-xs text-slate-500">Loading job listings...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-[28px] bg-white/45 p-10 text-center space-y-3">
          <Compass className="w-10 h-10 text-slate-400 mx-auto" />
          <h4 className="text-sm font-semibold text-primary-600">No jobs discovered yet</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Jobs will appear here after you load them from the dashboard.
          </p>
        </div>
      ) : (
        /* Jobs Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((job) => {
            const isProcessing = runningJobId === job.id;
            const apollo = job.apollo_enrichment;
            const app = job.application;
            const isTailored = !!app && (app.status === 'saved' || app.status === 'pending_approval' || app.status === 'sent' || hasTailoredAssets(app));
            const isTailoring = !!app && app.status === 'tailoring' && !hasTailoredAssets(app);
            const isSelected = selectedJobIds.includes(job.id);

              return (
              <div
                key={job.id}
                onClick={() => handleCardClick(job)}
                className={`rounded-[28px] bg-white/70 p-5 transition-colors flex flex-col justify-between space-y-4 cursor-pointer group relative ${
                  isSelected
                    ? 'ring-1 ring-primary-200'
                    : 'hover:bg-white/80'
                }`}
              >
                {/* Top Status & Checkbox */}
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-3 flex-1">
                      {/* Multi-select Checkbox */}
                      <button
                        type="button"
                        onClick={(e) => toggleJobSelection(job.id, e)}
                        className="mt-0.5 text-slate-400 hover:text-primary-500 transition-colors shrink-0"
                        title={isSelected ? 'Deselect job' : 'Select job for batch tailoring'}
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-primary-500" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-400 group-hover:text-slate-500" />
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {isTailored ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-emerald-200 text-emerald-700 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Ready
                            </span>
                          ) : isTailoring ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-amber-200 text-amber-700 flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin" /> Tailoring
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-border text-slate-500">
                              New
                            </span>
                          )}

                          {app?.ats_score && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-border text-slate-600 font-mono">
                              ATS {app.ats_score}%
                            </span>
                          )}

                          {job.match_score && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-border text-slate-600 font-mono">
                              {job.match_score}% Match
                            </span>
                          )}
                        </div>

                        <h3 className="text-sm font-semibold text-primary-600 leading-snug group-hover:text-primary-500 transition-colors line-clamp-1">
                          {job.title || 'Untitled Position'}
                        </h3>
                        <p className="mt-1 text-[11px] uppercase tracking-[0.2em] text-slate-400">
                          {currentCountryLabel(apollo?.location || apollo?.country)}
                        </p>
                      </div>
                    </div>

                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-slate-400 hover:text-primary-600 p-1 shrink-0"
                      title="View original job posting"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-500 pl-7">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" />
                    <span>{job.company || 'Unknown Company'}</span>
                  </div>
                </div>

                {apollo && (
                  <div className="space-y-2 text-xs ml-7">
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                      <span className="flex items-center gap-1">
                        <Layers className="w-3 h-3" /> Company insights
                      </span>
                      {apollo.verified && <span className="text-slate-500 font-medium">Verified</span>}
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      {apollo.domain && (
                        <div className="text-slate-500 truncate">
                          Domain: <span className="text-slate-700">{apollo.domain}</span>
                        </div>
                      )}
                      {apollo.estimated_num_employees && (
                        <div className="text-slate-500 flex items-center gap-1">
                          <Users className="w-3 h-3 text-slate-400" />
                          <span className="text-slate-700">{apollo.estimated_num_employees} employees</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Recruiter Email & Action Footer */}
                <div className="flex items-center justify-between text-xs pt-2 border-t border-white/60 ml-7">
                  <div className="flex items-center gap-1.5 text-slate-500 truncate max-w-[220px]">
                    <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    {job.recruiter_email ? (
                      <span className="text-slate-700 font-mono text-[11px] truncate" title={job.recruiter_email}>
                        {job.recruiter_email}
                      </span>
                    ) : apollo?.recruiter_name ? (
                      <span className="text-slate-600 text-[11px] truncate" title={apollo.recruiter_name}>
                        {apollo.recruiter_name} {apollo.recruiter_title ? `(${apollo.recruiter_title})` : ''}
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[11px]">Direct outreach ready</span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {isTailored && app ? (
                      <button
                        onClick={(e) => handleSingleJobTailor(job, e)}
                        className="flex items-center gap-1.5 rounded-full bg-accent-rose px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#e36457]"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>View Resume &amp; Letter</span>
                      </button>
                    ) : isTailoring ? (
                      <button
                        disabled
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border text-slate-500 text-xs font-medium cursor-not-allowed"
                      >
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Tailoring...</span>
                      </button>
                    ) : (
                      <button
                        onClick={(e) => handleSingleJobTailor(job, e)}
                        disabled={!activeResume || isProcessing}
                        className="flex items-center gap-1.5 rounded-full border border-border bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-primary-200 hover:text-primary-600"
                      >
                        {isProcessing ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Starting...</span>
                          </>
                        ) : (
                          <>
                            <span>Tailor Now</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Floating Multi-Select Action Bar */}
      {selectedJobIds.length > 0 && (
          <div className="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-4 rounded-full bg-white/90 px-5 py-3 backdrop-blur-xl">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-semibold text-primary-600">
              {selectedJobIds.length} Job{selectedJobIds.length > 1 ? 's' : ''} Selected
            </span>
          </div>

          <div className="h-4 w-px bg-border" />

          <button
            onClick={handleBatchTailor}
            disabled={!activeResume || isBatchRunning}
            className="flex items-center gap-2 rounded-full bg-accent-emerald px-5 py-2 text-xs font-bold text-white transition-colors hover:bg-[#18b486] disabled:opacity-50"
          >
            {isBatchRunning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Launching Parallel Agents...
              </>
            ) : (
              <>
                Generate Resumes &amp; Cover Emails ({selectedJobIds.length})
              </>
            )}
          </button>

          <button
            onClick={clearSelection}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Job Details Modal */}
      {inspectingJob && (
        <JobDetailsModal
          job={inspectingJob}
          activeResume={activeResume}
          onClose={() => setInspectingJob(null)}
          onTailorStarted={(appId) => {
            setInspectingJob(null);
            onApplicationStarted(appId);
            fetchJobs();
            startPolling(30, 2000);
          }}
          onViewTailored={(appId) => {
            setInspectingJob(null);
            onApplicationStarted(appId);
          }}
        />
      )}
    </div>
  );
};
