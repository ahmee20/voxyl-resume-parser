import React from 'react';
import { useAuth } from '../context/AuthContext';

export const AuthWall: React.FC = () => {
  const { loginWithGoogle, devMockLogin } = useAuth();

  return (
    <div id="auth-wall" className="flex min-h-[72vh] items-start justify-center px-4 py-6 sm:py-8">
      <div className="grid w-full max-w-[1240px] gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <section className="hero-grid-line relative overflow-hidden rounded-[36px] px-2 py-2">
          <div className="relative min-h-full overflow-hidden rounded-[36px] px-6 py-8 sm:px-10 sm:py-10">
            <div className="relative z-10 max-w-2xl space-y-6">
              <div className="space-y-4">
                <h1 className="hero-type text-[clamp(3.4rem,7.5vw,6.2rem)] font-semibold leading-[0.92] text-primary-600">
                  Voxyl
                </h1>
                <p className="max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
                  Voxyl helps you move faster without the noise. Keep your resume, preferred roles, and target
                  countries ready in one place, then return to a workspace that feels clear, calm, and easy to continue.
                </p>
              </div>

              <p className="max-w-2xl text-sm leading-8 text-slate-500 sm:text-base">
                <strong className="font-semibold text-primary-600">Voxyl</strong> is built for people who want a
                sharper starting point, less repetition, and a job search that feels organized from the first click.
              </p>

              <p className="max-w-2xl text-sm leading-7 text-slate-600">
                <strong className="font-semibold text-primary-600">Aim</strong> is making it easier for everyone to
                find and apply for jobs. <strong className="font-semibold text-primary-600">Impact</strong> is saving
                time every visit. <strong className="font-semibold text-primary-600">Voxyl Resume</strong> keeps your
                tailored resumes and cover letters ready when you need them.
              </p>
            </div>
          </div>
        </section>

        <section className="self-start rounded-[36px] bg-white/55 p-8 sm:p-10">
          <div className="space-y-6">
            <div className="space-y-3">
              <img src="/voxyl-mark.png" alt="Voxyl" className="h-12 w-auto" />
              <p className="text-xs font-semibold uppercase tracking-[0.34em] text-accent-emerald">
                Sign in to continue
              </p>
              <p className="max-w-md text-sm leading-7 text-slate-500">
                Use Google to open your workspace and keep your session available between visits.
              </p>
            </div>

            <div className="space-y-3">
              <button
                onClick={loginWithGoogle}
                className="flex w-full items-center justify-center gap-3 rounded-full bg-accent-rose px-5 py-3.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#e36457]"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#FFFFFF"
                    d="M21.35 11.1H12v2.9h5.36c-.23 1.25-.97 2.31-2.08 3.02v2.5h3.36c1.96-1.8 3.1-4.46 3.1-7.42 0-.79-.07-1.54-.19-2.25z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M12 22c2.7 0 4.97-.89 6.62-2.42l-3.36-2.5c-.94.62-2.12.98-3.26.98-2.5 0-4.62-1.68-5.38-3.95H3.19v2.54A9.98 9.98 0 0 0 12 22z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M6.62 14.11A5.99 5.99 0 0 1 6.32 12c0-.73.13-1.43.3-2.11V7.35H3.19A9.98 9.98 0 0 0 2 12c0 1.61.39 3.13 1.19 4.65l3.43-2.54z"
                  />
                  <path
                    fill="#FFFFFF"
                    d="M12 5.95c1.48 0 2.81.51 3.87 1.51l2.9-2.9C16.98 2.95 14.7 2 12 2a10 10 0 0 0-8.81 5.35l3.43 2.54C7.38 7.63 9.5 5.95 12 5.95z"
                  />
                </svg>
                Continue with Google
              </button>

              <button
                onClick={devMockLogin}
                className="w-full rounded-full bg-white/80 px-5 py-3 text-sm font-medium text-slate-600 transition hover:bg-white hover:text-primary-600"
              >
                Development quick access
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
