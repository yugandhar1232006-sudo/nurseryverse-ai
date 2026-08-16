"use client";

import { useEffect } from "react";

/**
 * Catches errors in the root layout itself (providers, fonts, etc.) --
 * app/error.tsx can't cover this case because it renders *inside* the
 * root layout, which is exactly what would be broken. Per Next.js
 * convention this must render its own <html>/<body> and cannot assume
 * globals.css's tokens or any provider (ThemeProvider/QueryProvider/etc.)
 * are working, hence the plain inline styles instead of Tailwind classes.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          display: "flex",
          minHeight: "100vh",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "12px",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          textAlign: "center",
          padding: "24px",
        }}
      >
        <p style={{ fontSize: "14px", color: "#5c574f" }}>
          NurseryVerse hit an unexpected error and couldn&apos;t load. Please try again.
        </p>
        <button
          onClick={reset}
          style={{
            padding: "8px 16px",
            borderRadius: "6px",
            border: "1px solid #d1cec9",
            background: "transparent",
            cursor: "pointer",
            fontSize: "13px",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
