import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User } from '../types/api';
import { authApi } from '../services/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginWithGoogle: () => void;
  logout: () => Promise<void>;
  setUser: React.Dispatch<React.SetStateAction<User | null>>;
  devMockLogin: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const USER_CACHE_KEY = 'voxyl.auth.user';

const clearVoxylSessionCache = () => {
  const keysToRemove: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith('voxyl.')) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((key) => sessionStorage.removeItem(key));
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkAuth = async () => {
    const cachedUser = sessionStorage.getItem(USER_CACHE_KEY);
    if (cachedUser) {
      try {
        const parsedUser = JSON.parse(cachedUser) as User;
        setUser(parsedUser);
        setIsLoading(false);

        void authApi
          .getMe()
          .then((currentUser) => {
            setUser(currentUser);
            sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(currentUser));
          })
          .catch(() => {
            setUser(null);
            sessionStorage.removeItem(USER_CACHE_KEY);
            clearVoxylSessionCache();
          });

        return;
      } catch {
        sessionStorage.removeItem(USER_CACHE_KEY);
      }
    }

    try {
      const currentUser = await authApi.getMe();
      setUser(currentUser);
      sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(currentUser));
    } catch {
      setUser(null);
      sessionStorage.removeItem(USER_CACHE_KEY);
      clearVoxylSessionCache();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const loginWithGoogle = () => {
    window.location.href = authApi.getLoginUrl();
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    } finally {
      setUser(null);
      clearVoxylSessionCache();
    }
  };

  const devMockLogin = async () => {
    try {
      setIsLoading(true);
      const devUser = await authApi.devLogin();
      setUser(devUser);
      sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(devUser));
    } catch {
      // Fallback
      const fallbackUser: User = {
        id: 1,
        email: "dev@autopilot.ai",
        name: "Developer Candidate",
        preferred_name: "Developer Candidate",
        preferred_roles: ["AI Engineer"],
        preferred_countries: ["US"],
        github_url: null,
        portfolio_url: null,
        linkedin_url: null,
        profile_completed: false,
        send_mode: "manual",
        has_google_token: true,
      };
      setUser(fallbackUser);
      sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(fallbackUser));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        loginWithGoogle,
        logout,
        setUser,
        devMockLogin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
