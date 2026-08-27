export interface User {
  id: number;
  email: string;
  name: string;
  preferred_name?: string | null;
  preferred_roles?: string[];
  preferred_countries?: string[];
  github_url?: string | null;
  portfolio_url?: string | null;
  linkedin_url?: string | null;
  profile_completed: boolean;
  send_mode: "manual" | "auto";
  has_google_token: boolean;
}

export interface UserProfileUpdate {
  preferred_name?: string;
  preferred_roles?: string[];
  preferred_countries?: string[];
  send_mode?: "manual" | "auto";
  github_url?: string;
  portfolio_url?: string;
  linkedin_url?: string;
}

export interface Resume {
  id: number;
  user_id: number;
  version: number;
  filename?: string | null;
  source_text: string;
  source_html: string;
  is_base: boolean;
  created_at?: string;
}

export interface JobApplicationSummary {
  id: number;
  status: string;
  applied_status: "no" | "yes" | "manual";
  pdf_url?: string | null;
  email_draft?: string | null;
  tailored_html?: string | null;
  ats_score?: number | null;
  gap_analysis?: string | null;
  approval_attempts?: number;
}

export interface Job {
  id: number;
  title: string;
  company: string;
  url: string;
  description: string;
  recruiter_email?: string | null;
  source: string;
  is_qualified?: boolean;
  match_score?: number | null;
  filter_reason?: string | null;
  apollo_enrichment?: {
    domain?: string;
    industry?: string;
    estimated_num_employees?: number | string;
    company_size?: string;
    location?: string;
    recruiter_name?: string;
    recruiter_title?: string;
    city?: string;
    country?: string;
    verified?: boolean;
  };
  application?: JobApplicationSummary | null;
}

export interface ApplicationTimelineItem {
  id: number;
  node_name: string;
  status: "running" | "success" | "failure";
  latency_ms: number;
  created_at: string;
  error_message?: string | null;
  state_snapshot?: {
    gap_analysis?: {
      missing_skills?: string[];
      matching_skills?: string[];
      match_score?: number;
    };
    ats_review?: {
      pass: boolean;
      score: number;
      feedback: string;
    };
    factual_review?: {
      pass: boolean;
      hallucinated_facts?: string[];
    };
    delivery_status?: string;
    gmail_message_id?: string;
    drive_folder_url?: string;
    draft_email?: {
      subject: string;
      body: string;
    };
  };
}

export interface ApplicationDetail {
  id: number;
  user_id: number;
  job_id: number;
  resume_id?: number | null;
  job_title?: string | null;
  job_company?: string | null;
  job_url?: string | null;
  job_description?: string | null;
  job_recruiter_email?: string | null;
  job_apollo_enrichment?: {
    domain?: string;
    industry?: string;
    estimated_num_employees?: number | string;
    company_size?: string;
    location?: string;
    recruiter_name?: string;
    recruiter_title?: string;
    city?: string;
    country?: string;
    verified?: boolean;
  } | null;
  applied_status: "no" | "yes" | "manual";
  mode: "manual" | "auto";
  status: string;
  tailored_html?: string | null;
  rendered_pdf_url?: string | null;
  ats_score?: number | null;
  gap_analysis?: string | null;
  email_draft?: string | null;
  approval_attempts: number;
  created_at?: string;
  updated_at?: string;
  timeline: ApplicationTimelineItem[];
}
