import React, { useEffect, useState } from 'react';
import type { Job } from '../types/api';
import { jobsApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const FilteredJobsBoard: React.FC = () => {
  const { user } = useAuth();
  const [filteredJobs, setFilteredJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');

  const loadFilteredJobs = async () => {
    try {
      setLoading(true);
      const data = await jobsApi.listJobs(false, 50, 0, false, user?.id);
      setFilteredJobs(data);
    } catch (err) {
      console.error('Failed to load filtered jobs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFilteredJobs();
  }, [user?.id]);

  const displayedJobs = filteredJobs.filter(
    (job) =>
      job.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      job.company.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (job.filter_reason || '').toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="industrial-panel flex flex-col justify-between gap-5 p-5 sm:flex-row sm:items-center sm:p-7">
        <div>
          <p className="section-index mb-2">06 / FILTER LOG</p>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="hero-type text-2xl font-bold text-primary-600">Below-threshold roles</h2>
            <span className="border border-accent-rose bg-surface-raised px-2.5 py-1 font-mono text-[10px] font-semibold uppercase text-accent-rose">
              {filteredJobs.length} Unmatched (&lt;70%)
            </span>
          </div>
          <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">
            Jobs that did not meet the match threshold or experience tolerance. Saved here for full transparency.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search filtered jobs..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-48 border border-primary-600 bg-surface px-3.5 py-2 text-sm text-primary-600 outline-none placeholder:text-slate-400 focus:border-accent-rose sm:w-64"
          />
          <button
            onClick={loadFilteredJobs}
            disabled={loading}
            className="border border-primary-600 bg-surface px-3.5 py-2 text-xs font-semibold text-primary-600 transition hover:bg-primary-600 hover:text-white disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {loading && filteredJobs.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-border border-t-accent-rose" />
        </div>
      ) : displayedJobs.length === 0 ? (
        <div className="border border-border bg-surface py-16 px-4 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center border border-primary-600 bg-background font-mono text-sm text-slate-500">
            0
          </div>
          <h3 className="text-base font-semibold text-primary-600">No filtered jobs found</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            When the app evaluates scraped listings against your background, any roles that fall below the match threshold will appear here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {displayedJobs.map((job) => {
            const score = job.match_score ?? 50;
            return (
              <div
                key={job.id}
                className="group flex flex-col justify-between border border-border bg-surface p-5 shadow-[3px_3px_0_rgba(29,28,26,0.08)] transition hover:-translate-y-0.5 hover:border-primary-600"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-primary-600 transition group-hover:text-accent-rose">
                        {job.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
                        <span className="font-medium text-primary-600">{job.company}</span>
                        <span>•</span>
                        <span className="text-slate-500">{job.source}</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end">
                      <span className="border border-accent-rose bg-surface-raised px-2.5 py-1 font-mono text-xs font-bold text-accent-rose">
                        {score}% Match
                      </span>
                      <span className="text-[10px] text-slate-500 mt-1">Below threshold</span>
                    </div>
                  </div>

                  <div className="mt-4 space-y-1 border-l-2 border-accent-rose bg-background p-3 text-xs text-slate-600">
                    <div className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase text-accent-rose">
                      <span className="h-1.5 w-1.5 bg-accent-rose" />
                      Filter explanation
                    </div>
                    <p className="text-xs leading-relaxed text-slate-600">
                      {job.filter_reason || 'Does not meet candidate core skills or required domain background.'}
                    </p>
                  </div>

                  <div className="mt-3 text-xs text-slate-400 line-clamp-3 leading-relaxed">
                    {job.description}
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-border pt-3">
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-slate-400 hover:text-slate-200 transition underline underline-offset-4"
                  >
                    View original listing
                  </a>
                  <span className="text-[11px] text-slate-500">
                    Saved processing cost
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
