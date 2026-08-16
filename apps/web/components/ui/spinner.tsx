import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * LoadingSpinner per docs/design/02-component-library.md's Feedback &
 * System State section: indeterminate short-wait indicator (button
 * loading, small inline fetches). Prefer Skeleton for list/table/card
 * content that has a known final shape -- this is for everything else.
 */
function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <Loader2
      role="status"
      aria-label="Loading"
      className={cn("size-4 animate-spin text-current", className)}
      {...props}
    />
  );
}

export { Spinner };
