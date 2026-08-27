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
const normalizePath = (pathname: string) => {
  const trimmed = pathname.replace(/\/+$/, '');
  return trimmed === '' ? '/' : trimmed;
};

const PublicLegalPage: React.FC<{
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}> = ({ title, lastUpdated, children }) => {
  return (
    <div className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="site-shell">
        <div className="mx-auto max-w-3xl rounded-[32px] border border-white/60 bg-white/88 p-6 shadow-[0_20px_60px_rgba(18,32,26,0.08)] backdrop-blur-xl sm:p-10">
          <div className="mb-8 flex items-center gap-3">
            <img src="/voxyl-mark.png" alt="Voxyl" className="h-10 w-auto" />
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-accent-emerald">Voxyl</p>
              <h1 className="text-2xl font-semibold tracking-tight text-primary-600 sm:text-3xl">{title}</h1>
            </div>
          </div>

          <p className="mb-8 text-sm text-slate-500">Last updated: {lastUpdated}</p>

          <div className="space-y-5 text-sm leading-7 text-slate-600">{children}</div>
        </div>
      </div>
    </div>
  );
};

const PrivacyPage: React.FC = () => (
  <PublicLegalPage title="Privacy Policy" lastUpdated="August 27, 2026">
    <p>
      Voxyl stores the information needed to run the app, including your account details, uploaded resumes, job and
      application data, and any Google authorization data you choose to connect.
    </p>
    <p>
      We use this data to sign you in, tailor resumes, manage job applications, and keep your session working across
      visits.
    </p>
    <p>
      We do not sell your personal data. We only share information with the services required to provide the app, such
      as your hosting, database, authentication, and connected AI or enrichment providers.
    </p>
    <p>
      If you do not want Voxyl to keep using this data, disconnect your account and stop using the service. You can ask
      the site owner to remove your data if needed.
    </p>
  </PublicLegalPage>
);

const TermsPage: React.FC = () => (
  <PublicLegalPage title="Terms of Service" lastUpdated="August 27, 2026">
    <p>
      Voxyl is provided as a job search and application assistant. You agree to use it responsibly and to review any
      automated output before submitting it anywhere.
    </p>
    <p>
      You are responsible for the accuracy of the information you upload and for complying with the rules of any job
      board, employer, or third-party service you connect.
    </p>
    <p>
      The service is offered on an as-is basis. The site owner may update, pause, or change the service at any time.
    </p>
    <p>
      If you do not agree with these terms, do not use the service.
    </p>
  </PublicLegalPage>
);

const HomePage: React.FC = () => (
  <div className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
    <div className="site-shell">
      <div className="mx-auto grid max-w-4xl gap-6 rounded-[36px] border border-white/60 bg-white/88 p-6 shadow-[0_20px_60px_rgba(18,32,26,0.08)] backdrop-blur-xl lg:grid-cols-[1.05fr_0.95fr] sm:p-10">
        <section className="space-y-6">
          <div className="flex items-center gap-3">
            <img src="/voxyl-mark.png" alt="Voxyl" className="h-10 w-auto" />
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-accent-emerald">Public home</p>
          </div>
          <div className="space-y-4">
            <h1 className="hero-type text-[clamp(2.6rem,6vw,4.8rem)] font-semibold leading-[0.95] text-primary-600">
              Voxyl Resume
            </h1>
            <p className="max-w-xl text-base leading-8 text-slate-600 sm:text-lg">
              Voxyl Resume is a focused workspace for job seekers who want their resumes, preferences, and applications
              organized in one place.
            </p>
            <p className="max-w-xl text-sm leading-7 text-slate-600">
              This page is intentionally simple and stays out of the main app navigation. It exists so Google and other
              services have a clean public home page for the product.
            </p>
          </div>
        </section>

        <aside className="rounded-[28px] bg-white/70 p-6">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-accent-emerald">What it is</p>
            <ul className="space-y-3 text-sm leading-7 text-slate-600">
              <li>Resume tailoring and job search tools.</li>
              <li>Private candidate profile and application workspace.</li>
              <li>Built for the Voxyl Resume app and its connected services.</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  </div>
);

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
  const isApplicationSessionActive = selectedApplicationId !== null;
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
              suspendAutoRefresh={isApplicationSessionActive}
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
              suspendAutoRefresh={isApplicationSessionActive}
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
              suspendAutoRefresh={isApplicationSessionActive}
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
  const pathname = typeof window !== 'undefined' ? normalizePath(window.location.pathname) : '/';

  if (pathname === '/privacy') {
    return <PrivacyPage />;
  }

  if (pathname === '/terms') {
    return <TermsPage />;
  }

  if (pathname === '/home') {
    return <HomePage />;
  }

  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}
