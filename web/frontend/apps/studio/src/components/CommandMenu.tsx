import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Search, ChevronRight, Monitor, LogOut } from "lucide-react";

interface CommandMenuProps {
  open: boolean;
  onClose: () => void;
  activeTab: string;
  onTab: (tab: any) => void;
  onRefresh: () => void;
  onLogout: () => void;
  tabs: Array<{ id: string; label: string; icon: any }>;
}

export function CommandMenu({ open, onClose, activeTab, onTab, onRefresh, onLogout, tabs }: CommandMenuProps) {
  const [query, setQuery] = useState("");

  useEffect(() => { if (open) setQuery(""); }, [open]);
  useEffect(() => {
    if (!open) return;
    const fn = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", fn); document.body.style.overflow = ""; };
  }, [open, onClose]);

  const actions = [
    ...tabs.map(t => ({ id: `go-${t.id}`, group: "Navigate", label: t.label, icon: t.icon, active: activeTab === t.id, fn: () => onTab(t.id) })),
    { id: "refresh", group: "Actions", label: "Refresh data", icon: Monitor, active: false, fn: onRefresh },
    { id: "logout",  group: "Account", label: "Sign out",     icon: LogOut,  active: false, fn: onLogout },
  ];

  const filtered = query
    ? actions.filter(a => a.label.toLowerCase().includes(query.toLowerCase()))
    : actions;

  const grouped = filtered.reduce<Record<string, typeof actions>>((acc, a) => {
    (acc[a.group] = acc[a.group] || []).push(a);
    return acc;
  }, {});

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}
            className="fixed inset-0 z-[100] bg-background/60 backdrop-blur-sm" onClick={onClose} />
          <div className="fixed inset-0 z-[101] flex items-start justify-center pt-[15vh] px-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.12 }}
              className="w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden pointer-events-auto flex flex-col max-h-[60vh]"
            >
              {/* Input */}
              <div className="flex items-center gap-3 border-b border-border px-4 h-12">
                <Search size={15} className="text-muted-foreground flex-none" />
                <input
                  autoFocus value={query} onChange={e => setQuery(e.target.value)}
                  placeholder="Type a command…"
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
                />
                <kbd className="text-[10px] font-mono bg-secondary border border-border px-1.5 rounded text-muted-foreground">ESC</kbd>
              </div>

              {/* Results */}
              <div className="overflow-y-auto scrollbar-hide py-2">
                {Object.entries(grouped).map(([group, items]) => (
                  <div key={group}>
                    <p className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{group}</p>
                    {items.map(action => {
                      const Icon = action.icon;
                      return (
                        <button
                          key={action.id}
                          onClick={() => { action.fn(); onClose(); }}
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors cursor-pointer group ${action.active ? "text-foreground bg-accent" : "text-foreground hover:bg-accent/60"}`}
                        >
                          <div className={`w-6 h-6 rounded flex items-center justify-center flex-none ${action.active ? "bg-foreground text-background" : "bg-secondary text-muted-foreground group-hover:text-foreground"}`}>
                            <Icon size={13} />
                          </div>
                          <span className="flex-1 text-left font-medium">{action.label}</span>
                          <ChevronRight size={13} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                        </button>
                      );
                    })}
                  </div>
                ))}
                {filtered.length === 0 && (
                  <div className="py-12 text-center text-sm text-muted-foreground">No results for "<span className="text-foreground">{query}</span>"</div>
                )}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
