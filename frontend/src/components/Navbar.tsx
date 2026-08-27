import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ChevronDown, LogOut, Settings, User } from 'lucide-react';

interface NavbarProps {
  activeTab: 'dashboard' | 'jobs' | 'applications' | 'profile';
  setActiveTab: (tab: 'dashboard' | 'jobs' | 'applications' | 'profile') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const { user, logout, loginWithGoogle } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="sticky top-4 z-40 w-full px-4 sm:px-6">
      <div className="site-shell grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-full bg-white/80 px-3 py-2 shadow-[0_10px_26px_rgba(18,32,26,0.04)]">
        <button
          type="button"
          onClick={() => user ? setActiveTab('dashboard') : undefined}
          className="flex items-center gap-3 shrink-0"
          aria-label="Voxyl home"
        >
          <img src="/voxyl-mark.png" alt="Voxyl" className="h-8 w-auto" />
          <span className="hidden sm:inline text-lg font-semibold tracking-tight text-primary-600">Voxyl</span>
        </button>

        {user ? (
          <nav className="hidden justify-self-center items-center gap-1 rounded-full bg-white/70 px-2 py-1 md:flex">
            {[
              ['dashboard', 'Dashboard'],
              ['jobs', 'Jobs'],
              ['applications', 'Applications'],
            ].map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as 'dashboard' | 'jobs' | 'applications' | 'profile')}
                className={`rounded-full px-4 py-2 text-xs font-medium transition-colors ${
                  activeTab === tab
                    ? 'bg-primary-600 text-white'
                    : 'text-slate-500 hover:text-primary-600'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        ) : (
          <div />
        )}

        {user ? (
          <div className="relative justify-self-end shrink-0" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((open) => !open)}
              className="flex items-center gap-2 rounded-full bg-white px-2.5 py-2 text-slate-600 transition-colors hover:text-primary-600"
              title="Account menu"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                <User className="h-4 w-4" />
              </span>
              <span className="hidden sm:block text-sm font-medium text-slate-600">
                {user.preferred_name || user.name}
              </span>
              <ChevronDown className="h-4 w-4 text-slate-400" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-3 w-48 overflow-hidden rounded-2xl border border-border bg-white shadow-[0_12px_24px_rgba(18,32,26,0.08)]">
                <button
                  onClick={() => {
                    setActiveTab('profile');
                    setMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm text-slate-600 hover:bg-slate-100 hover:text-primary-600"
                >
                  <Settings className="h-4 w-4" />
                  Profile
                </button>
                <button
                  onClick={async () => {
                    await logout();
                    setMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 border-t border-border px-4 py-3 text-left text-sm text-slate-600 hover:bg-slate-100 hover:text-primary-600"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={loginWithGoogle}
            className="justify-self-end rounded-full bg-accent-rose px-5 py-2.5 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(219,91,75,0.18)] transition hover:translate-y-[-1px] hover:bg-[#e36457]"
          >
            Login
          </button>
        )}
      </div>
    </header>
  );
};
