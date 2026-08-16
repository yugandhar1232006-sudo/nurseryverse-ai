"use client";

import { MailWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRequestEmailVerificationMutation } from "@/lib/auth/mutations";
import { toast } from "@/lib/toast";

/**
 * Shown whenever an authenticated user's `MeResponse.is_email_verified`
 * is false -- per apps/api/app/services/auth_service.py's `login()`, an
 * unverified account can still log in and use the app normally (nothing
 * server-side blocks it), so this is a soft, dismissable-by-navigating-
 * away nudge, not a hard gate on the rest of the app.
 */
export function EmailVerificationBanner() {
  const mutation = useRequestEmailVerificationMutation();

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 border-b border-warning/30 bg-warning-light px-4 py-2 text-body-sm text-warning-dark"
    >
      <div className="flex items-center gap-2">
        <MailWarning className="size-4 shrink-0" aria-hidden="true" />
        <span>Please verify your email address to secure your account.</span>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={mutation.isPending}
        onClick={() =>
          mutation.mutate(undefined, {
            onSuccess: () => toast.success("Verification email sent. Check your inbox."),
            onError: (error) => toast.apiError(error),
          })
        }
      >
        {mutation.isPending && <Spinner />}
        Resend verification email
      </Button>
    </div>
  );
}
