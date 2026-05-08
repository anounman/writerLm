import React from "react";
import { BookOpen } from "lucide-react";

interface LoadingScreenProps {
  theme?: "dark" | "light";
  onTheme?: (t: "dark" | "light") => void;
  message?: string;
}

export function LoadingScreen({ message = "Loading…" }: LoadingScreenProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center">
      <div className="w-8 h-8 rounded-md bg-foreground flex items-center justify-center mb-6">
        <BookOpen size={16} strokeWidth={2.5} className="text-background" />
      </div>
      <div className="flex items-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" />
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
