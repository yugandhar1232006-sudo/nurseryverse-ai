import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Shared empty-state primitive -- used wherever a real backend call
 * succeeded but returned zero items (an empty notification list, no
 * search results, a not-yet-built section landing page). Never used to
 * paper over a *failed* request (that's `ErrorState`) or to show
 * placeholder/fake content -- an empty state says "there is genuinely
 * nothing here," which is always true when it renders.
 */
export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-4 py-10 text-center", className)}>
      {Icon && (
        <div className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-5" aria-hidden="true" />
        </div>
      )}
      <div className="flex flex-col gap-1">
        <p className="text-body font-medium text-foreground">{title}</p>
        {description && <p className="max-w-sm text-body-sm text-muted-foreground">{description}</p>}
      </div>
      {action && (
        <Button type="button" variant="outline" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
