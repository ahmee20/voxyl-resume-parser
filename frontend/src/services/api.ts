import axios from 'axios';
import type { User, UserProfileUpdate, Resume, Job, ApplicationDetail } from '../types/api';

const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';
const AUTH_TOKEN_KEY = 'voxyl.auth.token';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // required for Starlette session cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const authToken = sessionStorage.getItem(AUTH_TOKEN_KEY);
    if (authToken) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${authToken}`;
    }
  }
  return config;
});

export const authApi = {
  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },
  getLoginUrl: (): string => {
    return `${API_BASE_URL}/auth/google/login`;
  },
  updateProfile: async (payload: UserProfileUpdate): Promise<User> => {
    const response = await apiClient.patch<User>('/auth/profile', payload);
    return response.data;
  },
  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },
};

export const resumeApi = {
  uploadResume: async (file: File, userId?: number): Promise<Resume> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<Resume>('/resumes/upload', formData, {
      params: userId ? { user_id: userId } : undefined,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
  getLatestResume: async (): Promise<Resume | null> => {
    const response = await apiClient.get<Resume | null>('/resumes/latest');
    return response.data;
  },
  getResume: async (id: number): Promise<Resume> => {
    const response = await apiClient.get<Resume>(`/resumes/${id}`);
    return response.data;
  },
};

export const jobsApi = {
  listJobs: async (
    qualified?: boolean,
    limit = 50,
    offset = 0,
    latest?: boolean,
    userId?: number
  ): Promise<Job[]> => {
    const response = await apiClient.get<Job[]>('/jobs', {
      params: {
        ...(qualified !== undefined ? { qualified } : {}),
        ...(latest ? { latest: true } : {}),
        ...(userId ? { user_id: userId } : {}),
        limit,
        offset,
      },
    });
    return response.data;
  },
  discoverJobs: async (
    userId: number,
    options?: { targetRole?: string; preferredRoles?: string[]; countries?: string[]; resumeId?: number; maxResults?: number }
  ): Promise<{
    status: string;
    search_queries: string[];
    preferred_roles?: string[];
    preferred_countries?: string[];
    scraped_count: number;
    relevant_count: number;
    persisted_job_ids: number[];
    jobs?: Job[];
  }> => {
    const payload: Record<string, unknown> = {
      user_id: userId,
      resume_id: options?.resumeId,
      target_role: options?.targetRole,
      preferred_roles: options?.preferredRoles,
      countries: options?.countries,
    };
    if (options?.maxResults !== undefined) {
      payload.max_results = options.maxResults;
    }

    const response = await apiClient.post('/jobs/discover', {
      ...payload,
    });
    return response.data;
  },
  discoverAndApply: async (
    userId: number,
    options?: { targetRole?: string; preferredRoles?: string[]; countries?: string[]; resumeId?: number; maxResults?: number }
  ): Promise<{
    status: string;
    search_queries: string[];
    preferred_roles?: string[];
    preferred_countries?: string[];
    scraped_count: number;
    persisted_job_ids: number[];
    batch_size: number;
    total_batches: number;
    message: string;
  }> => {
    const payload: Record<string, unknown> = {
      user_id: userId,
      resume_id: options?.resumeId,
      target_role: options?.targetRole,
      preferred_roles: options?.preferredRoles,
      countries: options?.countries,
    };
    if (options?.maxResults !== undefined) {
      payload.max_results = options.maxResults;
    }

    const response = await apiClient.post('/jobs/discover-and-apply', {
      ...payload,
    });
    return response.data;
  },
};

export const applicationsApi = {
  runSingleJob: async (jobId: number, resumeId?: number): Promise<{
    application_id: number;
    status: string;
    pdf_url?: string;
    approval_attempts: number;
  }> => {
    const response = await apiClient.post('/applications/run-single', {
      job_id: jobId,
      resume_id: resumeId,
    });
    return response.data;
  },
  runBatch: async (jobIds: number[], resumeId?: number, userId?: number): Promise<{
    status: string;
    job_ids: number[];
    count: number;
    message: string;
  }> => {
    const response = await apiClient.post('/applications/run-batch', {
      job_ids: jobIds,
      resume_id: resumeId,
      user_id: userId,
    });
    return response.data;
  },
  getApplication: async (id: number): Promise<ApplicationDetail> => {
    const response = await apiClient.get<ApplicationDetail>(`/applications/${id}`);
    return response.data;
  },
};
