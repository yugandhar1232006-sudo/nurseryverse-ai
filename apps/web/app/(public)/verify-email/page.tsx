"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useConfirmEmailVerificationMutation } from "@/lib/auth/mutations";

/**
 * Must live at exactly `/verify-email` with a `token` query param -- the
 * backend's verification email embeds this exact URL
 * (`{FRONTEND_BASE_URL}/verify-email?token=...`, see
 * apps/api/app/services/auth_service.py's `request_email_verification`).
 * Auto-submits on mount rather than requiring a button press -- clicking
 * the emailed link *is* the user's confirmation action, a second click
 * would be redundant friction.
 */
export default function VerifyEmailPage() {
  return (
    <React.Suspense fallback={<Spinner className="size-6" />}>
      <VerifyEmailConfirm />
    </React.Suspense>
  );
}

function VerifyEmailConfirm() {
  const token = useSearchParams().get("token");
  const mutation = useConfirmEmailVerificationMutation();
  const hasSubmitted = React.useRef(false);

  React.useEffect(() => {
    if (!token || hasSubmitted.current) return;
    hasSubmitted.current = true;
    mutation.mutate(token);
    // mutation is a fresh object each render by design (TanStack Query);
    // only re-running this when the token itself changes is correct.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Invalid verification link</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>Missing verification token</AlertTitle>
            <AlertDescription>This link is missing its verification token.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Email verification</CardTitle>
      </CardHeader>
      <CardContent>
        {mutation.isPending && (
          <div className="flex items-center gap-2 text-body-sm text-muted-foreground" role="status">
            <Spinner />
            Verifying your email…
          </div>
        )}
        {mutation.isSuccess && (
          <Alert variant="success">
            <CheckCircle2 />
            <AlertTitle>Email verified</AlertTitle>
            <AlertDescription>
              Your email address has been verified.{" "}
              <Link href="/" className="underline">
                Continue to NurseryVerse AI
              </Link>
              .
            </AlertDescription>
          </Alert>
        )}
        {mutation.isError && (
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>Verification failed</AlertTitle>
            <AlertDescription>
              {mutation.error?.message ?? "This verification link is invalid or has expired."}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
