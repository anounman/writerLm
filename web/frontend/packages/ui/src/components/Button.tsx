import React from "react";
import { cn } from "../utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger" | "success";
  size?: "sm" | "md" | "lg" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-1.5 font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 cursor-pointer select-none",
          {
            // Primary — filled
            "bg-primary text-primary-foreground hover:bg-primary/90 rounded-md shadow-sm": variant === "primary",
            // Secondary — subtle fill
            "bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border rounded-md": variant === "secondary",
            // Outline — just border
            "border border-border bg-transparent text-foreground hover:bg-accent hover:text-accent-foreground rounded-md": variant === "outline",
            // Ghost — no border
            "bg-transparent text-foreground hover:bg-accent rounded-md": variant === "ghost",
            // Danger
            "bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive hover:text-destructive-foreground rounded-md": variant === "danger",
            // Success
            "bg-success/10 text-success border border-success/30 hover:bg-success hover:text-primary-foreground rounded-md": variant === "success",
            // Sizes
            "h-7 px-2.5 text-xs": size === "sm",
            "h-8 px-3 text-sm": size === "md",
            "h-10 px-5 text-sm": size === "lg",
            "h-8 w-8 p-0 flex-none": size === "icon",
          },
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
