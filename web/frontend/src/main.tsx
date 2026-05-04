import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider, SignInButton, SignUpButton, UserButton, useAuth, useUser } from "@clerk/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  Activity,
  BookOpen,
  Box,
  Check,
  ChevronRight,
  Command,
  Cpu,
  Download,
  FileCode2,
  FileText,
  KeyRound,
  Library,
  LogOut,
  Moon,
  PanelsTopLeft,
  Play,
  RefreshCw,
  Save,
  Search,
  Settings,
  Sparkles,
  Sun,
  Terminal,
  Timer,
  Trash2,
  Upload,
  UserRound,
  X
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
  topic: "HMI 2 practice handbook with theory",
  audience: "Beginner to intermediate students preparing from course notes and exercise sheets",
  tone: "Clear, rigorous, and friendly",
  book_type: "auto",
  theory_practice_balance: "balanced",
  pedagogy_style: "auto",
  source_usage: "auto",
  exercise_strategy: "extract_patterns",
  goals: [
    "explain the theory with a clear mathematical structure",
    "teach the methods needed to solve the uploaded exercise sheets",
    "create original worked examples inspired by the source questions"
  ],
  project_based: false,
  running_project_description: null,
  code_density: "low",
  example_density: "high",
  diagram_density: "medium",
  max_section_words: 900,
  force_web_research: false,
};

const stageOrder = ["planner_research", "notes_synthesis", "writer", "reviewer", "assembler", "latex_compile"];
type Theme = "dark" | "light";
type BookType = BookRequest["book_type"];
type TheoryPracticeBalance = BookRequest["theory_practice_balance"];
type PedagogyStyle = BookRequest["pedagogy_style"];
type SourceUsage = BookRequest["source_usage"];
type ExerciseStrategy = BookRequest["exercise_strategy"];
const animatedStyle = { willChange: "opacity, transform" };
const apiKeyAliases: Record<ApiKeyProvider, string[]> = {
  google: ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY", "GENAI_API_KEY"],
  groq: ["GROQ_API_KEY"],
  tavily: ["TAVILY_API_KEY"],
  firecrawl: ["FIRECRAWL_API_KEY", "FIRECRAWL_KEY"],
  neon: ["NEON_DATABASE_URL", "WRITERLM_USER_NEON_DATABASE_URL"]
};

const bookTypeOptions: Array<{ value: BookType; label: string; hint: string }> = [
  { value: "auto", label: "Auto detect", hint: "Infer from topic, goals, and uploaded sources" },
  { value: "textbook", label: "Textbook", hint: "Structured theory with examples" },
  { value: "course_companion", label: "Course companion", hint: "Follow uploaded notes and sheets closely" },
  { value: "practice_workbook", label: "Practice workbook", hint: "Problem patterns, drills, and worked solutions" },
  { value: "exam_prep", label: "Exam prep", hint: "Focused revision and question strategy" },
  { value: "conceptual_guide", label: "Conceptual guide", hint: "Mental models and intuition" },
  { value: "reference_handbook", label: "Reference handbook", hint: "Broad lookup-oriented coverage" },
  { value: "implementation_guide", label: "Implementation guide", hint: "Build or apply something step by step" }
];

const balanceOptions: Array<{ value: TheoryPracticeBalance; label: string; hint: string }> = [
  { value: "balanced", label: "Balanced", hint: "Theory, examples, and practice in rhythm" },
  { value: "theory_heavy", label: "Theory-heavy", hint: "Definitions, derivations, proofs, and rigor first" },
  { value: "practice_heavy", label: "Practice-heavy", hint: "Theory followed by worked examples and exercises" },
  { value: "implementation_heavy", label: "Implementation-heavy", hint: "Applied build or execution focus" },
  { value: "auto", label: "Auto", hint: "Let sources and goals decide" }
];

