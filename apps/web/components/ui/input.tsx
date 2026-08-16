import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        data-slot="input"
        className={cn(
          "flex h-9 w-full min-w-0 rounded-sm border border-input bg-transparent px-3 py-1 text-body shadow-flat " +
            "transition-colors duration-fast outline-none file:border-0 file:bg-transparent file:text-body " +
            "file:font-medium placeholder:text-muted-foreground " +
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
Input.displayName = "Input";

export { Input };
