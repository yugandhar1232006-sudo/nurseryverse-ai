import * as React from "react";
import Link from "next/link";

/**
 * Minimal layout for unauthenticated-facing routes (login, password
 * reset, email verification) -- deliberately shares no chrome with
 * app/(app)/layout.tsx's AppHeader/nav. A signed-out visitor has no
 * session to show a header for.
 */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="mb-8 text-h3 font-semibold text-foreground">
        NurseryVerse AI
      </Link>
      <div className="w-full max-w-sm">{children}</div>
    </div>
  );
}
