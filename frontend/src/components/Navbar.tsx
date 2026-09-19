import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ChevronDown, LogOut, Settings, User, LayoutGrid, BriefcaseBusiness, Files } from 'lucide-react';

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

  const navItems: Array<['dashboard' | 'jobs' | 'applications', string, React.ComponentType<{ className?: string }>]> = [
    ['dashboard', 'Dashboard', LayoutGrid],
    ['jobs', 'Jobs', BriefcaseBusiness],
    ['applications', 'Applications', Files],
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-primary-600 bg-surface/95 px-3 backdrop-blur-md sm:px-6">
      <div className="site-shell flex min-h-[72px] flex-col justify-center gap-2 overflow-visible py-2">
        <div className="flex w-full items-center justify-between gap-2">
          {/* Logo */}
          <button
            type="button"
            onClick={() => (user ? setActiveTab('dashboard') : undefined)}
            className="flex min-w-0 items-center gap-3 shrink-0"
            aria-label="Voxyl home"
          >
            <img src="/voxyl-mark.png" alt="Voxyl" className="h-7 w-auto" />
            <span className="hero-type truncate text-base font-bold uppercase text-primary-600 sm:text-lg">
              Voxyl
            </span>
            <span className="hidden border-l border-border pl-3 font-mono text-[10px] uppercase text-slate-500 sm:block">Career OS / 01</span>
          </button>

          {/* Desktop Navigation */}
          {user ? (
            <nav className="hidden md:flex items-center gap-0 border border-primary-600 bg-background">
              {navItems.map(([tab, label, Icon]) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex min-h-10 items-center gap-2 border-r border-primary-600 px-4 text-xs font-semibold last:border-r-0 ${
                    activeTab === tab
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-500 hover:bg-surface hover:text-primary-600'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
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
                className="flex items-center gap-2 border border-primary-600 bg-surface px-2 py-1.5 text-slate-600 hover:bg-background hover:text-primary-600"
                title="Account menu"
              >
                <span className="flex h-7 w-7 items-center justify-center bg-accent-rose text-white sm:h-8 sm:w-8">
                  <User className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                </span>
                <span className="hidden sm:block text-xs sm:text-sm font-medium text-slate-600 max-w-[120px] truncate">
                  {user.preferred_name || user.name}
                </span>
                <ChevronDown className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-400" />
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-full mt-2 w-56 overflow-hidden border border-primary-600 bg-surface shadow-[5px_5px_0_rgba(29,28,26,0.14)] z-50">
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
              className="border border-primary-600 bg-accent-rose px-5 py-2.5 text-xs font-bold uppercase text-white shadow-[3px_3px_0_#1D1C1A] hover:-translate-y-0.5 hover:shadow-[4px_4px_0_#1D1C1A]"
            >
              Login
            </button>
          )}
        </div>

        {/* Mobile Navigation Tabs Bar */}
        {user ? (
          <nav className="grid w-full grid-cols-3 border border-primary-600 md:hidden">
            {navItems.map(([tab, label]) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`border-r border-primary-600 py-2 text-center text-[11px] font-semibold last:border-r-0 ${
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
