import React from "react";
import { Activity, BookOpen, CheckCircle2, Cpu } from "lucide-react";

interface StudioStatsProps {
  jobs: any[];
  books: any[];
}

export function StudioStats({ jobs, books }: StudioStatsProps) {
  const running = jobs.filter(j => {
    const stages = Object.values(j.stages || {});
    return j.status === "running" || stages.some((s: any) => s.status === "running");
  }).length;
  const completed = jobs.filter(j => j.status === "completed" || j.status === "completed_with_latex_issue").length;
  const latestStatus = jobs[0]?.status?.replaceAll("_", " ") ?? "idle";

  const stats = [
    { label: "Active runs",    value: String(running),          icon: Activity,     accent: running > 0 ? "text-success" : "text-muted-foreground" },
    { label: "Books total",    value: String(books.length),     icon: BookOpen,     accent: "text-muted-foreground" },
    { label: "Completed",      value: String(completed),        icon: CheckCircle2, accent: "text-muted-foreground" },
    { label: "Latest status",  value: latestStatus,             icon: Cpu,          accent: "text-muted-foreground" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 px-5 mb-6">
      {stats.map(({ label, value, icon: Icon, accent }) => (
        <div key={label} className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
            <Icon size={14} className={accent} />
          </div>
          <p className="text-2xl font-semibold tracking-tight text-foreground capitalize">{value}</p>
        </div>
      ))}
    </div>
  );
}
