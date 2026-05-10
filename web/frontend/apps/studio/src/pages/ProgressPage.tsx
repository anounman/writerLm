import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { RefreshCw, X, Check, Timer, Activity, AlertTriangle, Download, FileJson, FileText, Clock3, Gauge, Layers3, CircleDot, Wrench, Sparkles, Code2, Image, BookOpenCheck, ShieldCheck, FileDown } from "lucide-react";
import { Button } from "@writerlm/ui";
import { ApiClient, Job, JobArtifact, JobStatus, friendlyApiErrorMessage } from "../api";

interface ProgressPageProps {
  api: ApiClient;
  jobs: Job[];
  selectedJob: Job | null;
  onSelect: (id: number) => void;
  onJobs: React.Dispatch<React.SetStateAction<Job[]>>;
  onNotice: (message: string) => void;
}

const STAGE_ORDER = ["pre_run_quality", "planner_research", "sample_validation", "notes_synthesis", "writer", "reviewer", "quality_checker", "repair", "image_assets", "assembler", "latex_compile"];

function effectiveStatus(job: Job): JobStatus {
  const stages = Object.values(job.stages || {});
  if (stages.some((s: any) => s.status === "running")) return "running";
  if (job.status === "queued" && stages.some((s: any) => s.status === "completed")) return "running";
  return job.status;
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, string> = {
    running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    validating: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    repairing: "bg-purple-500/10 text-purple-300 border-purple-500/20",
    completed: "bg-success/10 text-success border-success/20",
    completed_with_warnings: "bg-yellow-500/10 text-yellow-300 border-yellow-500/20",
    completed_with_major_issues: "bg-red-500/10 text-red-300 border-red-500/20",
    qa_failed: "bg-red-500/10 text-red-300 border-red-500/20",
    needs_user_review: "bg-orange-500/10 text-orange-300 border-orange-500/20",
    failed: "bg-red-500/10 text-red-400 border-red-500/20",
    stopped: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    queued: "bg-muted text-muted-foreground border-border",
    completed_with_latex_issue: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  };
  const dot: Record<string, string> = {
    running: "bg-blue-500 animate-pulse",
    validating: "bg-sky-500 animate-pulse",
    repairing: "bg-purple-500 animate-pulse",
    completed: "bg-success",
    completed_with_warnings: "bg-yellow-500",
    completed_with_major_issues: "bg-red-500",
    qa_failed: "bg-red-500",
    needs_user_review: "bg-orange-500",
    failed: "bg-red-500",
    stopped: "bg-yellow-500",
    queued: "bg-muted-foreground",
    completed_with_latex_issue: "bg-orange-500",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium border rounded-full px-2 py-0.5 ${cfg[status] ?? cfg.queued}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot[status] ?? dot.queued}`} />
      {status.replaceAll("_", " ")}
    </span>
  );
}

function StageIcon({ status }: { status: string }) {
  if (status === "completed") return <Check size={13} className="text-success" strokeWidth={2.5} />;
  if (status === "running") return <RefreshCw size={13} className="text-blue-400 animate-spin" />;
  if (status === "failed") return <AlertTriangle size={13} className="text-red-400" />;
  if (status === "stopped") return <X size={13} className="text-yellow-400" />;
  return <Timer size={13} className="text-muted-foreground" />;
}

function stageTone(status: string) {
  const tones: Record<string, string> = {
    completed: "border-success/30 bg-success/5",
    running: "border-blue-500/30 bg-blue-500/5",
    failed: "border-red-500/30 bg-red-500/5",
    stopped: "border-yellow-500/30 bg-yellow-500/5",
    queued: "border-border bg-card",
  };
  return tones[status] ?? tones.queued;
}

function formatDetails(details: Record<string, unknown>) {
  const entries = Object.entries(details || {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return null;
  return entries.slice(0, 5).map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : String(v)}`).join("\n");
}

