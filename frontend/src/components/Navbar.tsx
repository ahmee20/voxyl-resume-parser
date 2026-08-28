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

  const navItems: Array<['dashboard' | 'jobs' | 'applications', string]> = [
    ['dashboard', 'Dashboard'],
    ['jobs', 'Jobs'],
    ['applications', 'Applications'],
  ];

  return (
    <header className="sticky top-0 sm:top-4 z-40 w-full px-2 pt-2 sm:px-6 sm:pt-0">
      <div className="site-shell flex flex-col gap-2 overflow-visible rounded-[24px] sm:rounded-full bg-white/88 p-2 shadow-[0_10px_26px_rgba(18,32,26,0.04)] backdrop-blur-xl border border-white/60">
        <div className="flex w-full items-center justify-between gap-2">
          {/* Logo */}
          <button
            type="button"
            onClick={() => (user ? setActiveTab('dashboard') : undefined)}
            className="flex min-w-0 items-center gap-2 sm:gap-3 shrink-0"
            aria-label="Voxyl home"
          >
            <img src="/voxyl-mark.png" alt="Voxyl" className="h-7 w-auto sm:h-8" />
            <span className="truncate text-sm font-semibold tracking-tight text-primary-600 sm:text-lg">
              Voxyl
            </span>
          </button>

          {/* Desktop Navigation */}
          {user ? (
            <nav className="hidden md:flex items-center gap-1 rounded-full bg-white/70 px-2 py-1">
              {navItems.map(([tab, label]) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`rounded-full px-4 py-2 text-xs font-medium transition-colors ${
                    activeTab === tab
                      ? 'bg-primary-600 text-white shadow-sm'
                      : 'text-slate-500 hover:text-primary-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>
          ) : null}

          {/* Account Menu / Login */}
          {user ? (
            <div className="relative shrink-0" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-expanded={menuOpen}
                className="flex items-center gap-1.5 rounded-full border border-border/50 bg-white/90 px-2 py-1.5 text-slate-600 transition-colors hover:text-primary-600 sm:gap-2 sm:px-2.5 sm:py-2"
                title="Account menu"
              >
                <span className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                  <User className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                </span>
                <span className="hidden sm:block text-xs sm:text-sm font-medium text-slate-600 max-w-[120px] truncate">
                  {user.preferred_name || user.name}
                </span>
                <ChevronDown className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-400" />
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-full mt-2 w-48 overflow-hidden rounded-2xl border border-border bg-white shadow-[0_12px_24px_rgba(18,32,26,0.08)] z-50">
                  <div className="px-4 py-2.5 border-b border-border text-xs text-slate-500 truncate">
                    {user.email}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab('profile');
                      setMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm text-slate-600 hover:bg-slate-50 hover:text-primary-600"
                  >
                    <Settings className="h-4 w-4 text-slate-400" />
                    Profile &amp; Settings
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await logout();
                      setMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 border-t border-border px-4 py-3 text-left text-sm text-rose-600 hover:bg-rose-50"
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
              className="rounded-full bg-accent-rose px-4 py-2 sm:px-5 sm:py-2.5 text-xs sm:text-sm font-semibold text-white shadow-[0_12px_30px_rgba(219,91,75,0.18)] transition hover:translate-y-[-1px] hover:bg-[#e36457]"
            >
              Login
            </button>
          )}
        </div>

        {/* Mobile Navigation Tabs Bar */}
        {user ? (
          <nav className="grid w-full grid-cols-3 gap-1 border-t border-slate-100 pt-2 md:hidden">
            {navItems.map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`rounded-full py-2 text-[11px] font-medium transition-colors text-center ${
                  activeTab === tab
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-500 hover:text-primary-600 bg-white/50'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        ) : null}
      </div>
    </header>
  );
};
