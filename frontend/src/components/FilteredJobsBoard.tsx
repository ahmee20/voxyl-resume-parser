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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800/80 backdrop-blur-xl">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white tracking-tight">Filtered opportunities</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
              {filteredJobs.length} Unmatched (&lt;70%)
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Jobs that did not meet the match threshold or experience tolerance. Saved here for full transparency.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search filtered jobs..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="px-3.5 py-1.5 bg-slate-800/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 w-48 sm:w-64"
          />
          <button
            onClick={loadFilteredJobs}
            disabled={loading}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-300 rounded-xl transition"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {loading && filteredJobs.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-7 h-7 border-2 border-rose-500/30 border-t-rose-500 rounded-full animate-spin" />
        </div>
      ) : displayedJobs.length === 0 ? (
        <div className="text-center py-16 px-4 bg-slate-900/30 border border-slate-800/50 rounded-2xl">
          <div className="w-12 h-12 rounded-2xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-center mx-auto mb-3 text-slate-400 font-mono text-sm">
            0
          </div>
          <h3 className="text-base font-medium text-slate-200">No filtered jobs found</h3>
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
                className="bg-slate-900/50 hover:bg-slate-900/70 border border-slate-800/80 hover:border-slate-700/80 rounded-2xl p-5 transition flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-slate-100 text-base group-hover:text-rose-300 transition">
                        {job.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
                        <span className="font-medium text-slate-300">{job.company}</span>
                        <span>•</span>
                        <span className="text-slate-500">{job.source}</span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end">
                      <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        {score}% Match
                      </span>
                      <span className="text-[10px] text-slate-500 mt-1">Below threshold</span>
                    </div>
                  </div>

                  <div className="mt-4 p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 space-y-1">
                    <div className="flex items-center gap-1.5 text-rose-400 font-medium text-[11px] uppercase tracking-wider">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                      Filter explanation
                    </div>
                    <p className="text-slate-300 text-xs leading-relaxed">
                      {job.filter_reason || 'Does not meet candidate core skills or required domain background.'}
                    </p>
                  </div>

                  <div className="mt-3 text-xs text-slate-400 line-clamp-3 leading-relaxed">
                    {job.description}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between">
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
