"use client";

import * as React from "react";
import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { CheckCircle2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useRequestPasswordResetMutation } from "@/lib/auth/mutations";
import { toast } from "@/lib/toast";
import { requestPasswordResetSchema, type RequestPasswordResetFormValues } from "@/lib/validation/auth";

/**
 * The backend (`POST /auth/password/reset/request`) always returns
 * success regardless of whether the email is registered -- an explicit
 * account-enumeration defense (apps/api/app/services/auth_service.py's
 * `request_password_reset` docstring). This page shows the identical
 * "if that email is registered..." message the backend itself returns,
 * for every submission that reaches the server -- there is no
 * "email not found" state to design for here, on purpose.
 */
export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = React.useState(false);
  const mutation = useRequestPasswordResetMutation();

  const form = useForm<RequestPasswordResetFormValues>({
    resolver: zodResolver(requestPasswordResetSchema),
    defaultValues: { email: "" },
  });

  function onSubmit(values: RequestPasswordResetFormValues) {
    mutation.mutate(values.email, {
      onSuccess: () => setSubmitted(true),
      onError: (error) => toast.apiError(error),
    });
  }

  if (submitted) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Check your email</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="success">
            <CheckCircle2 />
            <AlertTitle>Reset link sent</AlertTitle>
            <AlertDescription>
              If that email is registered, a password reset link has been sent. It expires in 60 minutes.
            </AlertDescription>
          </Alert>
          <Link href="/login" className="mt-4 inline-block text-body-sm text-muted-foreground hover:underline">
            Back to sign in
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Forgot password</CardTitle>
        <CardDescription>Enter your email and we&apos;ll send you a link to reset your password.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" placeholder="you@example.com" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="w-full" disabled={mutation.isPending} aria-busy={mutation.isPending}>
              {mutation.isPending && <Spinner />}
              Send reset link
            </Button>
            <Link href="/login" className="text-center text-body-sm text-muted-foreground hover:underline">
              Back to sign in
            </Link>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