const pedagogyOptions: Array<{ value: PedagogyStyle; label: string; hint: string }> = [
  { value: "auto", label: "Auto", hint: "Use the best style for the source material" },
  { value: "german_theoretical", label: "German theoretical", hint: "Rigorous theory-first explanation" },
  { value: "indian_theory_then_examples", label: "Theory then examples", hint: "Theory, solved examples, then practice" },
  { value: "exam_oriented", label: "Exam-oriented", hint: "Question patterns, tricks, and revision flow" },
  { value: "socratic", label: "Socratic", hint: "Question-led discovery" },
  { value: "project_based", label: "Project-based", hint: "One evolving artifact or implementation" }
];

const sourceUsageOptions: Array<{ value: SourceUsage; label: string; hint: string }> = [
  { value: "auto", label: "Auto", hint: "Uploaded PDFs become primary when attached" },
  { value: "primary_curriculum", label: "Primary curriculum", hint: "Follow uploaded documents as the main map" },
  { value: "example_inspiration", label: "Example inspiration", hint: "Use sources mainly for question style and examples" },
  { value: "supplemental", label: "Supplemental", hint: "Use sources as supporting references" }
];

const exerciseStrategyOptions: Array<{ value: ExerciseStrategy; label: string; hint: string }> = [
  { value: "extract_patterns", label: "Extract patterns", hint: "Learn the style of uploaded questions" },
  { value: "worked_examples", label: "Worked examples", hint: "Create source-inspired solved examples" },
  { value: "practice_sets", label: "Practice sets", hint: "Generate new exercises after each topic" },
  { value: "none", label: "None", hint: "Avoid exercise-style material" },
  { value: "auto", label: "Auto", hint: "Let sources decide" }
];

function App() {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("writerlm_theme") as Theme) || "dark");
  const api = useMemo(() => new ApiClient(token, isSignedIn ? getToken : undefined), [getToken, isSignedIn, token]);
  const [userEmail, setUserEmail] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("create");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [books, setBooks] = useState<GeneratedBook[]>([]);
  const [notice, setNotice] = useState<string>("");
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!isLoaded || !isSignedIn) {
      setToken(null);
      return;
    }
    getToken()
      .then((nextToken) => {
        if (!cancelled) setToken(nextToken);
      })
      .catch(() => {
        if (!cancelled) setToken(null);
      });
    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn]);

  const logout = useCallback(() => {
    setToken(null);
    signOut().catch(() => undefined);
  }, [signOut]);

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

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) || jobs[0] || null;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("writerlm_theme", theme);
  }, [theme]);

  if (!isLoaded) {
    return <LoadingScreen theme={theme} onTheme={setTheme} />;
  }

  if (!isSignedIn) {
    return <AuthScreen theme={theme} onTheme={setTheme} />;
  }

  if (!token) {
    return <LoadingScreen theme={theme} onTheme={setTheme} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <motion.div className="brand-mark" whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 28 }}><BookOpen size={21} /></motion.div>
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
                {activeTab === tab.id && <motion.span className="nav-indicator" layoutId="nav-indicator" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <ThemeToggle theme={theme} onTheme={setTheme} />
          <div className="user-strip">
            <UserRound size={18} />
            <span>{userEmail || user?.primaryEmailAddress?.emailAddress || "Signed in"}</span>
            <button
              className="icon-button"
              title="Log out"
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
            <UserButton />
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="project-heading">
            <div className="breadcrumb">
              <span>writerlm</span>
              <ChevronRight size={14} />
              <span>production</span>
            </div>
            <h1>{tabs.find((tab) => tab.id === activeTab)?.label}</h1>
            <p>Browser control for books, sources, models, deploy-like runs, and generated artifacts.</p>
          </div>
          <div className="topbar-actions">
            <motion.button className="command-button" onClick={() => setCommandOpen(true)} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 30 }}>
              <Search size={16} />
              <span>Search or jump</span>
              <kbd>⌘K</kbd>
            </motion.button>
            <motion.button className="secondary-button" onClick={() => refresh().catch((error) => setNotice(error.message))} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 30 }}>
              <RefreshCw size={17} />
              Refresh
            </motion.button>
            <motion.button className="primary-button" onClick={() => setActiveTab("create")} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 30 }}>
              <Play size={17} />
              New job
            </motion.button>
          </div>
        </header>

        <StudioStats jobs={jobs} books={books} />

        <AnimatePresence>
          {notice && (
            <motion.div className="notice" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ type: "spring", stiffness: 340, damping: 28 }}>
              {notice}
            </motion.div>
          )}
        </AnimatePresence>

        <CommandMenu
          open={commandOpen}
          onClose={() => setCommandOpen(false)}
          activeTab={activeTab}
          onTab={(tab) => setActiveTab(tab)}
          onRefresh={() => refresh().catch((error) => setNotice(error.message))}
          onLogout={logout}
        />

        <AnimatePresence mode="wait">
          <motion.section
            key={activeTab}
            className="page-surface"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: "spring", stiffness: 260, damping: 30 }}
            style={animatedStyle}
          >
            {activeTab === "create" && (
              <CreateBook api={api} onCreated={(job) => {
                setJobs((current) => [job, ...current]);
                setSelectedJobId(job.id);
                setActiveTab("progress");
              }} onNotice={setNotice} />
            )}
            {activeTab === "progress" && <ProgressPage api={api} jobs={jobs} selectedJob={selectedJob} onSelect={setSelectedJobId} onJobs={setJobs} onNotice={setNotice} />}
            {activeTab === "books" && <BooksPage api={api} books={books} onNotice={setNotice} />}
            {activeTab === "keys" && <KeysPage api={api} onNotice={setNotice} />}
            {activeTab === "config" && <ConfigPage api={api} onNotice={setNotice} />}
          </motion.section>
        </AnimatePresence>
      </main>
    </div>
  );
}

