import { Skeleton } from "@/components/ui/skeleton";

/**
 * Next.js App Router convention: automatic Suspense fallback shown while
 * this segment (and anything below it) is loading -- e.g. during a
 * server-rendered data fetch. Feature routes with a more specific known
 * final shape should add their own segment-local loading.tsx (a table
 * skeleton for a list route, a form skeleton for an edit route, etc. --
 * see docs/design/02-component-library.md's SkeletonLoader guidance:
 * "shape/size matching the content it precedes") rather than relying on
 * this generic one, which intentionally stays shape-agnostic.
 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite" className="flex flex-col gap-4 p-6">
      <Skeleton className="h-8 w-48" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    </div>
  );
}
