import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useAuth, useUser } from "@clerk/react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles, PanelsTopLeft, Library, KeyRound, Settings, X } from "lucide-react";

import { Sidebar, Tab } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { StudioStats } from "./components/StudioStats";
import { CommandMenu } from "./components/CommandMenu";

import { LandingPage } from "./pages/LandingPage";
import { LoadingScreen } from "./pages/LoadingScreen";
import { CreatePage } from "./pages/CreatePage";
import { ProgressPage } from "./pages/ProgressPage";
import { BooksPage } from "./pages/BooksPage";
import { KeysPage } from "./pages/KeysPage";
import { ConfigPage } from "./pages/ConfigPage";

import { ApiClient, Job, GeneratedBook } from "./api";

const TABS: Array<{ id: Tab; label: string; icon: any }> = [
  { id: "create",   label: "Create",   icon: Sparkles },
  { id: "progress", label: "Progress", icon: PanelsTopLeft },
  { id: "books",    label: "Books",    icon: Library },
  { id: "keys",     label: "Keys",     icon: KeyRound },
  { id: "config",   label: "Config",   icon: Settings },
];

type Theme = "dark" | "light";

function getInitialTheme(): Theme {
  return (localStorage.getItem("writerlm_theme") as Theme) ?? "dark";
}

export default function App() {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [activeTab, setActiveTab] = useState<Tab>("create");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [books, setBooks] = useState<GeneratedBook[]>([]);
  const [notice, setNotice] = useState("");
  const [userEmail, setUserEmail] = useState("");

  const api = useMemo(() => new ApiClient(token, isSignedIn ? getToken : undefined), [token, isSignedIn, getToken]);

  // Auth token
  useEffect(() => {
    if (!isLoaded || !isSignedIn) { setToken(null); return; }
    getToken().then(setToken).catch(() => setToken(null));
  }, [isLoaded, isSignedIn, getToken]);

  // Data refresh
  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [me, nextJobs, nextBooks] = await Promise.all([api.me(), api.jobs(), api.books()]);
      setUserEmail(me.email);
      setJobs(nextJobs);
      setBooks(nextBooks);
      if (!selectedJobId && nextJobs[0]) setSelectedJobId(nextJobs[0].id);
    } catch (e) { console.error("Refresh failed", e); }
  }, [api, token, selectedJobId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, [refresh]);

  // Theme
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.classList.toggle("light", theme === "light");
    localStorage.setItem("writerlm_theme", theme);
  }, [theme]);

  // Command menu keyboard shortcut
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCommandOpen(true); }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, []);

  // Auto-dismiss notice
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(id);
  }, [notice]);

  if (!isLoaded) return <LoadingScreen message="Checking authentication…" />;
  if (!isSignedIn) return <LandingPage theme={theme} onTheme={setTheme} />;
  if (!token) return <LoadingScreen message="Connecting to API…" />;

  const selectedJob = jobs.find(j => j.id === selectedJobId) ?? jobs[0] ?? null;
  const activeTabLabel = TABS.find(t => t.id === activeTab)?.label ?? "Studio";

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden transition-colors duration-200">
      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileSidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm md:hidden"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 transition-transform duration-200 md:relative md:translate-x-0
        ${mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"}
      `}>
        <Sidebar
          activeTab={activeTab}
          setActiveTab={tab => { setActiveTab(tab); setMobileSidebarOpen(false); }}
          tabs={TABS}
          theme={theme}
          setTheme={setTheme}
          userEmail={userEmail || user?.primaryEmailAddress?.emailAddress || ""}
          logout={signOut}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <TopBar
          activeTabLabel={activeTabLabel}
          onSearchClick={() => setCommandOpen(true)}
          onRefresh={refresh}
          onCreateClick={() => setActiveTab("create")}
          onMenuClick={() => setMobileSidebarOpen(true)}
        />

        <div className="flex-1 overflow-y-auto scrollbar-hide">
          {/* Stats — always visible */}
          <div className="pt-5">
            <StudioStats jobs={jobs} books={books} />
          </div>

          {/* Page content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.12, ease: "easeOut" }}
            >
              {activeTab === "create" && (
                <CreatePage
                  api={api}
                  onCreated={job => { setJobs(prev => [job, ...prev]); setSelectedJobId(job.id); setActiveTab("progress"); }}
                  onNotice={setNotice}
                />
              )}
              {activeTab === "progress" && (
                <ProgressPage api={api} jobs={jobs} selectedJob={selectedJob} onSelect={setSelectedJobId} onJobs={setJobs} onNotice={setNotice} />
              )}
              {activeTab === "books" && <BooksPage api={api} books={books} onNotice={setNotice} />}
              {activeTab === "keys" && <KeysPage api={api} onNotice={setNotice} />}
              {activeTab === "config" && <ConfigPage api={api} onNotice={setNotice} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Command palette */}
      <CommandMenu
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        activeTab={activeTab}
        onTab={setActiveTab}
        onRefresh={refresh}
        onLogout={() => signOut()}
        tabs={TABS}
      />

      {/* Toast notification */}
      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, y: 16, x: "-50%" }}
            animate={{ opacity: 1, y: 0, x: "-50%" }}
            exit={{ opacity: 0, y: 16, x: "-50%" }}
            transition={{ duration: 0.15 }}
            className="fixed bottom-8 left-1/2 z-[200] flex items-center gap-3 px-4 py-2.5 rounded-lg border border-border bg-card text-foreground text-sm font-medium shadow-xl"
          >
            <span>{notice}</span>
            <button onClick={() => setNotice("")} className="text-muted-foreground hover:text-foreground transition-colors">
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
