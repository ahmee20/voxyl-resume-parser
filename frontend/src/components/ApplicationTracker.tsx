import React, { useEffect, useMemo, useState } from 'react';
import { Building2, ChevronRight, CheckCircle2, FileText, Layers, MapPin, Search } from 'lucide-react';
import type { Job } from '../types/api';
import { jobsApi } from '../services/api';

interface ApplicationTrackerProps {
  applicationIds: number[];
  userId?: number | null;
  onSelectApplication: (id: number) => void;
}

export const ApplicationTracker: React.FC<ApplicationTrackerProps> = ({
  applicationIds,
  userId,
  onSelectApplication,
}) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const loadTailoredJobs = async () => {
    if (!userId) {
      setJobs([]);
      return;
    }

    try {
      setIsLoading(true);
      const data = await jobsApi.listJobs(undefined, 100, 0, false, userId);
      setJobs(
        data.filter((job) => {
          const status = job.application?.status;
          return !!job.application && status !== 'tailoring';
        })
      );
    } catch {
      setJobs([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadTailoredJobs();
  }, [userId, applicationIds.length]);

  const displayedJobs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return jobs;

    return jobs.filter((job) => {
      const location = job.apollo_enrichment?.location || job.apollo_enrichment?.country || '';
      const status = job.application?.status || '';
      return (
        job.title.toLowerCase().includes(query) ||
        job.company.toLowerCase().includes(query) ||
        location.toLowerCase().includes(query) ||
        status.toLowerCase().includes(query) ||
        (job.description || '').toLowerCase().includes(query)
      );
    });
  }, [jobs, searchQuery]);

  return (
    <div className="space-y-5">
      <div className="rounded-[34px] px-2 py-2">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-accent-emerald">
              Tailored jobs
            </p>
            <h2 className="hero-type text-2xl font-semibold text-primary-600">Jobs with tailored resumes</h2>
            <p className="max-w-2xl text-sm leading-7 text-slate-500">
              These are the jobs where Voxyl has already prepared a tailored resume and outreach assets for you.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search tailored jobs"
                className="w-56 rounded-full border border-border bg-white/90 py-2.5 pl-9 pr-4 text-sm text-primary-600 outline-none transition focus:border-primary-400"
              />
            </div>
            <span className="rounded-full border border-border bg-white/90 px-3 py-1.5 text-xs font-mono text-slate-500">
              {displayedJobs.length} ready
            </span>
          </div>
        </div>
      </div>

      {isLoading && jobs.length === 0 ? (
        <div className="rounded-[28px] bg-white/45 p-10 text-center text-sm text-slate-500">
          Loading tailored jobs...
        </div>
      ) : displayedJobs.length === 0 ? (
        <div className="rounded-[28px] bg-white/45 p-10 text-center space-y-3">
          <Layers className="mx-auto h-8 w-8 text-slate-400" />
          <h3 className="text-base font-semibold text-primary-600">No tailored jobs yet</h3>
          <p className="mx-auto max-w-md text-sm leading-7 text-slate-500">
            Tailor a few jobs first, then they will appear here with the actual job details and saved assets.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {displayedJobs.map((job) => {
            const app = job.application;
            const location = job.apollo_enrichment?.location || job.apollo_enrichment?.country;
            const description = (job.description || '').trim();
            const snippet =
              description.length > 180 ? `${description.slice(0, 180).trim()}...` : description || 'No description available.';

            return (
              <article key={job.id} className="rounded-[28px] bg-white/70 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                        Tailored
                      </span>
                      {app?.ats_score ? (
                        <span className="rounded-full border border-border bg-white/90 px-2.5 py-1 text-[10px] font-mono text-slate-500">
                          ATS {app.ats_score}%
                        </span>
                      ) : null}
                    </div>
                    <h3 className="hero-type text-xl font-semibold text-primary-600">{job.title}</h3>
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                      <span className="inline-flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-slate-400" />
                        {job.company}
                      </span>
                      {location ? <span className="text-slate-300">•</span> : null}
                      {location ? (
                        <span className="inline-flex items-center gap-1.5">
                          <MapPin className="h-3.5 w-3.5 text-slate-400" />
                          {location}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>

                <p className="mt-4 text-sm leading-7 text-slate-600">{snippet}</p>

                <div className="mt-4 flex flex-wrap gap-2">
                  <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-xs text-slate-600">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    Resume ready
                  </div>
                  {app?.email_draft ? (
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-xs text-slate-600">
                      <FileText className="h-3.5 w-3.5 text-accent-emerald" />
                      Email drafted
                    </div>
                  ) : null}
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-white/60 pt-4">
                  <span className="text-[11px] text-slate-400">
                    Click through for the tailored assets and application details.
                  </span>
                  {app ? (
                    <button
                      onClick={() => onSelectApplication(app.id)}
                      className="inline-flex items-center gap-2 rounded-full bg-accent-rose px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#e36457]"
                    >
                      Open assets
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};
