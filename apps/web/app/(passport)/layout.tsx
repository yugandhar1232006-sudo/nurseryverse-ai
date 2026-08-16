import * as React from "react";

/**
 * Layout for the one public, unauthenticated surface in this app -- the
 * tokenized Plant Passport certificate a customer reaches by scanning a
 * physical QR tag, per docs/ux/15-plant-passport-workflow.md ("customer
 * scans tag - no login required"). Deliberately its own route group,
 * separate from both `app/(app)/layout.tsx` (which redirects anyone
 * without a session to `/login`) and `app/(public)/layout.tsx` (built for
 * a signed-out visitor who is *about to* sign in -- its branding links
 * back into the app). Neither fits here: this page must never redirect
 * to a login screen (there is nothing to log into for this visitor), and
 * the branding below is plain text, not a `Link`, so a customer viewing
 * their plant's certificate is never invited into the internal app.
 */
export default function PassportLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center px-4 py-10">
      <span className="mb-8 text-h3 font-semibold text-foreground">NurseryVerse AI · Plant Passport</span>
      <div className="w-full max-w-2xl">{children}</div>
    </div>
  );
}
