import React, { useEffect, useMemo, useState } from 'react';
import { Check, Search } from 'lucide-react';
import { authApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

const AVAILABLE_COUNTRIES = [
  { code: 'REMOTE', name: 'Worldwide / Remote' },
  { code: 'US', name: 'United States' },
  { code: 'CA', name: 'Canada' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'AU', name: 'Australia' },
  { code: 'IN', name: 'India' },
  { code: 'PK', name: 'Pakistan' },
  { code: 'SG', name: 'Singapore' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'AE', name: 'United Arab Emirates' },
  { code: 'SA', name: 'Saudi Arabia' },
  { code: 'IE', name: 'Ireland' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'JP', name: 'Japan' },
];

interface ProfileSetupProps {
  mode?: 'onboarding' | 'profile';
}

export const ProfileSetup: React.FC<ProfileSetupProps> = ({ mode = 'onboarding' }) => {
  const { user, setUser } = useAuth();
  const initialRoles = useMemo(() => {
    const roles = user?.preferred_roles ?? [];
    return roles.length > 0 ? roles.slice(0, 1) : [''];
  }, [user?.preferred_roles]);

  const [preferredName, setPreferredName] = useState(user?.preferred_name || user?.name || '');
  const [roles, setRoles] = useState<string[]>(initialRoles);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(
    user?.preferred_countries?.length ? user.preferred_countries.slice(0, 3) : ['REMOTE', 'US']
  );
  const [countryQuery, setCountryQuery] = useState('');
  const [sendMode, setSendMode] = useState<'manual' | 'auto'>(user?.send_mode || 'manual');
  const [githubUrl, setGithubUrl] = useState(user?.github_url || '');
  const [portfolioUrl, setPortfolioUrl] = useState(user?.portfolio_url || '');
  const [linkedinUrl, setLinkedinUrl] = useState(user?.linkedin_url || '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPreferredName(user?.preferred_name || user?.name || '');
    const nextRoles = user?.preferred_roles ?? [];
    setRoles(nextRoles.length > 0 ? nextRoles.slice(0, 1) : ['']);
    setSelectedCountries(user?.preferred_countries?.length ? user.preferred_countries.slice(0, 3) : ['REMOTE', 'US']);
    setCountryQuery('');
    setSendMode(user?.send_mode || 'manual');
    setGithubUrl(user?.github_url || '');
    setPortfolioUrl(user?.portfolio_url || '');
    setLinkedinUrl(user?.linkedin_url || '');
  }, [user]);

  const toggleCountry = (code: string) => {
    setSelectedCountries((current) => {
      if (current.includes(code)) {
        return current.filter((item) => item !== code);
      }

      if (code === 'REMOTE') {
        return ['REMOTE', ...current.filter((item) => item !== 'REMOTE')].slice(0, 3);
      }

      const withoutRemote = current.filter((item) => item !== 'REMOTE');
      return withoutRemote.length >= 3 ? [...withoutRemote.slice(1), code] : [...current, code];
    });
  };

  const updateRole = (value: string) => {
    setRoles((current) => {
      return [value, ...current.slice(1)];
    });
  };

  const saveProfile = async () => {
    setError(null);
    setIsSaving(true);
    const cleanedRoles = roles.map((role) => role.trim()).filter(Boolean).slice(0, 1);
    const cleanedCountries = selectedCountries.slice(0, 3);

    try {
      const updated = await authApi.updateProfile({
        preferred_name: preferredName,
        preferred_roles: cleanedRoles,
        preferred_countries: cleanedCountries,
        send_mode: sendMode,
        github_url: githubUrl,
        portfolio_url: portfolioUrl,
        linkedin_url: linkedinUrl,
      });
      setUser(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not save profile details.');
    } finally {
      setIsSaving(false);
    }
  };

  const canSave = roles.some((role) => role.trim()) && selectedCountries.length > 0;
  const showOptionalLinks = mode === 'profile';
  const filteredCountries = useMemo(() => {
    const term = countryQuery.trim().toLowerCase();
    if (!term) return AVAILABLE_COUNTRIES;
    return AVAILABLE_COUNTRIES.filter(
      (country) => country.name.toLowerCase().includes(term) || country.code.toLowerCase().includes(term)
    );
  }, [countryQuery]);
  const previewCountries = selectedCountries.slice(0, 3);

  return (
    <main className="flex-1 px-4 py-8 sm:py-10">
      <section className="panel-air mx-auto w-full max-w-2xl rounded-[34px] p-6 sm:p-8">
        <div className="space-y-6">
          <div className="space-y-2">
            <h1 className="hero-type text-3xl font-semibold text-primary-600 sm:text-4xl">Profile details</h1>
            <p className="max-w-xl text-sm leading-7 text-slate-500">
              Save the details you want Voxyl to remember, then update them anytime from this page.
            </p>
          </div>

          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
              Preferred name
            </span>
            <input
              value={preferredName}
              onChange={(event) => setPreferredName(event.target.value)}
              placeholder={user?.name || 'Your name'}
              className="w-full rounded-full border border-border bg-white/90 px-5 py-3 text-sm text-primary-600 outline-none transition focus:border-primary-400"
            />
          </label>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                Automation mode
              </span>
              <span className="text-[11px] text-slate-400">Choose now, change later in Profile</span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setSendMode('manual')}
                className={`rounded-[24px] border px-4 py-3 text-left transition ${
                  sendMode === 'manual'
                    ? 'border-primary-200 bg-white text-primary-600'
                    : 'border-border bg-white/80 text-slate-600 hover:border-primary-200'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">Manual</span>
                  {sendMode === 'manual' && <Check className="h-4 w-4 text-emerald-500" />}
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  You discover jobs and tailor them yourself when needed.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setSendMode('auto')}
                className={`rounded-[24px] border px-4 py-3 text-left transition ${
                  sendMode === 'auto'
                    ? 'border-primary-200 bg-white text-primary-600'
                    : 'border-border bg-white/80 text-slate-600 hover:border-primary-200'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">Autonomous</span>
                  {sendMode === 'auto' && <Check className="h-4 w-4 text-emerald-500" />}
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Voxyl scrapes, tailors, and emails you when new jobs are ready.
                </p>
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                Preferred role
              </span>
            </div>

            <div className="space-y-2">
              <input
                value={roles[0] || ''}
                onChange={(event) => updateRole(event.target.value)}
                placeholder="AI Engineer"
                className="w-full rounded-full border border-border bg-white/90 px-5 py-3 text-sm text-primary-600 outline-none transition focus:border-primary-400"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                Preferred countries
              </span>
              <span className="text-[11px] text-slate-400">Selected at startup</span>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1 soft-scrollbar">
              {previewCountries.map((country) => (
                <span
                  key={country}
                  className="inline-flex min-w-fit items-center gap-2 rounded-full border border-border bg-white/90 px-4 py-2 text-xs text-slate-600"
                >
                  <span>{AVAILABLE_COUNTRIES.find((item) => item.code === country)?.name || country}</span>
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                </span>
              ))}
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={countryQuery}
                onChange={(event) => setCountryQuery(event.target.value)}
                placeholder="Search countries"
                className="w-full rounded-full border border-border bg-white/90 py-3 pl-9 pr-4 text-sm text-primary-600 outline-none transition focus:border-primary-400"
              />
            </div>
            <div className="max-h-52 space-y-2 overflow-y-auto rounded-[28px] border border-border bg-white/70 p-3 soft-scrollbar">
              {filteredCountries.map((country) => {
                const isSelected = selectedCountries.includes(country.code);
                return (
                  <button
                    key={country.code}
                    type="button"
                    onClick={() => toggleCountry(country.code)}
                    className={`flex w-full items-center justify-between rounded-full border px-3 py-2.5 text-left text-sm transition ${
                      isSelected
                        ? 'border-primary-200 bg-white text-primary-600'
                        : 'border-transparent bg-transparent text-slate-600 hover:border-border hover:bg-white/90'
                    }`}
                  >
                    <span>{country.name}</span>
                    {isSelected ? <Check className="h-4 w-4 text-emerald-500" /> : <span className="h-4 w-4" />}
                  </button>
                );
              })}
            </div>
          </div>

          {showOptionalLinks && (
            <div className="space-y-3 border-t border-border pt-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    GitHub
                  </span>
                  <input
                    value={githubUrl}
                    onChange={(event) => setGithubUrl(event.target.value)}
                    placeholder="https://github.com/username"
                    className="w-full rounded-full border border-border bg-white/90 px-4 py-3 text-sm text-primary-600 outline-none transition focus:border-primary-400"
                  />
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    Portfolio
                  </span>
                  <input
                    value={portfolioUrl}
                    onChange={(event) => setPortfolioUrl(event.target.value)}
                    placeholder="https://your-portfolio.com"
                    className="w-full rounded-full border border-border bg-white/90 px-4 py-3 text-sm text-primary-600 outline-none transition focus:border-primary-400"
                  />
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    LinkedIn
                  </span>
                  <input
                    value={linkedinUrl}
                    onChange={(event) => setLinkedinUrl(event.target.value)}
                    placeholder="https://linkedin.com/in/username"
                    className="w-full rounded-full border border-border bg-white/90 px-4 py-3 text-sm text-primary-600 outline-none transition focus:border-primary-400"
                  />
                </label>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-700">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={saveProfile}
              disabled={isSaving || !canSave}
              className="inline-flex items-center justify-center rounded-full bg-primary-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#20352e] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : mode === 'onboarding' ? 'Save and continue' : 'Save changes'}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
};
