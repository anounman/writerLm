import React from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "../utils";
import { Button } from "./Button";

interface ThemeToggleProps {
  theme: "dark" | "light";
  onTheme: (theme: "dark" | "light") => void;
  className?: string;
}

export function ThemeToggle({ theme, onTheme, className }: ThemeToggleProps) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => onTheme(theme === "dark" ? "light" : "dark")}
      className={cn("text-muted-foreground hover:text-foreground", className)}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </Button>
  );
}
