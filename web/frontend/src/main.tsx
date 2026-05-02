import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  BookOpen,
  Box,
  Check,
  ChevronRight,
  Download,
  FileCode2,
  KeyRound,
  Library,
  LogOut,
  PanelsTopLeft,
  Play,
  RefreshCw,
  Save,
  Settings,
  Sparkles,
  Terminal,
  Timer,
  Trash2,
  UserRound
} from "lucide-react";
import {
  ApiClient,
  ApiKeyProvider,
  ApiKeyRecord,
  BookRequest,
  GeneratedBook,
  Job,
  PipelineConfig
} from "./api";
import "./styles.css";

type Tab = "create" | "progress" | "books" | "keys" | "config";

const tabs: Array<{ id: Tab; label: string; icon: React.ComponentType<{ size?: number }> }> = [
  { id: "create", label: "Create", icon: Sparkles },
  { id: "progress", label: "Progress", icon: PanelsTopLeft },
  { id: "books", label: "Books", icon: Library },
  { id: "keys", label: "Keys", icon: KeyRound },
  { id: "config", label: "Config", icon: Settings }
];

const defaultBookRequest: BookRequest = {
  topic: "Build a retrieval-augmented generation system for answering questions over your own documents",
  audience: "Beginner to intermediate developers who understand basic Python but are new to RAG systems",
  tone: "Practical step by step guide",
  goals: [
    "teach the reader how RAG works by building one from scratch",
    "help the reader implement each core component with code",
    "end with a working mini project the reader can extend"
  ],
  project_based: true,
  running_project_description: "Build a local RAG assistant over personal documents",
  code_density: "high",
  example_density: "high",
  diagram_density: "medium",
  max_section_words: 900
};

const stageOrder = ["planner_research", "notes_synthesis", "writer", "reviewer", "assembler", "latex_compile"];

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("writerlm_token"));
  const api = useMemo(() => new ApiClient(token), [token]);
  const [userEmail, setUserEmail] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("create");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [books, setBooks] = useState<GeneratedBook[]>([]);
  const [notice, setNotice] = useState<string>("");

  const refresh = useCallback(async () => {
    if (!token) return;
    const [me, nextJobs, nextBooks] = await Promise.all([api.me(), api.jobs(), api.books()]);
    setUserEmail(me.email);
    setJobs(nextJobs);
    setBooks(nextBooks);
    if (!selectedJobId && nextJobs[0]) setSelectedJobId(nextJobs[0].id);
  }, [api, selectedJobId, token]);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  useEffect(() => {
    if (!token) return;
    const interval = window.setInterval(() => refresh().catch(() => undefined), 3500);
    return () => window.clearInterval(interval);
  }, [refresh, token]);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) || jobs[0] || null;

  if (!token) {
    return (
      <AuthScreen
        api={api}
        onToken={(nextToken) => {
          localStorage.setItem("writerlm_token", nextToken);
          setToken(nextToken);
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><BookOpen size={21} /></div>
          <div>
            <strong>WriterLM Studio</strong>
            <span>AI book production</span>
          </div>
        </div>

        <nav className="nav-list">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} className={activeTab === tab.id ? "nav-item active" : "nav-item"} onClick={() => setActiveTab(tab.id)}>
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="user-strip">
          <UserRound size={18} />
          <span>{userEmail || "Signed in"}</span>
          <button
            className="icon-button"
            title="Log out"
            onClick={() => {
              localStorage.removeItem("writerlm_token");
              setToken(null);
            }}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Pipeline Control</span>
            <h1>{tabs.find((tab) => tab.id === activeTab)?.label}</h1>
          </div>
          <button className="secondary-button" onClick={() => refresh().catch((error) => setNotice(error.message))}>
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

        {notice && <div className="notice">{notice}</div>}

        <AnimatePresence mode="wait">
          <motion.section
            key={activeTab}
            className="page-surface"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            style={{ willChange: "opacity, transform" }}
          >
            {activeTab === "create" && (
              <CreateBook api={api} onCreated={(job) => {
                setJobs((current) => [job, ...current]);
                setSelectedJobId(job.id);
                setActiveTab("progress");
              }} onNotice={setNotice} />
            )}
            {activeTab === "progress" && <ProgressPage jobs={jobs} selectedJob={selectedJob} onSelect={setSelectedJobId} />}
            {activeTab === "books" && <BooksPage api={api} books={books} />}
            {activeTab === "keys" && <KeysPage api={api} onNotice={setNotice} />}
            {activeTab === "config" && <ConfigPage api={api} onNotice={setNotice} />}
          </motion.section>
        </AnimatePresence>
      </main>
    </div>
  );
}

function AuthScreen({ api, onToken }: { api: ApiClient; onToken: (token: string) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = mode === "login" ? await api.login(email, password) : await api.signup(email, password);
      onToken(result.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    }
  }

  return (
    <div className="auth-screen">
      <motion.form
        className="auth-panel"
        onSubmit={submit}
        initial={{ opacity: 0, scale: 0.97, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 24 }}
      >
        <div className="auth-symbol"><Sparkles size={26} /></div>
        <h1>WriterLM Studio</h1>
        <p>Run the full AI book pipeline from one browser workspace.</p>
        <label>Email<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required /></label>
        <label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" minLength={8} required /></label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button" type="submit">
          <ChevronRight size={18} />
          {mode === "login" ? "Log in" : "Create account"}
        </button>
        <button className="text-button" type="button" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? "Create a new account" : "Use an existing account"}
        </button>
      </motion.form>
    </div>
  );
}

