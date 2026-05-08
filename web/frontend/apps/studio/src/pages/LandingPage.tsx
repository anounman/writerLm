import React from "react";
import { BookOpen, Github, ChevronRight, Terminal } from "lucide-react";
import { ThemeToggle, Button } from "@writerlm/ui";
import { SignInButton, SignUpButton } from "@clerk/react";

interface LandingPageProps {
  theme: "dark" | "light";
  onTheme: (theme: "dark" | "light") => void;
}

export function LandingPage({ theme, onTheme }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-background text-foreground transition-colors">
      {/* Nav */}
      <header className="fixed inset-x-0 top-0 z-50 h-14 flex items-center justify-between px-6 border-b border-border bg-background/90 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 rounded bg-foreground flex items-center justify-center">
            <BookOpen size={11} strokeWidth={2.5} className="text-background" />
          </div>
          <span className="text-sm font-semibold tracking-tight">WriterLM</span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle theme={theme} onTheme={onTheme} />
          <div className="h-4 w-px bg-border" />
          <SignInButton mode="modal">
            <Button variant="ghost" size="sm">Sign in</Button>
          </SignInButton>
          <SignUpButton mode="modal">
            <Button size="sm">Get started</Button>
          </SignUpButton>
        </div>
      </header>

      {/* Hero */}
      <main className="pt-40 pb-24 px-6 text-center max-w-4xl mx-auto">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 border border-border bg-secondary text-muted-foreground text-xs font-medium px-3 py-1 rounded-full mb-8">
          <Terminal size={11} />
          AI-powered technical book generation
        </div>

        <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-foreground mb-6 leading-[0.95]">
          Ship technical<br />
          <span className="text-muted-foreground">documentation faster.</span>
        </h1>

        <p className="text-lg text-muted-foreground max-w-xl mx-auto mb-10 leading-relaxed">
          WriterLM turns your prompts and source material into production-quality textbooks, course companions, and implementation guides.
        </p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <SignUpButton mode="modal">
            <Button size="lg" className="h-11 px-6 text-sm font-semibold">
              Start building <ChevronRight size={16} />
            </Button>
          </SignUpButton>
          <Button variant="outline" size="lg" className="h-11 px-6 text-sm font-semibold" onClick={() => window.open("https://github.com/anounman/writerLm", "_blank")}>
            <Github size={16} /> GitHub
          </Button>
        </div>
      </main>

      {/* Feature grid */}
      <div className="max-w-5xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: "→", title: "Prompt to book", desc: "Describe your topic and audience in plain language. WriterLM handles the rest." },
            { icon: "⊞", title: "PDF source ingestion", desc: "Attach PDFs as primary sources. The pipeline extracts and synthesizes them." },
            { icon: "◎", title: "LaTeX compilation", desc: "Full LaTeX output with professional typesetting, ready to publish." },
          ].map(f => (
            <div key={f.title} className="p-6 rounded-xl border border-border bg-card">
              <div className="text-lg font-mono text-muted-foreground mb-3">{f.icon}</div>
              <h3 className="text-sm font-semibold text-foreground mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-8">
        <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <BookOpen size={13} />
            <span>WriterLM</span>
          </div>
          <span>© 2026 · Open Source</span>
        </div>
      </footer>
    </div>
  );
}
