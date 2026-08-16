"use client";

import * as React from "react";
import { AlertTriangle, RefreshCw, Sparkles } from "lucide-react";

import { isApiError, messageForStatus } from "@/lib/api/error";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * ErrorState per docs/design/02-component-library.md: page/section-level
 * failure display. Message is always plain language (NFR-6.2 -- never a
 * raw stack trace); the raw `error` is only used to pick a message, never
 * rendered directly.
 */
export interface ErrorStateProps {
  error?: unknown;
  /** Overrides the message derived from `error`. */
  message?: string;
  variant?: "full-page" | "section" | "ai-module";
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}

function deriveMessage(error: unknown, override?: string): string {
  if (override) return override;
  if (isApiError(error)) return error.message || messageForStatus(error.status);
  return "Something went wrong. Please try again.";
}

export function ErrorState({
  error,
  message,
  variant = "section",
  onRetry,
  retrying = false,
  className,
}: ErrorStateProps) {
  const resolvedMessage =
    variant === "ai-module"
      ? (message ?? "AI predictions are temporarily unavailable. You can keep working -- everything else in NurseryVerse still works normally.")
      : deriveMessage(error, message);

  const Icon = variant === "ai-module" ? Sparkles : AlertTriangle;

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 text-center",
        variant === "full-page" ? "min-h-[60vh] px-6 py-16" : "px-4 py-10",
        className,
      )}
    >
      <div
        className={cn(
          "flex size-10 items-center justify-center rounded-full",
          variant === "ai-module" ? "bg-ai-accent-50 text-ai-accent-700" : "bg-danger-light text-danger-dark",
        )}
      >
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <p className={cn("max-w-sm text-body-sm text-muted-foreground", variant === "full-page" && "text-body")}>
        {resolvedMessage}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying} aria-busy={retrying}>
          <RefreshCw className={cn("size-4", retrying && "animate-spin")} />
          {retrying ? "Retrying…" : "Try again"}
        </Button>
      )}
    </div>
  );
}