function StudioStats({ jobs, books }: { jobs: Job[]; books: GeneratedBook[] }) {
  const running = jobs.filter((job) => job.status === "running").length;
  const completed = jobs.filter((job) => job.status === "completed" || job.status === "completed_with_latex_issue").length;
  const latest = jobs[0];
  const stats = [
    { label: "Active runs", value: String(running), icon: Activity },
    { label: "Generated books", value: String(books.length), icon: BookOpen },
    { label: "Completed jobs", value: String(completed), icon: Check },
    { label: "Latest status", value: latest ? latest.status.replaceAll("_", " ") : "idle", icon: Cpu }
  ];

  return (
    <motion.section
      className="stats-grid"
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.045 } }, hidden: {} }}
    >
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <motion.article
            className="stat-card"
            key={stat.label}
            variants={{ hidden: { opacity: 0, y: 10 }, visible: { opacity: 1, y: 0 } }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            style={animatedStyle}
          >
            <div>
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
            </div>
            <Icon size={18} />
          </motion.article>
        );
      })}
    </motion.section>
  );
}

function CommandMenu({
  open,
  onClose,
  activeTab,
  onTab,
  onRefresh,
  onLogout
}: {
  open: boolean;
  onClose: () => void;
  activeTab: Tab;
  onTab: (tab: Tab) => void;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const actions: Array<{ label: string; detail: string; icon: React.ComponentType<{ size?: number }>; run: () => void; active?: boolean }> = [
    ...tabs.map((tab) => ({
      label: `Go to ${tab.label}`,
      detail: tab.id === "create" ? "Create a new book generation job" : `Open ${tab.label.toLowerCase()}`,
      icon: tab.icon,
      active: activeTab === tab.id,
      run: () => onTab(tab.id)
    })),
    { label: "Refresh data", detail: "Sync jobs, books, and account state", icon: RefreshCw, run: onRefresh },
    { label: "Log out", detail: "End this browser session", icon: LogOut, run: onLogout }
  ];
  const filteredActions = actions.filter((action) => `${action.label} ${action.detail}`.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (!open) return;
    setQuery("");
    window.setTimeout(() => inputRef.current?.focus(), 40);
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="command-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          onMouseDown={onClose}
        >
          <motion.div
            className="command-menu"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 360, damping: 30 }}
            style={animatedStyle}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="command-input">
              <Command size={17} />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search pages and actions"
              />
              <button className="icon-button" type="button" onClick={onClose}><X size={16} /></button>
            </div>
            <div className="command-list">
              {filteredActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    type="button"
                    className={action.active ? "command-row active" : "command-row"}
                    key={action.label}
                    onClick={() => {
                      action.run();
                      onClose();
                    }}
                  >
                    <Icon size={17} />
                    <span>
                      <strong>{action.label}</strong>
                      <small>{action.detail}</small>
                    </span>
                    {action.active && <Check size={16} />}
                  </button>
                );
              })}
              {!filteredActions.length && <div className="command-empty">No matching actions</div>}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function AuthScreen({ theme, onTheme }: { theme: Theme; onTheme: (theme: Theme) => void }) {
  return (
    <div className="auth-screen">
      <div className="auth-theme">
        <ThemeToggle theme={theme} onTheme={onTheme} />
      </div>
      <motion.div
        className="auth-panel"
        initial={{ opacity: 0, scale: 0.97, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 24 }}
        style={animatedStyle}
      >
        <div className="auth-symbol"><Sparkles size={26} /></div>
        <h1>WriterLM Studio</h1>
        <p>Run the full AI book pipeline from one browser workspace.</p>
        <div className="auth-actions">
          <SignInButton mode="modal">
            <motion.button className="primary-button" type="button" whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 30 }}>
              <ChevronRight size={18} />
              Log in
            </motion.button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button className="secondary-button" type="button">Create account</button>
          </SignUpButton>
        </div>
      </motion.div>
    </div>
  );
}