function CreateBook({ api, onCreated, onNotice }: { api: ApiClient; onCreated: (job: Job) => void; onNotice: (message: string) => void }) {
  const [request, setRequest] = useState<BookRequest>(defaultBookRequest);
  const [goalText, setGoalText] = useState(defaultBookRequest.goals.join("\n"));
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const job = await api.createJob({ ...request, goals: goalText.split("\n").map((item) => item.trim()).filter(Boolean) });
      onCreated(job);
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Could not start job.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="studio-grid" onSubmit={submit}>
      <section className="control-panel wide">
        <PanelTitle icon={Sparkles} title="Book Request" meta="Generation brief" />
        <div className="form-grid">
          <label className="span-2">Topic<textarea value={request.topic} onChange={(e) => setRequest({ ...request, topic: e.target.value })} rows={3} /></label>
          <label>Audience<input value={request.audience} onChange={(e) => setRequest({ ...request, audience: e.target.value })} /></label>
          <label>Tone<input value={request.tone} onChange={(e) => setRequest({ ...request, tone: e.target.value })} /></label>
          <label className="span-2">Goals<textarea value={goalText} onChange={(e) => setGoalText(e.target.value)} rows={5} /></label>
          <label className="span-2">Running project<input value={request.running_project_description || ""} onChange={(e) => setRequest({ ...request, running_project_description: e.target.value || null })} /></label>
        </div>
      </section>

      <section className="control-panel">
        <PanelTitle icon={Box} title="Density" meta="Content targets" />
        <Segmented label="Code" value={request.code_density} options={["high", "medium", "low"]} onChange={(value) => setRequest({ ...request, code_density: value })} />
        <Segmented label="Examples" value={request.example_density} options={["high", "medium", "low"]} onChange={(value) => setRequest({ ...request, example_density: value })} />
        <Segmented label="Diagrams" value={request.diagram_density} options={["high", "medium", "low"]} onChange={(value) => setRequest({ ...request, diagram_density: value })} />
      </section>

      <section className="control-panel">
        <PanelTitle icon={Settings} title="Shape" meta="Planner constraints" />
        <label className="toggle-row"><span>Project-based</span><input type="checkbox" checked={request.project_based} onChange={(e) => setRequest({ ...request, project_based: e.target.checked })} /></label>
        <label>Max section words<input type="number" min={150} max={2000} value={request.max_section_words || ""} onChange={(e) => setRequest({ ...request, max_section_words: e.target.value ? Number(e.target.value) : null })} /></label>
        <button className="primary-button full" disabled={submitting}>
          <Play size={18} />
          {submitting ? "Starting" : "Start generation"}
        </button>
      </section>
    </form>
  );
}

