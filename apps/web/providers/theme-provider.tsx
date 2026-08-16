"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Wraps next-themes so `.dark` gets toggled on <html>, matching the
 * `@custom-variant dark (&:where(.dark, .dark *))` selector defined in
 * globals.css. `disableTransitionOnChange` avoids a flash of transitioning
 * colors on first theme resolution.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
