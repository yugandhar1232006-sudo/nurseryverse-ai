import * as React from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

/**
 * FormActions per docs/design/02-component-library.md: the primary
 * submit target for a form (Enter key works from any field since the
 * primary button has `type="submit"` and is the only submit button in
 * the form). `sticky` turns this into a bottom-anchored bar on mobile
 * for long forms, per that same spec's Responsive note -- desktop/tablet
 * stays inline regardless.
 */
export interface FormActionsProps {
  primaryLabel: string;
  onCancel?: () => void;
  cancelLabel?: string;
  submitting?: boolean;
  disabled?: boolean;
  sticky?: boolean;
  className?: string;
}

export function FormActions({
  primaryLabel,
  onCancel,
  cancelLabel = "Cancel",
  submitting = false,
  disabled = false,
  sticky = false,
  className,
}: FormActionsProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-end gap-3",
        sticky &&
          "sticky bottom-0 -mx-4 border-t border-border bg-card/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-card/80 sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none",
        className,
      )}
    >
      {onCancel && (
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          {cancelLabel}
        </Button>
      )}
      <Button type="submit" disabled={disabled || submitting} aria-busy={submitting}>
        {submitting && <Spinner className="text-current" />}
        {primaryLabel}
      </Button>
    </div>
  );
}
