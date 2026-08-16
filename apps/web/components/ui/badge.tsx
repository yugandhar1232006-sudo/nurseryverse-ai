import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * `variant` covers shadcn/ui's generic set; `tone` layers this project's
 * own domain-specific semantic colors (success/warning/danger/info) on
 * top -- kept as a second prop rather than folding into `variant` so a
 * StatusBadge (health status, order status, etc. -- docs/design/
 * 02-component-library.md) can compose freely without needing five near-
 * duplicate variant names.
 */
const badgeVariants = cva(
  "inline-flex items-center justify-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 " +
    "text-caption font-medium transition-colors duration-fast w-fit " +
    "[&_svg]:pointer-events-none [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-foreground",
        tone: "border-transparent",
      },
      tone: {
        neutral: "",
        success: "bg-success-light text-success-dark",
        warning: "bg-warning-light text-warning-dark",
        danger: "bg-danger-light text-danger-dark",
        info: "bg-info-light text-info-dark",
        ai: "bg-ai-accent-50 text-ai-accent-700",
      },
    },
    defaultVariants: {
      variant: "default",
      tone: "neutral",
    },
  },
);

export interface BadgeProps
  extends React.ComponentProps<"span">,
    VariantProps<typeof badgeVariants> {
  asChild?: boolean;
}

function Badge({ className, variant, tone, asChild = false, ...props }: BadgeProps) {
  const Comp = asChild ? Slot : "span";
  return <Comp data-slot="badge" className={cn(badgeVariants({ variant: tone !== "neutral" ? "tone" : variant, tone, className }))} {...props} />;
}

export { Badge, badgeVariants };
