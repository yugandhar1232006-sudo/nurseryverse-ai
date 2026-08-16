import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        data-slot="textarea"
        className={cn(
          "flex min-h-16 w-full rounded-sm border border-input bg-transparent px-3 py-2 text-body shadow-flat " +
            "transition-colors duration-fast outline-none placeholder:text-muted-foreground " +
            "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 " +
            "disabled:cursor-not-allowed disabled:opacity-50 " +
            "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