function LoadingScreen({ theme, onTheme }: { theme: Theme; onTheme: (theme: Theme) => void }) {
  return (
    <div className="auth-screen">
      <div className="auth-theme">
        <ThemeToggle theme={theme} onTheme={onTheme} />
      </div>
      <motion.div className="auth-panel" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 260, damping: 24 }} style={animatedStyle}>
        <div className="auth-symbol"><RefreshCw size={24} className="spin" /></div>
        <h1>Loading WriterLM</h1>
        <p>Preparing your authenticated studio session.</p>
      </motion.div>
    </div>
  );
}

function ThemeToggle({ theme, onTheme }: { theme: Theme; onTheme: (theme: Theme) => void }) {
  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {(["dark", "light"] as const).map((mode) => {
        const Icon = mode === "dark" ? Moon : Sun;
        return (
          <button key={mode} type="button" className={theme === mode ? "selected" : ""} onClick={() => onTheme(mode)} title={mode === "dark" ? "Dark mode" : "Light mode"}>
            {theme === mode && <motion.span className="theme-indicator" layoutId="theme-indicator" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <Icon size={15} />
          </button>
        );
      })}
    </div>
  );
}

function CreateBook({ api, onCreated, onNotice }: { api: ApiClient; onCreated: (job: Job) => void; onNotice: (message: string) => void }) {
  const [request, setRequest] = useState<BookRequest>(defaultBookRequest);
  const [goalText, setGoalText] = useState(defaultBookRequest.goals.join("\n"));
  const [submitting, setSubmitting] = useState(false);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasPdfs = pdfFiles.length > 0;
  const webResearchEnabled = !hasPdfs || request.force_web_research;

  function addFiles(incoming: FileList | File[]) {
    const valid = Array.from(incoming).filter(f => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (!valid.length) { onNotice("Only PDF files are accepted."); return; }
    setPdfFiles(prev => {
      const existing = new Set(prev.map(f => f.name));
      return [...prev, ...valid.filter(f => !existing.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setPdfFiles(prev => prev.filter(f => f.name !== name));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    const finalRequest = { ...request, goals: goalText.split("\n").map(item => item.trim()).filter(Boolean) };
    try {
      const job = hasPdfs
        ? await api.createJobWithPdfs(finalRequest, pdfFiles)
        : await api.createJob(finalRequest);
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
          <label>
            Book type
            <select value={request.book_type} onChange={(e) => setRequest({ ...request, book_type: e.target.value as BookType })}>
              {bookTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{bookTypeOptions.find((option) => option.value === request.book_type)?.hint}</small>
          </label>
          <label>
            Theory / practice
            <select value={request.theory_practice_balance} onChange={(e) => setRequest({ ...request, theory_practice_balance: e.target.value as TheoryPracticeBalance })}>
              {balanceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{balanceOptions.find((option) => option.value === request.theory_practice_balance)?.hint}</small>
          </label>
          <label>
            Teaching style
            <select value={request.pedagogy_style} onChange={(e) => setRequest({ ...request, pedagogy_style: e.target.value as PedagogyStyle })}>
              {pedagogyOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{pedagogyOptions.find((option) => option.value === request.pedagogy_style)?.hint}</small>
          </label>
          <label>
            Uploaded sources
            <select value={request.source_usage} onChange={(e) => setRequest({ ...request, source_usage: e.target.value as SourceUsage })}>
              {sourceUsageOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{sourceUsageOptions.find((option) => option.value === request.source_usage)?.hint}</small>
          </label>
          <label className="span-2">
            Exercise handling
            <select value={request.exercise_strategy} onChange={(e) => setRequest({ ...request, exercise_strategy: e.target.value as ExerciseStrategy })}>
              {exerciseStrategyOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <small>{exerciseStrategyOptions.find((option) => option.value === request.exercise_strategy)?.hint}</small>
          </label>
          <label className="span-2">Goals<textarea value={goalText} onChange={(e) => setGoalText(e.target.value)} rows={5} /></label>
          {(request.project_based || request.book_type === "implementation_guide") && (
            <label className="span-2">Running project<input value={request.running_project_description || ""} onChange={(e) => setRequest({ ...request, running_project_description: e.target.value || null })} /></label>
          )}
        </div>
      </section>

      <section className="control-panel wide">
        <PanelTitle
          icon={Upload}
          title="Research Sources"
          meta={hasPdfs ? `${pdfFiles.length} PDF${pdfFiles.length > 1 ? "s" : ""} attached` : "Web research is the default source"}
        />
        <motion.div
          className={`pdf-dropzone${isDragging ? " dragging" : ""}${hasPdfs ? " has-files" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files); }}
          whileHover={{ y: -2, scale: 1.002 }}
          transition={{ type: "spring", stiffness: 360, damping: 26 }}
          style={animatedStyle}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            style={{ display: "none" }}
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          {hasPdfs ? (
            <ul className="pdf-file-list" onClick={(e) => e.stopPropagation()}>
              {pdfFiles.map(f => (
                <li key={f.name}>
                  <FileText size={15} />
                  <span>{f.name}</span>
                  <span className="pdf-size">{(f.size / 1024).toFixed(0)} KB</span>
                  <button type="button" className="icon-button" onClick={() => removeFile(f.name)}><Trash2 size={14} /></button>
                </li>
              ))}
              <li className="pdf-add-more" onClick={() => fileInputRef.current?.click()}>
                <Upload size={14} />
                <span>Add more PDFs</span>
              </li>
            </ul>
          ) : (
            <div className="dropzone-prompt">
              <Upload size={28} />
              <strong>Drop PDF files here</strong>
              <span>or click to browse &nbsp;·&nbsp; Only PDF files accepted</span>
            </div>
          )}
        </motion.div>
        <div className="source-mode">
          <div>
            <strong>{webResearchEnabled ? "Web research on" : "PDF-only research"}</strong>
            <span>{hasPdfs ? "Uploaded PDFs stay primary; web search only supplements them when this is on." : "At least one source is required, so web research stays on until PDFs are attached."}</span>
          </div>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={webResearchEnabled}
              disabled={!hasPdfs}
              onChange={(e) => setRequest({ ...request, force_web_research: e.target.checked })}
            />
            <span />
          </label>
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
        <motion.button className="primary-button full" disabled={submitting} whileHover={{ y: submitting ? 0 : -1 }} whileTap={{ scale: submitting ? 1 : 0.98 }} transition={{ type: "spring", stiffness: 420, damping: 30 }}>
          <Play size={18} />
          {submitting ? "Starting" : hasPdfs ? `Start - ${pdfFiles.length} PDF${pdfFiles.length > 1 ? "s" : ""}${request.force_web_research ? " + web" : ""}` : "Start generation"}
        </motion.button>
      </section>
    </form>
  );
}

function ProgressPage({
  api,
  jobs,
  selectedJob,
  onSelect,
  onJobs,
  onNotice
}: {
  api: ApiClient;
  jobs: Job[];
  selectedJob: Job | null;
  onSelect: (id: number) => void;
  onJobs: React.Dispatch<React.SetStateAction<Job[]>>;
  onNotice: (message: string) => void;
}) {
  const shouldReduceMotion = useReducedMotion();
  const canStop = selectedJob?.status === "queued" || selectedJob?.status === "running";

  async function stopSelectedJob() {
    if (!selectedJob) return;
    try {
      const stoppedJob = await api.stopJob(selectedJob.id);
      onJobs((current) => current.map((job) => job.id === stoppedJob.id ? stoppedJob : job));
      onNotice(`Job #${stoppedJob.id} stopped.`);
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Could not stop job.");
    }
  }

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
              <div className="job-hero-actions">
                <StatusPill status={selectedJob.status} />
                {canStop && (
                  <motion.button className="secondary-button" type="button" onClick={stopSelectedJob} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}>
                    <X size={16} />
                    Stop
                  </motion.button>
                )}
              </div>
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
                    style={animatedStyle}
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

function BooksPage({ api, books, onNotice }: { api: ApiClient; books: GeneratedBook[]; onNotice: (message: string) => void }) {
  async function download(book: GeneratedBook, artifactName: string) {
    try {
      const { blob, filename } = await api.downloadArtifact(book.id, artifactName);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Could not download artifact.");
    }
  }

  return (
    <div className="book-grid">
      {books.map((book) => (
        <motion.article key={book.id} className="book-card" whileHover={{ y: -3 }} transition={{ type: "spring", stiffness: 360, damping: 24 }} style={animatedStyle}>
          <div className="book-icon"><BookOpen size={22} /></div>
          <h3>{book.title}</h3>
          <p>{book.topic}</p>
          <div className="book-meta">
            <StatusPill status={book.status} />
            <span>{new Date(book.created_at).toLocaleString()}</span>
          </div>
          <div className="artifact-actions">
            {book.pdf_path && <button className="secondary-button" onClick={() => download(book, "pdf")}><Download size={16} />PDF</button>}
            {book.latex_path && <button className="secondary-button" onClick={() => download(book, "latex")}><FileCode2 size={16} />LaTeX</button>}
          </div>
        </motion.article>
      ))}
      {!books.length && <EmptyState title="No generated books" text="Completed jobs will appear here with downloadable artifacts." />}
    </div>
  );
}

function KeysPage({ api, onNotice }: { api: ApiClient; onNotice: (message: string) => void }) {
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [values, setValues] = useState<Record<ApiKeyProvider, string>>({ google: "", groq: "", tavily: "", firecrawl: "", neon: "" });
  const [detected, setDetected] = useState<ApiKeyProvider[]>([]);
  const [isDraggingEnv, setIsDraggingEnv] = useState(false);
  const envInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => api.apiKeys().then(setKeys).catch((error) => onNotice(error.message)), [api, onNotice]);
  useEffect(() => { refresh(); }, [refresh]);

  async function importEnvFile(file: File) {
    if (!file.name.startsWith(".env") && !file.name.endsWith(".env")) {
      onNotice("Drop a .env file to import API keys.");
      return;
    }
    if (file.size > 1024 * 1024) {
      onNotice(".env file is too large. Please use a file under 1 MB.");
      return;
    }

    const text = await file.text();
    const env = parseEnv(text);
    const nextValues = { ...values };
    const found: ApiKeyProvider[] = [];

    (Object.keys(apiKeyAliases) as ApiKeyProvider[]).forEach((provider) => {
      const keyName = apiKeyAliases[provider].find((name) => env[name]);
      if (keyName && env[keyName]) {
        nextValues[provider] = env[keyName];
        found.push(provider);
      }
    });

    setValues(nextValues);
    setDetected(found);
    onNotice(found.length ? `Imported ${found.length} key${found.length > 1 ? "s" : ""} from ${file.name}. Review and save them.` : "No supported API keys were found in that .env file.");
  }

  function handleEnvFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    importEnvFile(file).catch((error) => onNotice(error instanceof Error ? error.message : "Could not import .env file."));
  }

  async function save(provider: ApiKeyProvider) {
    if (!values[provider]) return;
    await api.saveApiKey(provider, values[provider]);
    setValues({ ...values, [provider]: "" });
    setDetected((current) => current.filter((item) => item !== provider));
    refresh();
  }

  async function saveDetected() {
    const providers = detected.filter((provider) => values[provider]);
    if (!providers.length) return;
    await Promise.all(providers.map((provider) => api.saveApiKey(provider, values[provider])));
    setValues((current) => providers.reduce((next, provider) => ({ ...next, [provider]: "" }), current));
    setDetected([]);
    refresh();
    onNotice(`Saved ${providers.length} imported key${providers.length > 1 ? "s" : ""}.`);
  }

  async function remove(provider: ApiKeyProvider) {
    await api.deleteApiKey(provider);
    refresh();
  }

  const labels: Record<ApiKeyProvider, string> = { google: "Google / Gemini", groq: "Groq", tavily: "Tavily", firecrawl: "Firecrawl", neon: "Neon database" };
  return (
    <div className="keys-layout">
      <section className="env-import-panel">
        <div>
          <span className="eyebrow">Environment Import</span>
          <h2>Drop your `.env` file</h2>
          <p>WriterLM will pull only the supported provider keys and place them into the secure save fields below.</p>
        </div>
        <motion.div
          className={`env-dropzone${isDraggingEnv ? " dragging" : ""}${detected.length ? " has-detected" : ""}`}
          onClick={() => envInputRef.current?.click()}
          onDragOver={(event) => { event.preventDefault(); setIsDraggingEnv(true); }}
          onDragLeave={() => setIsDraggingEnv(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDraggingEnv(false);
            handleEnvFiles(event.dataTransfer.files);
          }}
          whileHover={{ y: -2 }}
          whileTap={{ scale: 0.995 }}
          transition={{ type: "spring", stiffness: 360, damping: 28 }}
          style={animatedStyle}
        >
          <input
            ref={envInputRef}
            type="file"
            accept=".env,text/plain"
            style={{ display: "none" }}
            onChange={(event) => handleEnvFiles(event.target.files)}
          />
          <Upload size={24} />
          <strong>{detected.length ? `${detected.length} key${detected.length > 1 ? "s" : ""} detected` : "Drag and drop .env"}</strong>
          <span>Supports Google/Gemini, Groq, Tavily, Firecrawl, and optional Neon database URLs.</span>
        </motion.div>
        <div className="detected-row">
          {(Object.keys(labels) as ApiKeyProvider[]).map((provider) => (
            <span key={provider} className={detected.includes(provider) ? "detected" : ""}>
              {detected.includes(provider) ? <Check size={13} /> : <KeyRound size={13} />}
              {labels[provider]}
            </span>
          ))}
        </div>
        <motion.button className="primary-button" disabled={!detected.length} onClick={saveDetected} whileHover={{ y: detected.length ? -1 : 0 }} whileTap={{ scale: detected.length ? 0.98 : 1 }}>
          <Save size={16} />
          Save imported keys
        </motion.button>
      </section>

      <div className="key-grid">
        {(Object.keys(labels) as ApiKeyProvider[]).map((provider) => {
          const existing = keys.find((item) => item.provider === provider);
          return (
            <section className={detected.includes(provider) ? "control-panel detected-key" : "control-panel"} key={provider}>
              <PanelTitle icon={KeyRound} title={labels[provider]} meta={existing ? existing.key_hint : "Not saved"} />
              <input type="password" value={values[provider]} placeholder="Paste API key" onChange={(e) => setValues({ ...values, [provider]: e.target.value })} />
              <div className="button-row">
                <motion.button className="primary-button" onClick={() => save(provider)} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}><Save size={16} />Save</motion.button>
                <motion.button className="danger-button" onClick={() => remove(provider)} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}><Trash2 size={16} />Remove</motion.button>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function parseEnv(text: string) {
  const parsed: Record<string, string> = {};
  text.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) return;
    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match) return;
    const [, key, rawValue] = match;
    parsed[key] = cleanEnvValue(rawValue);
  });
  return parsed;
}

function cleanEnvValue(rawValue: string) {
  let value = rawValue.trim();
  const quote = value[0];
  if ((quote === "\"" || quote === "'") && value.endsWith(quote)) {
    return value.slice(1, -1);
  }
  const commentIndex = value.indexOf(" #");
  if (commentIndex >= 0) value = value.slice(0, commentIndex);
  return value.trim();
}

function ConfigPage({ api, onNotice }: { api: ApiClient; onNotice: (message: string) => void }) {
  const [config, setConfig] = useState<PipelineConfig | null>(null);
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [neonDatabaseUrl, setNeonDatabaseUrl] = useState("");
  useEffect(() => {
    Promise.all([api.config(), api.apiKeys()])
      .then(([nextConfig, nextKeys]) => {
        setConfig(nextConfig);
        setKeys(nextKeys);
      })
      .catch((error) => onNotice(error.message));
  }, [api, onNotice]);
  if (!config) return <EmptyState title="Loading config" text="Fetching your pipeline controls." />;
  const neonKey = keys.find((item) => item.provider === "neon");

  function update<K extends keyof PipelineConfig>(key: K, value: PipelineConfig[K]) {
    setConfig({ ...config, [key]: value } as PipelineConfig);
  }

  async function saveNeonDatabaseUrl() {
    if (!neonDatabaseUrl.trim()) return;
    const saved = await api.saveApiKey("neon", neonDatabaseUrl.trim());
    setKeys((current) => [saved, ...current.filter((item) => item.provider !== "neon")]);
    setNeonDatabaseUrl("");
    onNotice("Advanced Neon database URL saved encrypted.");
  }

  async function removeNeonDatabaseUrl() {
    await api.deleteApiKey("neon");
    setKeys((current) => current.filter((item) => item.provider !== "neon"));
    onNotice("Advanced Neon database URL removed.");
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
        <motion.button className="primary-button full" onClick={() => api.saveConfig(config).then(setConfig).then(() => onNotice("Configuration saved."))} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}><Save size={17} />Save config</motion.button>
      </section>
      <section className="control-panel">
        <PanelTitle icon={Cpu} title="Advanced" meta="Optional user-owned Neon database" />
        <label>
          Neon database URL
          <input
            type="password"
            value={neonDatabaseUrl}
            placeholder={neonKey ? neonKey.key_hint : "postgresql://...sslmode=require"}
            onChange={(e) => setNeonDatabaseUrl(e.target.value)}
          />
          <small>{neonKey ? `Saved encrypted: ${neonKey.key_hint}` : "Optional. Stored encrypted and passed only to your jobs as WRITERLM_USER_NEON_DATABASE_URL."}</small>
        </label>
        <div className="button-row">
          <motion.button className="primary-button" type="button" disabled={!neonDatabaseUrl.trim()} onClick={() => saveNeonDatabaseUrl().catch((error) => onNotice(error.message))} whileHover={{ y: neonDatabaseUrl.trim() ? -1 : 0 }} whileTap={{ scale: neonDatabaseUrl.trim() ? 0.98 : 1 }}>
            <Save size={16} />
            Save Neon URL
          </motion.button>
          {neonKey && <button className="danger-button" type="button" onClick={() => removeNeonDatabaseUrl().catch((error) => onNotice(error.message))}><Trash2 size={16} />Remove</button>}
        </div>
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
        {options.map((option) => (
          <button type="button" key={option} className={value === option ? "selected" : ""} onClick={() => onChange(option)}>
            {value === option && <motion.span className="segment-indicator" layoutId={`${label}-segment`} transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <span>{option}</span>
          </button>
        ))}
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
  if (status === "stopped") return <X size={17} />;
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

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  throw new Error("Add your Clerk Publishable Key to VITE_CLERK_PUBLISHABLE_KEY in the frontend environment.");
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={PUBLISHABLE_KEY}>
      <App />
    </ClerkProvider>
  </React.StrictMode>
);
