import React from "react";
import { LogOut, BookOpen } from "lucide-react";
import { ThemeToggle, Button } from "@writerlm/ui";
import { UserButton } from "@clerk/react";

function cn(...classes: (string | undefined | false)[]) { return classes.filter(Boolean).join(" "); }

export type Tab = "create" | "progress" | "books" | "keys" | "config";

interface SidebarProps {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  tabs: Array<{ id: Tab; label: string; icon: any }>;
  theme: "dark" | "light";
  setTheme: (t: "dark" | "light") => void;
  userEmail: string;
  logout: () => void;
}

export function Sidebar({ activeTab, setActiveTab, tabs, theme, setTheme, userEmail, logout }: SidebarProps) {
  return (
    <aside className="w-[220px] flex-none flex flex-col border-r border-border bg-background h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 h-12 px-4 border-b border-border">
        <div className="w-5 h-5 rounded bg-foreground flex items-center justify-center flex-none">
          <BookOpen size={11} strokeWidth={2.5} className="text-background" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-foreground">WriterLM</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 overflow-y-auto scrollbar-hide">
        <div className="space-y-px">
          {tabs.map(({ id, label, icon: Icon }) => {
            const active = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors cursor-pointer",
                  active
                    ? "bg-accent text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                )}
              >
                <Icon size={15} strokeWidth={active ? 2.5 : 2} />
                {label}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3 space-y-1">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2 min-w-0">
            <UserButton />
            <p className="text-xs text-muted-foreground truncate">{userEmail}</p>
          </div>
          <ThemeToggle theme={theme} onTheme={setTheme} />
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-muted-foreground gap-2 h-8"
          onClick={logout}
        >
          <LogOut size={13} />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
