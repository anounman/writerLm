/// <reference types="vite/client" />
export type ApiKeyProvider = "google" | "groq" | "tavily" | "firecrawl" | "neon";
export type JobStatus = "queued" | "running" | "completed" | "completed_with_latex_issue" | "failed" | "stopped";

export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface ApiKeyRecord {
  id: number;
  provider: ApiKeyProvider;
  key_hint: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineConfig {
  llm_provider: "google" | "groq";
  planner_google_model: string;
  researcher_google_model: string;
  notes_google_model: string;
  writer_google_model: string;
  reviewer_google_model: string;
  planner_groq_model: string;
  researcher_groq_model: string;
  notes_groq_model: string;
  writer_groq_model: string;
  reviewer_groq_model: string;
  parallel_section_pipeline: boolean;
  section_pipeline_concurrency: number;
  compile_latex: boolean;
  strict_latex_compile: boolean;
  latex_engine: "pdflatex" | "xelatex" | "lualatex";
  research_execution_profile: "budget" | "debug" | "full";
  token_budget: number | null;
  max_completion_tokens: number | null;
}

export interface BookRequest {
  topic: string;
  audience: string;
  tone: string;
  book_type:
    | "auto"
    | "textbook"
    | "practice_workbook"
    | "course_companion"
    | "implementation_guide"
    | "reference_handbook"
    | "conceptual_guide"
    | "exam_prep";
  theory_practice_balance: "auto" | "theory_heavy" | "balanced" | "practice_heavy" | "implementation_heavy";
  pedagogy_style: "auto" | "german_theoretical" | "indian_theory_then_examples" | "socratic" | "exam_oriented" | "project_based";
  source_usage: "auto" | "primary_curriculum" | "supplemental" | "example_inspiration";
  exercise_strategy: "auto" | "none" | "extract_patterns" | "worked_examples" | "practice_sets";
  goals: string[];
  project_based: boolean;
  running_project_description: string | null;
  code_density: "high" | "medium" | "low";
  example_density: "high" | "medium" | "low";
  diagram_density: "high" | "medium" | "low";
  max_section_words: number | null;
  force_web_research: boolean;
}

export interface JobStage {
  label: string;
  status: "queued" | "running" | "completed" | "failed" | "stopped";
  started_at: string | null;
  completed_at: string | null;
  seconds: number | null;
  details: Record<string, unknown>;
}

export interface Job {
  id: number;
  status: JobStatus;
  current_stage: string;
  request_payload: Record<string, unknown>;
  config_snapshot: Record<string, unknown>;
  stages: Record<string, JobStage>;
  summary: Record<string, unknown>;
  warnings: Record<string, unknown>;
  error_message: string | null;
  run_dir: string | null;
  process_id: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface GeneratedBook {
  id: number;
  job_id: number;
  title: string;
  topic: string;
  status: string;
  run_dir: string;
  latex_path: string | null;
  pdf_path: string | null;
  summary_metrics: Record<string, unknown>;
  artifact_paths: Record<string, string | null>;
  created_at: string;
}

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export class ApiClient {
  token: string | null;

  constructor(token: string | null) {
    this.token = token;
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set("Content-Type", "application/json");
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(payload.detail || response.statusText);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  signup(email: string, password: string) {
    return this.request<{ access_token: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  }

  login(email: string, password: string) {
    return this.request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  }

  me() {
    return this.request<User>("/me");
  }

  apiKeys() {
    return this.request<ApiKeyRecord[]>("/api-keys");
  }

  saveApiKey(provider: ApiKeyProvider, value: string) {
    return this.request<ApiKeyRecord>(`/api-keys/${provider}`, {
      method: "PUT",
      body: JSON.stringify({ provider, value })
    });
  }

  deleteApiKey(provider: ApiKeyProvider) {
    return this.request<void>(`/api-keys/${provider}`, { method: "DELETE" });
  }

  config() {
    return this.request<PipelineConfig>("/config");
  }

  saveConfig(config: PipelineConfig) {
    return this.request<PipelineConfig>("/config", {
      method: "PUT",
      body: JSON.stringify(config)
    });
  }

  createJob(payload: BookRequest) {
    return this.request<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  /** Create a job and attach PDF source files via multipart upload. */
  createJobWithPdfs(payload: BookRequest, pdfFiles: File[]) {
    const form = new FormData();
    form.append("request_json", JSON.stringify(payload));
    for (const file of pdfFiles) {
      form.append("pdf_files", file, file.name);
    }
    // Use fetch directly — request() forces Content-Type: application/json
    const headers = new Headers();
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    return fetch(`${API_BASE}/jobs/upload`, { method: "POST", headers, body: form })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(payload.detail || response.statusText);
        }
        return response.json() as Promise<Job>;
      });
  }

  jobs() {
    return this.request<Job[]>("/jobs");
  }

  job(id: number) {
    return this.request<Job>(`/jobs/${id}`);
  }

  stopJob(id: number) {
    return this.request<Job>(`/jobs/${id}/stop`, { method: "POST" });
  }

  books() {
    return this.request<GeneratedBook[]>("/books");
  }

  async downloadArtifact(bookId: number, artifactName: string) {
    const headers = new Headers();
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    const response = await fetch(this.artifactUrl(bookId, artifactName), { headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(payload.detail || response.statusText);
    }
    const blob = await response.blob();
    const contentDisposition = response.headers.get("content-disposition") || "";
    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
    return {
      blob,
      filename: filenameMatch?.[1] || `${artifactName}-${bookId}`,
    };
  }

  artifactUrl(bookId: number, artifactName: string) {
    return `${API_BASE}/books/${bookId}/artifacts/${artifactName}`;
  }
}