function ProgressPage({ jobs, selectedJob, onSelect }: { jobs: Job[]; selectedJob: Job | null; onSelect: (id: number) => void }) {
  const shouldReduceMotion = useReducedMotion();
  return (
    <div className="progress-layout">
      <section className="job-list">
        {jobs.map((job) => (
          <button key={job.id} className={selectedJob?.id === job.id ? "job-row active" : "job-row"} onClick={() => onSelect(job.id)}>
            <span>Job #{job.id}</span>
            <small>{String(job.request_payload.topic || "Untitled")}</small>
            <StatusPill status={job.status} />
          </button>
        ))}
        {!jobs.length && <EmptyState title="No jobs yet" text="Start a book request to see the pipeline timeline." />}
      </section>

      <section className="timeline-panel">
        {selectedJob ? (
          <>
            <div className="job-hero">
              <div>
                <span className="eyebrow">Current job</span>
                <h2>{String(selectedJob.request_payload.topic || `Job #${selectedJob.id}`)}</h2>
              </div>
              <StatusPill status={selectedJob.status} />
            </div>
            <div className="stage-stack">
              {stageOrder.map((stageKey, index) => {
                const stage = selectedJob.stages?.[stageKey];
                if (!stage) return null;
                return (
                  <motion.div
                    key={stageKey}
                    className={`stage-row ${stage.status}`}
                    initial={{ opacity: 0, x: shouldReduceMotion ? 0 : -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 28, delay: shouldReduceMotion ? 0 : index * 0.035 }}
                  >
                    <div className="stage-icon">{stageIcon(stage.status)}</div>
                    <div>
                      <strong>{stage.label}</strong>
                      <span>{stage.seconds ? `${stage.seconds}s` : stage.status}</span>
                    </div>
                    <pre>{formatDetails(stage.details)}</pre>
                  </motion.div>
                );
              })}
            </div>
            <Metrics job={selectedJob} />
          </>
        ) : (
          <EmptyState title="No selected job" text="Choose a job to inspect progress." />
        )}
      </section>
    </div>
  );
}

function BooksPage({ api, books }: { api: ApiClient; books: GeneratedBook[] }) {
  return (
    <div className="book-grid">
      {books.map((book) => (
        <motion.article key={book.id} className="book-card" whileHover={{ y: -3 }} transition={{ type: "spring", stiffness: 360, damping: 24 }}>
          <div className="book-icon"><BookOpen size={22} /></div>
          <h3>{book.title}</h3>
          <p>{book.topic}</p>
          <div className="book-meta">
            <StatusPill status={book.status} />
            <span>{new Date(book.created_at).toLocaleString()}</span>
          </div>
          <div className="artifact-actions">
            {book.pdf_path && <a className="secondary-button" href={api.artifactUrl(book.id, "pdf")}><Download size={16} />PDF</a>}
            {book.latex_path && <a className="secondary-button" href={api.artifactUrl(book.id, "latex")}><FileCode2 size={16} />LaTeX</a>}
          </div>
        </motion.article>
      ))}
      {!books.length && <EmptyState title="No generated books" text="Completed jobs will appear here with downloadable artifacts." />}
    </div>
  );
}

