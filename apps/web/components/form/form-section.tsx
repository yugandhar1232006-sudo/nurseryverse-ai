"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * FormSection per docs/design/02-component-library.md: a titled group of
 * fields within a multi-section form (e.g. PG-02 signup). Non-collapsible
 * by default; pass `collapsible` for long forms where letting the user
 * fold away completed sections helps.
 */
export interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  className?: string;
}

export function FormSection({
  title,
  description,
  children,
  collapsible = false,
  defaultOpen = true,
  className,
}: FormSectionProps) {
  const [open, setOpen] = React.useState(defaultOpen);
  const contentId = React.useId();

  return (
    <section className={cn("flex flex-col gap-4 border-b border-border pb-6 last:border-b-0 last:pb-0", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h3 className="text-h4 font-semibold text-foreground">{title}</h3>
          {description && <p className="text-body-sm text-muted-foreground">{description}</p>}
        </div>
        {collapsible && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={contentId}
            onClick={() => setOpen((v) => !v)}
            className="flex size-8 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <ChevronDown className={cn("size-4 transition-transform duration-fast", open && "rotate-180")} />
            <span className="sr-only">{open ? `Collapse ${title}` : `Expand ${title}`}</span>
          </button>
        )}
      </div>
      {(!collapsible || open) && (
        <div id={contentId} className="flex flex-col gap-4">
          {children}
        </div>
      )}
    </section>
  );
}
