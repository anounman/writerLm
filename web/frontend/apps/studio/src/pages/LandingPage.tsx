import React from "react";
import { BookOpen, Github, ChevronRight, Terminal, Brain, FileText, Layers, Search, Code2, PenTool, ArrowRight, Sparkles, Database } from "lucide-react";
import { ThemeToggle, Button } from "@writerlm/ui";
import { SignInButton, SignUpButton } from "@clerk/react";

interface LandingPageProps {
  theme: "dark" | "light";
  onTheme: (theme: "dark" | "light") => void;
}

export function LandingPage({ theme, onTheme }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-background text-foreground transition-colors selection:bg-foreground/10">
      {/* Nav */}
      <header className="fixed inset-x-0 top-0 z-50 h-14 flex items-center justify-between px-6 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-foreground flex items-center justify-center shadow-sm">
            <BookOpen size={13} strokeWidth={2.5} className="text-background" />
          </div>
          <span className="text-sm font-semibold tracking-tight">WriterLM</span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle theme={theme} onTheme={onTheme} />
          <div className="h-4 w-px bg-border mx-1" />
          <SignInButton mode="modal">
            <Button variant="ghost" size="sm" className="font-medium">Sign in</Button>
          </SignInButton>
          <SignUpButton mode="modal">
            <Button size="sm" className="font-medium shadow-sm">Get started</Button>
          </SignUpButton>
        </div>
      </header>

      {/* Hero */}
      <main className="relative pt-48 pb-32 px-6 text-center max-w-5xl mx-auto overflow-hidden">
        {/* Subtle Background Glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] opacity-[0.03] dark:opacity-[0.07] pointer-events-none">
          <div className="absolute inset-0 rounded-full bg-emerald-500 blur-[100px]" />
        </div>

        {/* Badge */}
        <div className="relative inline-flex items-center gap-2 border border-border bg-secondary/50 backdrop-blur-sm text-muted-foreground text-xs font-medium px-4 py-1.5 rounded-full mb-10 transition-colors hover:bg-secondary">
          <Sparkles size={12} className="text-emerald-500" />
          <span>Production-grade AI documentation pipeline</span>
        </div>

        <h1 className="relative text-6xl md:text-[5.5rem] font-bold tracking-tighter text-foreground mb-8 leading-[0.9]">
          Ship technical
          <br />
          <span className="text-muted-foreground bg-clip-text text-transparent bg-gradient-to-r from-foreground/60 to-foreground/30">
            knowledge faster.
          </span>
        </h1>

        <p className="relative text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-12 leading-relaxed font-light">
          WriterLM orchestrates multiple LLMs to autonomously research, draft, and typeset full-length textbooks, course companions, and technical guides.
        </p>

        <div className="relative flex items-center justify-center gap-4 flex-wrap">
          <SignUpButton mode="modal">
            <Button size="lg" className="h-12 px-8 text-sm font-semibold shadow-lg shadow-emerald-500/10">
              Start building <ChevronRight size={16} className="ml-1" />
            </Button>
          </SignUpButton>
          <Button variant="outline" size="lg" className="h-12 px-8 text-sm font-semibold border-border bg-background hover:bg-secondary" onClick={() => window.open("https://github.com/anounman/writerLm", "_blank")}>
            <Github size={16} className="mr-2" /> View on GitHub
          </Button>
        </div>
      </main>

      {/* Bento Grid Features */}
      <section className="max-w-6xl mx-auto px-6 pb-32">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight mb-4">Enterprise-ready architecture</h2>
          <p className="text-muted-foreground max-w-xl mx-auto">A fully containerized pipeline designed for deep research, factual accuracy, and beautiful typography.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 md:grid-rows-2">
          
          {/* Card 1: Multi-LLM Orchestration (Large span) */}
          <div className="md:col-span-2 md:row-span-2 p-8 rounded-2xl border border-border bg-card/50 backdrop-blur-sm flex flex-col relative overflow-hidden group transition-all hover:border-border/80">
            <div className="absolute top-0 right-0 p-8 opacity-10 transition-opacity group-hover:opacity-20">
              <Brain size={120} />
            </div>
            <div className="w-10 h-10 rounded-lg bg-foreground/10 flex items-center justify-center mb-6">
              <Layers size={20} className="text-foreground" />
            </div>
            <h3 className="text-xl font-semibold mb-3">Multi-LLM Orchestration</h3>
            <p className="text-muted-foreground leading-relaxed mb-8 flex-grow">
              Assign the right model for the right job. Use reasoning models like Gemini Flash for curriculum planning, and high-throughput OSS models like Llama 3 for drafting.
            </p>
            <div className="grid grid-cols-2 gap-3 mt-auto">
              <div className="bg-background rounded-lg border border-border p-3 text-xs font-mono text-muted-foreground">
                <span className="text-foreground font-medium block mb-1">Planner</span>
                gemini-2.5-flash
              </div>
              <div className="bg-background rounded-lg border border-border p-3 text-xs font-mono text-muted-foreground">
                <span className="text-foreground font-medium block mb-1">Drafter</span>
                llama-3.3-70b
              </div>
            </div>
          </div>

          {/* Card 2: Hybrid RAG */}
          <div className="md:col-span-2 p-8 rounded-2xl border border-border bg-card/50 backdrop-blur-sm group transition-all hover:border-border/80">
            <div className="flex items-start justify-between mb-6">
              <div className="w-10 h-10 rounded-lg bg-foreground/10 flex items-center justify-center">
                <Search size={20} className="text-foreground" />
              </div>
              <div className="flex gap-2">
                <span className="text-[10px] font-mono uppercase tracking-wider bg-emerald-500/10 text-emerald-500 px-2 py-1 rounded">Web</span>
                <span className="text-[10px] font-mono uppercase tracking-wider bg-blue-500/10 text-blue-500 px-2 py-1 rounded">PDF</span>
              </div>
            </div>
            <h3 className="text-xl font-semibold mb-3">Hybrid Source Ingestion</h3>
            <p className="text-muted-foreground leading-relaxed">
              Upload local PDFs to ground the AI in your proprietary documents, or enable Web Search (via Tavily/Firecrawl) to pull live data from the internet.
            </p>
          </div>

          {/* Card 3: LaTeX Compilation */}
          <div className="md:col-span-1 p-8 rounded-2xl border border-border bg-card/50 backdrop-blur-sm group transition-all hover:border-border/80">
            <div className="w-10 h-10 rounded-lg bg-foreground/10 flex items-center justify-center mb-6">
              <FileText size={20} className="text-foreground" />
            </div>
            <h3 className="text-xl font-semibold mb-3">LaTeX Engine</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Native pdflatex integration compiles mathematically rigorous, publish-ready PDFs instantly.
            </p>
          </div>

          {/* Card 4: Granular Control */}
          <div className="md:col-span-1 p-8 rounded-2xl border border-border bg-card/50 backdrop-blur-sm group transition-all hover:border-border/80">
            <div className="w-10 h-10 rounded-lg bg-foreground/10 flex items-center justify-center mb-6">
              <Code2 size={20} className="text-foreground" />
            </div>
            <h3 className="text-xl font-semibold mb-3">Granular Tone</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Control pedagogy style, theory/practice balance, and code density per book.
            </p>
          </div>

        </div>
      </section>

      {/* Pipeline Journey */}
      <section className="border-t border-border bg-secondary/20 py-32 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="mb-16 text-center">
            <h2 className="text-3xl font-bold tracking-tight mb-4">How it works</h2>
            <p className="text-muted-foreground">A multi-stage pipeline designed to beat context window limits.</p>
          </div>

          <div className="space-y-12 relative">
            {/* Connecting line */}
            <div className="absolute left-[27px] top-6 bottom-6 w-px bg-border md:left-1/2 md:-ml-px" />

            {[
              { 
                step: 1, 
                title: "Planning & Outline", 
                icon: Brain,
                desc: "The Planner LLM parses your prompt and generates a structured JSON table of contents, determining sections, word counts, and pedagogical approach."
              },
              { 
                step: 2, 
                title: "Research Phase", 
                icon: Database,
                desc: "For each section, the Researcher LLM scans your uploaded PDFs and executes targeted web searches to build factual context briefs."
              },
              { 
                step: 3, 
                title: "Parallel Drafting", 
                icon: PenTool,
                desc: "The Drafter LLM processes the research briefs in parallel (chunking up to 12 concurrent workers) to write high-density content in raw LaTeX format."
              },
              { 
                step: 4, 
                title: "Compilation & Review", 
                icon: FileText,
                desc: "The sections are stitched together into a master document. The backend invokes a native LaTeX compiler to generate the final PDF."
              }
            ].map((stage, i) => (
              <div key={stage.step} className="relative flex items-start gap-8 md:justify-center">
                <div className={`hidden md:block w-1/2 pt-2 pr-12 text-right ${i % 2 !== 0 ? 'order-1' : 'order-3 text-left pl-12 pr-0'}`}>
                  <h3 className="text-lg font-semibold mb-2">{stage.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{stage.desc}</p>
                </div>

                <div className={`z-10 flex-shrink-0 w-14 h-14 rounded-full bg-background border-2 border-border flex items-center justify-center ${i % 2 !== 0 ? 'md:order-2' : 'md:order-2'}`}>
                  <stage.icon size={20} className="text-foreground" />
                </div>

                <div className="md:hidden pt-2">
                  <h3 className="text-lg font-semibold mb-2">Step {stage.step}: {stage.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{stage.desc}</p>
                </div>
                
                <div className={`hidden md:block w-1/2 ${i % 2 !== 0 ? 'order-3' : 'order-1'}`} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-32 px-6 text-center border-t border-border">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-6">Ready to generate your first book?</h2>
        <p className="text-muted-foreground mb-10 max-w-lg mx-auto">Create an account, bring your own API keys, and start building long-form technical content.</p>
        <SignUpButton mode="modal">
          <Button size="lg" className="h-12 px-8 font-semibold shadow-lg shadow-emerald-500/10">
            Get started for free
          </Button>
        </SignUpButton>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-10 bg-background">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-muted-foreground/20 flex items-center justify-center">
              <BookOpen size={11} strokeWidth={2.5} className="text-foreground" />
            </div>
            <span className="font-semibold text-foreground">WriterLM</span>
            <span className="px-2">·</span>
            <span>Open Source AI Pipeline</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="https://github.com/anounman/writerLm" target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors flex items-center gap-1.5">
              <Github size={14} /> GitHub
            </a>
            <span>© 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
