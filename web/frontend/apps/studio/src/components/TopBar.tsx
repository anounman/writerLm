import React from "react";
import { Search, RefreshCw, Plus, Menu } from "lucide-react";
import { Button } from "@writerlm/ui";

interface TopBarProps {
  activeTabLabel: string;
  onSearchClick: () => void;
  onRefresh: () => void;
  onCreateClick: () => void;
  onMenuClick: () => void;
}

export function TopBar({ activeTabLabel, onSearchClick, onRefresh, onCreateClick, onMenuClick }: TopBarProps) {
  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-border bg-background flex-none">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="md:hidden text-muted-foreground" onClick={onMenuClick}>
          <Menu size={16} />
        </Button>
        <h1 className="text-sm font-medium text-foreground">{activeTabLabel}</h1>
      </div>

      <div className="flex items-center gap-2">
        {/* Search bar — desktop */}
        <button
          onClick={onSearchClick}
          className="hidden md:flex items-center gap-2 h-7 px-3 rounded-md border border-border bg-secondary text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors text-xs w-52 cursor-pointer"
        >
          <Search size={12} />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="font-mono text-[10px] bg-muted border border-border rounded px-1">⌘K</kbd>
        </button>
        {/* Search icon — mobile */}
        <Button variant="ghost" size="icon" className="md:hidden text-muted-foreground" onClick={onSearchClick}>
          <Search size={15} />
        </Button>

        <div className="h-4 w-px bg-border hidden sm:block" />

        <Button variant="ghost" size="icon" className="text-muted-foreground hidden sm:flex" onClick={onRefresh} title="Refresh">
          <RefreshCw size={14} />
        </Button>

        <Button size="sm" onClick={onCreateClick}>
          <Plus size={14} />
          New
        </Button>
      </div>
    </header>
  );
}
