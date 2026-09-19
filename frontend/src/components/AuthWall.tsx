import React from 'react';
import { useAuth } from '../context/AuthContext';

export const AuthWall: React.FC = () => {
  const { loginWithGoogle } = useAuth();

  return (
    <div id="auth-wall" className="flex min-h-[calc(100vh-73px)] items-center justify-center px-4 py-10 sm:px-6">
      <div className="workspace-enter grid w-full max-w-[1240px] border border-primary-600 bg-surface shadow-[8px_8px_0_rgba(29,28,26,0.14)] lg:grid-cols-[1.35fr_0.65fr]">
        <section className="relative flex min-h-[520px] flex-col justify-between overflow-hidden border-b border-primary-600 p-7 lg:border-b-0 lg:border-r lg:p-12">
          <div className="flex items-center justify-between border-b border-border pb-4 font-mono text-[10px] uppercase text-slate-500">
            <span>Workspace protocol 01</span><span>Resume → Match → Apply</span>
          </div>
          <div className="max-w-3xl py-12">
            <p className="section-index mb-5">CAREER APPLICATION SYSTEM</p>
            <h1 className="hero-type text-[clamp(3.6rem,9vw,7.6rem)] font-bold leading-[0.84] text-primary-600">Your search,<br/><span className="text-accent-rose">in motion.</span></h1>
            <p className="mt-8 max-w-xl text-base leading-7 text-slate-600">Parse your resume, find roles that fit, and prepare tailored applications from one focused workspace.</p>
          </div>
          <div className="grid grid-cols-3 border-t border-primary-600 pt-4 font-mono text-[10px] uppercase text-slate-500">
            <span>01 / Parse</span><span>02 / Discover</span><span className="text-right">03 / Apply</span>
          </div>
        </section>

        <section className="flex flex-col justify-between bg-background p-7 sm:p-10">
          <div className="space-y-10">
            <div className="space-y-3">
              <span className="font-mono text-[10px] uppercase text-accent-rose">Secure entry</span>
              <h2 className="hero-type text-3xl font-bold text-primary-600">Open your workspace</h2>
              <p className="max-w-md text-sm leading-6 text-slate-500">Continue with Google to access your saved resume, preferences, and applications.</p>
            </div>

            <div className="space-y-3">
              <button
                onClick={loginWithGoogle}
                className="flex w-full items-center justify-center gap-3 border border-primary-600 bg-accent-rose px-5 py-4 text-sm font-bold text-white shadow-[4px_4px_0_#1D1C1A] hover:-translate-y-0.5 hover:shadow-[6px_6px_0_#1D1C1A]"
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

            </div>
          </div>
          <p className="mt-12 border-t border-border pt-4 font-mono text-[10px] uppercase leading-5 text-slate-500">Private workspace · Your documents stay tied to your account</p>
        </section>
      </div>
    </div>
  );
};
