import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import { AuthProvider } from "@/providers/auth-provider";
import { QueryProvider } from "@/providers/query-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

// Self-hosted via @fontsource-variable/inter rather than next/font/google:
// avoids a runtime dependency on fonts.googleapis.com (blocked by some
// corporate/CI network policies -- this build itself hit that), and
// avoids sending a Google-hosted request on every visitor's first load.
// next/font/local still gets Next's usual font optimizations (self-hosted
// static asset, automatic fallback-metric CSS to prevent layout shift).
const inter = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter",
  display: "swap",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: {
    default: "NurseryVerse AI",
    template: "%s | NurseryVerse AI",
  },
  description:
    "AI-powered nursery management: plant lifecycle, digital twins, inventory, sales, and analytics.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafaf9" },
    { media: "(prefers-color-scheme: dark)", color: "#100f0d" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col antialiased">
        <ThemeProvider>
          <QueryProvider>
            <AuthProvider>
              <TooltipProvider>
                {children}
                <Toaster position="top-right" closeButton richColors />
              </TooltipProvider>
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
