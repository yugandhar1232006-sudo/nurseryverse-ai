"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { isApiError } from "@/lib/api/error";
import { useConfirmPasswordResetMutation } from "@/lib/auth/mutations";
import { confirmPasswordResetSchema, type ConfirmPasswordResetFormValues } from "@/lib/validation/auth";

/**
 * Must live at exactly `/reset-password` with a `token` query param --
 * the backend's password-reset email embeds this exact URL
 * (`{FRONTEND_BASE_URL}/reset-password?token=...`, see
 * apps/api/app/services/auth_service.py's `request_password_reset`).
 * `NEXT_PUBLIC_API_BASE_URL`'s counterpart on the backend,
 * `FRONTEND_BASE_URL`, must point at this app's origin for the emailed
 * link to resolve here at all -- an ops/config concern documented in
 * docs/frontend/06-authentication.md, not something this page can
 * control.
 */
export default function ResetPasswordPage() {
  return (
    <React.Suspense fallback={null}>
      <ResetPasswordForm />
    </React.Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const mutation = useConfirmPasswordResetMutation();
  const [done, setDone] = React.useState(false);

  const form = useForm<ConfirmPasswordResetFormValues>({
    resolver: zodResolver(confirmPasswordResetSchema),
    defaultValues: { newPassword: "", confirmPassword: "" },
  });

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Invalid reset link</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>Missing reset token</AlertTitle>
            <AlertDescription>This link is missing its reset token. Request a new one below.</AlertDescription>
          </Alert>
          <Link href="/forgot-password" className="mt-4 inline-block text-body-sm text-muted-foreground hover:underline">
            Request a new reset link
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Password reset</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="success">
            <CheckCircle2 />
            <AlertTitle>Your password has been reset</AlertTitle>
            <AlertDescription>
              For security, you&apos;ve been signed out everywhere. Please sign in again with your new password.
            </AlertDescription>
          </Alert>
          <Button className="mt-4 w-full" onClick={() => router.replace("/login")}>
            Go to sign in
          </Button>
        </CardContent>
      </Card>
    );
  }

  function onSubmit(values: ConfirmPasswordResetFormValues) {
    if (!token) return;
    mutation.mutate(
      { token, newPassword: values.newPassword },
      { onSuccess: () => setDone(true) },
    );
  }

  const tokenInvalid =
    isApiError(mutation.error) && mutation.error.status === 422;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Set a new password</CardTitle>
        <CardDescription>Choose a new password for your account.</CardDescription>
      </CardHeader>
      <CardContent>
        {tokenInvalid && (
          <Alert variant="destructive" className="mb-4">
            <AlertTriangle />
            <AlertTitle>Link expired or already used</AlertTitle>
            <AlertDescription>
              {mutation.error?.message ?? "This reset link is invalid or has expired."} Request a new one.
            </AlertDescription>
          </Alert>
        )}
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="newPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm new password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="w-full" disabled={mutation.isPending} aria-busy={mutation.isPending}>
              {mutation.isPending && <Spinner />}
              Reset password
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
