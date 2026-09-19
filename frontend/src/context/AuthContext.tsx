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
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const USER_CACHE_KEY = 'voxyl.auth.user';
const SESSION_FLAG_KEY = 'voxyl.auth.has_session';

const clearVoxylCache = () => {
  localStorage.removeItem(USER_CACHE_KEY);
  localStorage.removeItem(SESSION_FLAG_KEY);
  sessionStorage.removeItem(USER_CACHE_KEY);

  const sessionKeys: string[] = [];
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith('voxyl.')) {
      sessionKeys.push(key);
    }
  }
  sessionKeys.forEach((key) => sessionStorage.removeItem(key));
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 1. Immediately read cached user from localStorage (0ms synchronous restore)
  const [user, setUser] = useState<User | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY) || sessionStorage.getItem(USER_CACHE_KEY);
      return cached ? (JSON.parse(cached) as User) : null;
    } catch {
      return null;
    }
  });

  // 2. Only show full loading spinner if user has an active session flag AND user is not yet in cache.
  // New visitors / logged-out users see the Google login page INSTANTLY with 0ms delay.
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    try {
      const hasCachedUser = !!(localStorage.getItem(USER_CACHE_KEY) || sessionStorage.getItem(USER_CACHE_KEY));
      if (hasCachedUser) {
        return false;
      }
      const hasSession = localStorage.getItem(SESSION_FLAG_KEY) === 'true';
      return hasSession;
    } catch {
      return false;
    }
  });

  const checkAuth = async () => {
    try {
      const currentUser = await authApi.getMe();
      setUser(currentUser);
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(currentUser));
      localStorage.setItem(SESSION_FLAG_KEY, 'true');
      sessionStorage.setItem(USER_CACHE_KEY, JSON.stringify(currentUser));
    } catch {
      setUser(null);
      clearVoxylCache();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Run silent auth check in background without blocking landing view
    void checkAuth();
  }, []);

  const loginWithGoogle = () => {
    localStorage.setItem(SESSION_FLAG_KEY, 'true');
    window.location.href = authApi.getLoginUrl();
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    } finally {
      setUser(null);
      clearVoxylCache();
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
