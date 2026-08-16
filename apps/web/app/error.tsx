"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/error-state";

/**
 * Next.js App Router convention: catches any error thrown while
 * rendering this segment's tree (or its children's) that wasn't already
 * handled locally. Framework-level errors (rendering bugs, unexpected
 * exceptions) rather than expected API-failure states, which each
 * feature's own query/mutation error handling covers with `ErrorState`
 * directly against the real error instead of this generic catch-all.
 */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Intentional: surfaces render-time errors during development and in
    // server logs. A real telemetry sink (Sentry/etc.) is a disclosed
    // future upgrade, not faked here.
    console.error(error);
  }, [error]);

  return (
    <ErrorState
      variant="full-page"
      message="Something went wrong loading this page."
      onRetry={reset}
    />
  );
}
