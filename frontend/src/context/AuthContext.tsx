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
const AUTH_TOKEN_KEY = 'voxyl.auth.token';

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

const bootstrapAuthTokenFromUrl = () => {
  if (typeof window === 'undefined') {
    return;
  }

  const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
  if (!hash) {
    return;
  }

  const params = new URLSearchParams(hash);
  const authToken = params.get('auth_token');
  if (!authToken) {
    return;
  }

  sessionStorage.setItem(AUTH_TOKEN_KEY, authToken);
  window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.search}`);
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkAuth = async () => {
    bootstrapAuthTokenFromUrl();

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
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
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
