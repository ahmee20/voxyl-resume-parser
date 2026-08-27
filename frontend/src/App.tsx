import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { AuthWall } from './components/AuthWall';
import { ProfileSetup } from './components/ProfileSetup';
import { ResumeUpload } from './components/ResumeUpload';
import { JobDiscoveryBoard } from './components/JobDiscoveryBoard';
import { ApplicationTracker } from './components/ApplicationTracker';
import { ApplicationTimelineModal } from './components/ApplicationTimelineModal';
import type { Resume } from './types/api';

const ACTIVE_TAB_KEY = 'voxyl.activeTab';
const DASHBOARD_BATCH_KEY = 'voxyl.dashboard.showLatestBatch';

const DashboardContent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'jobs' | 'applications' | 'profile'>(() => {
    const cached = sessionStorage.getItem(ACTIVE_TAB_KEY);
    if (cached === 'dashboard' || cached === 'jobs' || cached === 'applications' || cached === 'profile') {
      return cached;
    }
    return 'dashboard';
  });
  const [activeResume, setActiveResume] = useState<Resume | null>(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | null>(null);
  const [applicationIds, setApplicationIds] = useState<number[]>([]);
  const [showLatestDashboardJobs, setShowLatestDashboardJobs] = useState(false);
  const [mountedTabs, setMountedTabs] = useState<Set<'dashboard' | 'jobs' | 'applications' | 'profile'>>(
    () => new Set(['dashboard'])
  );
  const dashboardBatchKey = user?.id ? `${DASHBOARD_BATCH_KEY}.${user.id}` : null;

  useEffect(() => {
    sessionStorage.setItem(ACTIVE_TAB_KEY, activeTab);
  }, [activeTab]);

  useEffect(() => {
    setMountedTabs((current) => {
      if (current.has(activeTab)) {
        return current;
      }
      const next = new Set(current);
      next.add(activeTab);
      return next;
    });
  }, [activeTab]);

  useEffect(() => {
    if (!dashboardBatchKey) {
      return;
    }
    const cached = sessionStorage.getItem(dashboardBatchKey);
    setShowLatestDashboardJobs(cached === 'true');
  }, [dashboardBatchKey]);

  useEffect(() => {
    if (!dashboardBatchKey) {
      return;
    }
    sessionStorage.setItem(dashboardBatchKey, String(showLatestDashboardJobs));
  }, [dashboardBatchKey, showLatestDashboardJobs]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin mb-3" />
        <p className="text-xs text-slate-500">Verifying session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen text-primary-600 flex flex-col">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
        <main className="flex-1 flex items-center justify-center">
          <AuthWall />
        </main>
      </div>
    );
  }

  if (user && !user.profile_completed) {
    return (
      <div className="min-h-screen text-primary-600 flex flex-col">
        <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
        <ProfileSetup mode="onboarding" />
      </div>
    );
  }

  const handleApplicationStarted = (appId: number | null | undefined) => {
    if (typeof appId !== 'number' || !Number.isFinite(appId) || appId <= 0) {
      return;
    }
    setApplicationIds((prev) => [appId, ...prev.filter((id) => id !== appId)]);
    setSelectedApplicationId(appId);
  };

  return (
    <div className="min-h-screen text-primary-600 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 w-full max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-10 space-y-8">
        {mountedTabs.has('dashboard') && (
          <div className="space-y-8" hidden={activeTab !== 'dashboard'}>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.12fr_0.88fr]">
              <section className="hero-grid-line relative overflow-hidden rounded-[34px] px-7 py-8 sm:px-10 sm:py-10">
                <div className="relative z-10 max-w-2xl space-y-6">
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.32em] text-accent-emerald">
                      AI job search workspace
                    </p>
                    <h1 className="hero-type text-[clamp(3.25rem,7vw,6.5rem)] font-semibold leading-[0.9] text-primary-600">
                      Voxyl
                    </h1>
                    <p className="max-w-xl text-base leading-8 text-slate-600 sm:text-lg">
                      Voxyl keeps your search focused, your resume ready, and your preferences saved so you can move
                      faster. It gives you a cleaner starting point every time, with less resetting and more time
                      spent on the opportunities that actually matter.
                    </p>
                  </div>

                  <p className="max-w-2xl text-sm leading-7 text-slate-600">
                    <strong className="font-semibold text-primary-600">Aim</strong> is making it easier for everyone
                    to find and apply for jobs. <strong className="font-semibold text-primary-600">Impact</strong> is
                    saving time every visit. <strong className="font-semibold text-primary-600">Voxyl Resume</strong>{' '}
                    keeps your tailored resumes and cover letters ready when you need them.
                  </p>
                </div>
              </section>

              <ResumeUpload onUploadSuccess={(res) => setActiveResume(res)} />
            </div>

            <JobDiscoveryBoard
              activeResume={activeResume}
              onApplicationStarted={handleApplicationStarted}
              latestOnly={true}
              showLatestBatch={showLatestDashboardJobs}
              showLoadJobsButton={false}
              onDiscoverySuccess={() => setShowLatestDashboardJobs(true)}
            />
          </div>
        )}

        {mountedTabs.has('jobs') && (
          <div hidden={activeTab !== 'jobs'}>
            <JobDiscoveryBoard
              activeResume={activeResume}
              onApplicationStarted={handleApplicationStarted}
              latestOnly={false}
              showLatestBatch={true}
              showLoadJobsButton={true}
              onDiscoverySuccess={() => {
                setShowLatestDashboardJobs(true);
                setActiveTab('dashboard');
              }}
            />
          </div>
        )}

        {mountedTabs.has('applications') && (
          <div hidden={activeTab !== 'applications'}>
            <ApplicationTracker
              applicationIds={applicationIds}
              userId={user?.id}
              onSelectApplication={(id) => setSelectedApplicationId(id)}
            />
          </div>
        )}

        {mountedTabs.has('profile') && (
          <div hidden={activeTab !== 'profile'}>
            <ProfileSetup mode="profile" />
          </div>
        )}
      </main>

      <ApplicationTimelineModal
        applicationId={selectedApplicationId}
        userId={user?.id}
        onClose={() => setSelectedApplicationId(null)}
      />

      <footer className="mt-10 border-t border-border/80 py-6 bg-white/65 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1440px] flex-col items-center justify-between gap-3 px-4 text-xs text-slate-500 sm:flex-row sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <img src="/voxyl-mark.png" alt="Voxyl" className="h-5 w-auto" />
            <span>Voxyl</span>
          </div>
          <span>Resume tailoring and outreach workspace</span>
        </div>
      </footer>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}