function KeysPage({ api, onNotice }: { api: ApiClient; onNotice: (message: string) => void }) {
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [values, setValues] = useState<Record<ApiKeyProvider, string>>({ google: "", groq: "", tavily: "", firecrawl: "" });

  const refresh = useCallback(() => api.apiKeys().then(setKeys).catch((error) => onNotice(error.message)), [api, onNotice]);
  useEffect(() => { refresh(); }, [refresh]);

  async function save(provider: ApiKeyProvider) {
    if (!values[provider]) return;
    await api.saveApiKey(provider, values[provider]);
    setValues({ ...values, [provider]: "" });
    refresh();
  }

  async function remove(provider: ApiKeyProvider) {
    await api.deleteApiKey(provider);
    refresh();
  }

  const labels: Record<ApiKeyProvider, string> = { google: "Google / Gemini", groq: "Groq", tavily: "Tavily", firecrawl: "Firecrawl" };
  return (
    <div className="key-grid">
      {(Object.keys(labels) as ApiKeyProvider[]).map((provider) => {
        const existing = keys.find((item) => item.provider === provider);
        return (
          <section className="control-panel" key={provider}>
            <PanelTitle icon={KeyRound} title={labels[provider]} meta={existing ? existing.key_hint : "Not saved"} />
            <input type="password" value={values[provider]} placeholder="Paste API key" onChange={(e) => setValues({ ...values, [provider]: e.target.value })} />
            <div className="button-row">
              <button className="primary-button" onClick={() => save(provider)}><Save size={16} />Save</button>
              <button className="danger-button" onClick={() => remove(provider)}><Trash2 size={16} />Remove</button>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function ConfigPage({ api, onNotice }: { api: ApiClient; onNotice: (message: string) => void }) {
  const [config, setConfig] = useState<PipelineConfig | null>(null);
  useEffect(() => { api.config().then(setConfig).catch((error) => onNotice(error.message)); }, [api, onNotice]);
  if (!config) return <EmptyState title="Loading config" text="Fetching your pipeline controls." />;

  function update<K extends keyof PipelineConfig>(key: K, value: PipelineConfig[K]) {
    setConfig({ ...config, [key]: value });
  }

  return (
    <div className="config-layout">
      <section className="control-panel">
        <PanelTitle icon={Settings} title="Provider" meta="Model routing" />
        <Segmented label="LLM" value={config.llm_provider} options={["google", "groq"]} onChange={(value) => update("llm_provider", value)} />
        <label>Research profile<select value={config.research_execution_profile} onChange={(e) => update("research_execution_profile", e.target.value as PipelineConfig["research_execution_profile"])}><option>budget</option><option>debug</option><option>full</option></select></label>
      </section>
      <section className="control-panel wide">
        <PanelTitle icon={Terminal} title="Models" meta="Per-layer defaults" />
        <div className="model-grid">
          {(["planner", "researcher", "notes", "writer", "reviewer"] as const).map((layer) => (
            <React.Fragment key={layer}>
              <label>{layer} Google<input value={String(config[`${layer}_google_model` as keyof PipelineConfig] || "")} onChange={(e) => update(`${layer}_google_model` as keyof PipelineConfig, e.target.value as never)} /></label>
              <label>{layer} Groq<input value={String(config[`${layer}_groq_model` as keyof PipelineConfig] || "")} onChange={(e) => update(`${layer}_groq_model` as keyof PipelineConfig, e.target.value as never)} /></label>
            </React.Fragment>
          ))}
        </div>
      </section>
      <section className="control-panel">
        <PanelTitle icon={Timer} title="Runtime" meta="Execution controls" />
        <label className="toggle-row"><span>Parallel sections</span><input type="checkbox" checked={config.parallel_section_pipeline} onChange={(e) => update("parallel_section_pipeline", e.target.checked)} /></label>
        <label>Concurrency<input type="number" min={1} max={12} value={config.section_pipeline_concurrency} onChange={(e) => update("section_pipeline_concurrency", Number(e.target.value))} /></label>
        <label className="toggle-row"><span>Compile LaTeX</span><input type="checkbox" checked={config.compile_latex} onChange={(e) => update("compile_latex", e.target.checked)} /></label>
        <label className="toggle-row"><span>Strict compile</span><input type="checkbox" checked={config.strict_latex_compile} onChange={(e) => update("strict_latex_compile", e.target.checked)} /></label>
        <label>LaTeX engine<select value={config.latex_engine} onChange={(e) => update("latex_engine", e.target.value as PipelineConfig["latex_engine"])}><option>pdflatex</option><option>xelatex</option><option>lualatex</option></select></label>
        <button className="primary-button full" onClick={() => api.saveConfig(config).then(setConfig).then(() => onNotice("Configuration saved."))}><Save size={17} />Save config</button>
      </section>
    </div>
  );
}

function PanelTitle({ icon: Icon, title, meta }: { icon: React.ComponentType<{ size?: number }>; title: string; meta: string }) {
  return <div className="panel-title"><Icon size={19} /><div><strong>{title}</strong><span>{meta}</span></div></div>;
}

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: T[]; onChange: (value: T) => void }) {
  return (
    <div className="segmented-field">
      <span>{label}</span>
      <div className="segmented">
        {options.map((option) => <button type="button" key={option} className={value === option ? "selected" : ""} onClick={() => onChange(option)}>{option}</button>)}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${status}`}>{status.replaceAll("_", " ")}</span>;
}

function stageIcon(status: string) {
  if (status === "completed") return <Check size={17} />;
  if (status === "running") return <RefreshCw size={17} className="spin" />;
  if (status === "failed") return <Trash2 size={17} />;
  return <Timer size={17} />;
}

function formatDetails(details: Record<string, unknown>) {
  const entries = Object.entries(details || {}).filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!entries.length) return "";
  return entries.slice(0, 5).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`).join("\n");
}

function Metrics({ job }: { job: Job }) {
  const evaluation = (job.summary?.evaluation || {}) as Record<string, unknown>;
  const usage = (job.summary?.llm_usage || {}) as Record<string, unknown>;
  return (
    <div className="metrics-strip">
      <Metric label="Quality" value={evaluation.quality_score ? `${evaluation.quality_score}/100` : "pending"} />
      <Metric label="Tokens" value={usage.accounted_total_tokens ? String(usage.accounted_total_tokens) : "pending"} />
      <Metric label="Elapsed" value={job.summary?.elapsed_seconds ? `${job.summary.elapsed_seconds}s` : "pending"} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><Sparkles size={24} /><strong>{title}</strong><span>{text}</span></div>;
}

createRoot(document.getElementById("root")!).render(<App />);