function stageDescription(key: string) {
  const descriptions: Record<string, string> = {
    planner_research: "Planning the book structure and gathering source material.",
    notes_synthesis: "Turning research into section-level notes and evidence.",
    writer: "Drafting chapters and examples from the plan.",
    reviewer: "Reviewing sections for quality, correctness, and consistency.",
    quality_checker: "Running deterministic checks and repair passes.",
    image_assets: "Preparing visual assets and image references.",
    assembler: "Assembling the manuscript into final book files.",
    latex_compile: "Rendering the final LaTeX/PDF output.",
  };
  return descriptions[key] ?? "Waiting for pipeline updates.";
}

function stageProgressValue(status: string) {
  if (status === "completed") return 100;
  if (status === "running") return 55;
  if (status === "failed" || status === "stopped") return 100;
  return 0;
}

function formatRuntime(seconds: number | null | undefined) {
  if (!seconds) return "--";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function getProgressSummary(job: Job | null, status: JobStatus | null) {
  const orderedStages = STAGE_ORDER.map(key => [key, job?.stages?.[key]] as const).filter(([, stage]) => Boolean(stage));
  const total = orderedStages.length || STAGE_ORDER.length;
  const completed = orderedStages.filter(([, stage]) => stage?.status === "completed").length;
  const failed = orderedStages.filter(([, stage]) => stage?.status === "failed").length;
  const running = orderedStages.find(([, stage]) => stage?.status === "running");
  const active = running?.[1] || orderedStages.find(([, stage]) => stage?.status === "failed")?.[1] || orderedStages.find(([, stage]) => stage?.status === "stopped")?.[1];
  const terminalComplete = ["completed", "completed_with_latex_issue", "completed_with_warnings", "completed_with_major_issues", "qa_failed", "needs_user_review"].includes(status ?? "");
  const percent = terminalComplete ? 100 : Math.min(100, Math.round(((completed + (running ? 0.45 : 0)) / total) * 100));
  return {
    completed,
    failed,
    total,
    percent,
    activeLabel: active?.label || (terminalComplete ? "Complete" : "Queued"),
  };
}

function categorizeError(message: string | null | undefined) {
  const raw = (message || "").trim();
  const text = raw.toLowerCase();
  if (!raw) {
    return {
      title: "Job failed",
      summary: "The pipeline stopped before it could finish.",
      action: "Download the available logs below, then retry after checking your configuration.",
      raw,
    };
  }
  if (text.includes("rate limit") || text.includes("429") || text.includes("quota") || text.includes("too many requests")) {
    return {
      title: "Rate limit reached",
      summary: "One of the model or research providers rejected the request because the account is temporarily over its allowed usage.",
      action: "Wait a while before retrying, or switch to a provider/model with more available quota in Settings.",
      raw,
    };
  }
  if (text.includes("api key") || text.includes("unauthorized") || text.includes("401") || text.includes("403") || text.includes("permission")) {
    return {
      title: "Provider access problem",
      summary: "A provider key appears to be missing, invalid, or not allowed to use the requested model/service.",
      action: "Check your API keys and selected models, then retry the job.",
      raw,
    };
  }
  if (text.includes("timeout") || text.includes("timed out") || text.includes("connection") || text.includes("network")) {
    return {
      title: "Network or timeout problem",
      summary: "The pipeline could not reach a provider or a provider took too long to respond.",
      action: "Retry the job. If it happens again, try a smaller request or a different provider.",
      raw,
    };
  }
  if (text.includes("latex") || text.includes("pdflatex") || text.includes("xelatex") || text.includes("lualatex")) {
    return {
      title: "Book compiled with a LaTeX issue",
      summary: "The content was generated, but the final document renderer reported a formatting or compilation problem.",
      action: "Download logs and retry. You may also disable strict LaTeX compilation in Settings.",
      raw,
    };
  }
  if (text.includes("validation") || text.includes("invalid json") || text.includes("schema")) {
    return {
      title: "Generated content failed validation",
      summary: "A model response did not match the structured format the pipeline needs.",
      action: "Retry the job. If it repeats, reduce the scope or switch to a stronger model.",
      raw,
    };
  }
  return {
    title: "Pipeline error",
    summary: "The job stopped before completion. The raw diagnostic is available below for troubleshooting.",
    action: "Download the logs and retry the job after reviewing the failed stage.",
    raw,
  };
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProgressPage({ api, jobs, selectedJob, onSelect, onJobs, onNotice }: ProgressPageProps) {
  const status = selectedJob ? effectiveStatus(selectedJob) : null;
  const canStop = status === "running" || status === "queued";
  const canRetry = selectedJob && ["failed", "stopped", "completed_with_latex_issue"].includes(status ?? "");
  const canRepair = selectedJob && ["completed_with_warnings", "completed_with_major_issues", "qa_failed", "needs_user_review", "completed"].includes(status ?? "");
  const hasError = selectedJob?.error_message && status !== "running" && status !== "queued";
  const friendlyError = categorizeError(selectedJob?.error_message);
  const progressSummary = getProgressSummary(selectedJob, status);
  const [artifacts, setArtifacts] = useState<JobArtifact[]>([]);
  const [loadingArtifacts, setLoadingArtifacts] = useState(false);

  useEffect(() => {
    if (!selectedJob || !["failed", "stopped", "completed_with_latex_issue"].includes(status ?? "")) {
      setArtifacts([]);
      return;
    }
    let active = true;
    setLoadingArtifacts(true);
    api.jobArtifacts(selectedJob.id)
      .then(items => { if (active) setArtifacts(items); })
      .catch(() => { if (active) setArtifacts([]); })
      .finally(() => { if (active) setLoadingArtifacts(false); });
    return () => { active = false; };
  }, [api, selectedJob?.id, status]);

  async function stop() {
    if (!selectedJob) return;
    try {
      const s = await api.stopJob(selectedJob.id);
      onJobs(prev => prev.map(j => j.id === s.id ? s : j));
      onNotice(`Job #${s.id} stopped.`);
    } catch (e) { onNotice(friendlyApiErrorMessage(e, "Could not stop job.")); }
  }

  async function retry() {
    if (!selectedJob) return;
    try {
      const r = await api.retryJob(selectedJob.id);
      onJobs(prev => [r, ...prev]);
      onSelect(r.id);
      onNotice(`Retry job #${r.id} started.`);
    } catch (e) { onNotice(friendlyApiErrorMessage(e, "Could not retry job.")); }
  }

  async function repair(action: "repair" | "code" | "diagrams" | "sources" | "showcase") {
    if (!selectedJob) return;
    try {
      const updated = await api.repairJob(selectedJob.id, action);
      onJobs(prev => prev.map(j => j.id === updated.id ? updated : j));
      onNotice(`Repair action queued for job #${updated.id}: ${action.replaceAll("_", " ")}.`);
    } catch (e) { onNotice(friendlyApiErrorMessage(e, "Could not run repair.")); }
  }

  async function downloadArtifact(artifact: JobArtifact) {
    if (!selectedJob) return;
    try {
      const { blob, filename } = await api.downloadJobArtifact(selectedJob.id, artifact.key);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { onNotice(friendlyApiErrorMessage(e, "Download failed.")); }
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4 lg:gap-0 h-full overflow-hidden px-4 sm:px-5">
      {/* Job list */}
      <div className="lg:w-56 flex-none lg:border-r border-border lg:pr-4 overflow-x-auto lg:overflow-y-auto scrollbar-hide py-1 lg:-ml-5 lg:pl-5">
        {jobs.length === 0 && <p className="text-xs text-muted-foreground text-center py-10 lg:py-12">No jobs yet</p>}
        <div className="flex lg:block gap-2 min-w-0 pb-1 lg:pb-0">
        {jobs.map(job => {
          const s = effectiveStatus(job);
          const active = selectedJob?.id === job.id;
          return (
            <button
              key={job.id}
              onClick={() => onSelect(job.id)}
              className={`w-[230px] lg:w-full flex-none text-left px-3 py-3 rounded-lg lg:mb-1 border transition-colors cursor-pointer ${active ? "bg-accent border-border" : "border-transparent hover:bg-accent/50 hover:border-border"}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] text-muted-foreground">#{job.id}</span>
                <StatusBadge status={s} />
              </div>
              <p className={`text-xs font-medium truncate ${active ? "text-foreground" : "text-muted-foreground"}`}>
                {String(job.request_payload?.topic || "Untitled")}
              </p>
            </button>
          );
        })}
        </div>
      </div>

      {/* Detail pane */}
      <div className="flex-1 overflow-y-auto scrollbar-hide lg:pl-5 py-1 min-w-0">
        <AnimatePresence mode="wait">
          {selectedJob ? (
            <motion.div key={selectedJob.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}>
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-4 gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={status ?? ""} />
                    <span className="font-mono text-[10px] text-muted-foreground">#{selectedJob.id}</span>
                  </div>
                  <h2 className="text-lg sm:text-xl font-semibold text-foreground tracking-tight leading-snug break-words">
                    {String(selectedJob.request_payload?.topic || "Generation Task")}
                  </h2>
                </div>
                <div className="flex gap-2 flex-none w-full sm:w-auto">
                  {canRetry && <Button variant="secondary" size="sm" onClick={retry} className="flex-1 sm:flex-none"><RefreshCw size={13} /> Retry</Button>}
                  {canStop && <Button variant="danger" size="sm" onClick={stop} className="flex-1 sm:flex-none"><X size={13} /> Stop</Button>}
                </div>
              </div>

              {/* Progress overview */}
              <div className="rounded-lg border border-border bg-card p-4 sm:p-5 mb-5" aria-live="polite">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-1">
                      <CircleDot size={13} className={status === "running" ? "text-blue-400 animate-pulse" : "text-muted-foreground"} />
                      <span>Current stage</span>
                    </div>
                    <p className="text-base font-semibold text-foreground truncate">{progressSummary.activeLabel}</p>
                    <p className="text-xs text-muted-foreground mt-1">Large books can run for hours; this view updates automatically.</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2 md:w-[360px]">
                    {[
                      { label: "Progress", value: `${progressSummary.percent}%`, icon: Gauge },
                      { label: "Stages", value: `${progressSummary.completed}/${progressSummary.total}`, icon: Layers3 },
                      { label: "Runtime", value: formatRuntime(selectedJob.summary?.elapsed_seconds), icon: Clock3 },
                    ].map(item => (
                      <div key={item.label} className="rounded-md border border-border bg-secondary/35 p-3 min-w-0">
                        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                          <item.icon size={11} />
                          <span className="truncate">{item.label}</span>
                        </div>
                        <p className="text-sm sm:text-base font-semibold text-foreground truncate">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${status === "failed" ? "bg-red-500" : status === "stopped" ? "bg-yellow-500" : "bg-blue-500"}`}
                    style={{ width: `${progressSummary.percent}%` }}
                  />
                </div>
              </div>

              {/* Quality control */}
              <div className="rounded-lg border border-border bg-card p-4 sm:p-5 mb-5">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-1">
                      <ShieldCheck size={13} />
                      <span>Quality control</span>
                    </div>
                    <p className="text-xl font-semibold text-foreground tracking-tight">
                      {selectedJob.summary?.quality?.score != null
                        ? `${selectedJob.summary.quality.score}/100 — ${selectedJob.summary.quality.label}`
                        : selectedJob.summary?.evaluation?.quality_score != null
                          ? `${selectedJob.summary.evaluation.quality_score}/100`
                          : "Quality check pending"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {status === "repairing"
                        ? `Repair pass ${selectedJob.summary?.quality?.repair_passes ?? 0}: fixing weak sections`
                        : selectedJob.summary?.quality?.pre_run_risk?.risk
                          ? `Estimated risk: ${selectedJob.summary.quality.pre_run_risk.risk}. Recommended: ${selectedJob.summary.quality.pre_run_risk.recommended}.`
                          : "Live estimates appear as checkpoints finish."}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 md:w-[420px]">
                    {[
                      { label: "Gate", value: selectedJob.stages?.quality_checker?.status === "running" ? "validating" : selectedJob.current_stage || "queued" },
                      { label: "Repairs", value: String(selectedJob.summary?.quality?.repair_passes ?? 0) },
                      { label: "Target", value: selectedJob.summary?.quality?.target_quality_score ? `${selectedJob.summary.quality.target_quality_score}+` : "75+" },
                    ].map(item => (
                      <div key={item.label} className="rounded-md border border-border bg-secondary/35 p-3 min-w-0">
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">{item.label}</p>
                        <p className="text-sm font-semibold text-foreground truncate">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
                {selectedJob.summary?.quality?.top_issues?.length ? (
                  <div className="mt-4 rounded-md border border-border bg-secondary/40 p-3">
                    <p className="text-xs font-semibold text-foreground mb-2">Quality is low because:</p>
                    <ol className="space-y-1 text-xs text-muted-foreground list-decimal list-inside">
                      {selectedJob.summary.quality.top_issues.slice(0, 5).map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}
                    </ol>
                  </div>
                ) : null}
                {selectedJob.summary?.quality?.breakdown && (
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-2">
                    {Object.entries(selectedJob.summary.quality.breakdown).map(([key, item]) => (
                      <div key={key} className="rounded-md border border-border bg-background/30 p-2">
                        <p className="text-[10px] text-muted-foreground truncate">{item.label}</p>
                        <p className="text-sm font-semibold text-foreground">{item.score}</p>
                      </div>
                    ))}
                  </div>
                )}
                {canRepair && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {[
                      { label: "Repair book", action: "repair", icon: Wrench },
                      { label: "Polish for showcase", action: "showcase", icon: Sparkles },
                      { label: "Regenerate weak sections", action: "repair", icon: RefreshCw },
                      { label: "Remove code examples", action: "code", icon: X },
                      { label: "Improve diagrams", action: "diagrams", icon: Image },
                      { label: "Strengthen sources", action: "sources", icon: BookOpenCheck },
                      { label: "Fix code blocks", action: "code", icon: Code2 },
                    ].map(item => (
                      <Button key={item.label} variant="secondary" size="sm" onClick={() => repair(item.action as any)}>
                        <item.icon size={13} /> {item.label}
                      </Button>
                    ))}
                    <Button variant="ghost" size="sm" onClick={() => onNotice("Export is allowed; use the generated book download from Books once the artifact is available.")}>
                      <FileDown size={13} /> Export anyway
                    </Button>
                  </div>
                )}
              </div>

              {/* Error */}
              {hasError && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 mb-5">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={16} className="flex-none mt-0.5 text-red-400" />
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-red-300">{friendlyError.title}</h3>
                      <p className="text-sm text-red-200/90 mt-1">{friendlyError.summary}</p>
                      <p className="text-xs text-red-200/70 mt-2">{friendlyError.action}</p>
                    </div>
                  </div>
                  {friendlyError.raw && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-widest text-red-200/70">Technical detail</summary>
                      <pre className="mt-2 text-[11px] font-mono text-red-100/80 leading-relaxed whitespace-pre-wrap bg-background/40 p-3 rounded-md border border-red-500/20">
                        {friendlyError.raw}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              {["failed", "stopped", "completed_with_latex_issue", "completed_with_warnings", "completed_with_major_issues", "qa_failed", "needs_user_review"].includes(status ?? "") && (
                <div className="rounded-lg border border-border bg-card p-4 mb-5">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">Troubleshooting downloads</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">Available logs and approved JSON artifacts from this job.</p>
                    </div>
                    {loadingArtifacts && <RefreshCw size={14} className="text-muted-foreground animate-spin" />}
                  </div>
                  {artifacts.length === 0 && !loadingArtifacts ? (
                    <p className="text-xs text-muted-foreground">No downloadable job files are available yet.</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {artifacts.map(artifact => {
                        const Icon = artifact.filename.endsWith(".json") ? FileJson : FileText;
                        return (
                          <button
                            key={`${artifact.key}-${artifact.filename}`}
                            onClick={() => downloadArtifact(artifact)}
                            className="flex items-center gap-2 rounded-md border border-border bg-secondary/40 px-3 py-2 text-left hover:bg-accent transition-colors"
                          >
                            <Icon size={14} className="text-muted-foreground flex-none" />
                            <span className="min-w-0 flex-1">
                              <span className="block text-xs font-medium text-foreground truncate">{artifact.filename}</span>
                              <span className="block text-[10px] text-muted-foreground">{formatBytes(artifact.size_bytes)}</span>
                            </span>
                            <Download size={13} className="text-muted-foreground flex-none" />
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Metrics */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                {[
                  { label: "Quality score", value: selectedJob.summary?.evaluation?.quality_score ? `${selectedJob.summary.evaluation.quality_score}/100` : "—" },
                  { label: "Quality label", value: selectedJob.summary?.quality?.label || "—" },
                  { label: "Tokens used", value: selectedJob.summary?.llm_usage?.accounted_total_tokens ? `${(selectedJob.summary.llm_usage.accounted_total_tokens / 1000).toFixed(1)}k` : "—" },
                  { label: "Weak sections", value: selectedJob.summary?.quality?.weak_section_count != null ? String(selectedJob.summary.quality.weak_section_count) : progressSummary.failed ? String(progressSummary.failed) : "—" },
                ].map(m => (
                  <div key={m.label} className="rounded-lg border border-border bg-card p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">{m.label}</p>
                    <p className="text-xl font-semibold text-foreground tracking-tight">{m.value}</p>
                  </div>
                ))}
              </div>

              {/* Pipeline stages */}
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-foreground">Pipeline stages</h3>
                <span className="text-[10px] font-mono text-muted-foreground">{progressSummary.completed} completed</span>
              </div>
              <div className="space-y-2.5 pb-8">
                {STAGE_ORDER.map(key => {
                  const stage = selectedJob.stages?.[key];
                  if (!stage) return null;
                  const details = formatDetails(stage.details || {});
                  const progress = stageProgressValue(stage.status);
                  return (
                    <div key={key} className={`rounded-lg border p-4 ${stageTone(stage.status)}`}>
                      <div className="flex flex-col sm:flex-row sm:items-start gap-3">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div className="w-7 h-7 rounded-md bg-secondary border border-border flex items-center justify-center flex-none">
                            <StageIcon status={stage.status} />
                          </div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium text-foreground">{stage.label}</span>
                              <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">{stage.status}</span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{stageDescription(key)}</p>
                          </div>
                        </div>
                        <div className="sm:w-36 flex-none">
                          <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground mb-1">
                            <span>{stage.seconds ? formatRuntime(stage.seconds) : stage.status === "running" ? "running" : "waiting"}</span>
                            <span>{progress}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${stage.status === "completed" ? "bg-success" : stage.status === "failed" ? "bg-red-500" : stage.status === "stopped" ? "bg-yellow-500" : "bg-blue-500"}`}
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                        </div>
                      </div>
                      {details && (
                        <pre className="mt-3 text-[11px] font-mono text-muted-foreground leading-relaxed whitespace-pre-wrap bg-secondary/50 p-3 rounded-md border border-border">
                          {details}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ) : (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <Activity size={28} className="text-muted-foreground/30 mb-4" />
              <p className="text-sm font-medium text-muted-foreground">Select a job to view progress</p>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
