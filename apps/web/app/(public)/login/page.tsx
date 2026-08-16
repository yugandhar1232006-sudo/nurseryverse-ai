"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { AlertTriangle, Lock, WifiOff } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useLoginMutation } from "@/lib/auth/mutations";
import { classifyLoginError, type LoginErrorKind } from "@/lib/auth/login-error";
import { loginSchema, type LoginFormValues } from "@/lib/validation/auth";

const ERROR_COPY: Partial<Record<LoginErrorKind, { title: string; icon: typeof AlertTriangle }>> = {
  account_locked: { title: "Account temporarily locked", icon: Lock },
  rate_limited: { title: "Too many attempts", icon: AlertTriangle },
  network: { title: "Can't reach the server", icon: WifiOff },
  server: { title: "Service unavailable", icon: AlertTriangle },
};

/**
 * `useSearchParams()` (for the post-login `?next=` redirect target)
 * opts a page out of static rendering unless wrapped in Suspense --
 * Next.js's App Router requirement, not optional. This default export is
 * the actual route component; `LoginForm` below holds everything that
 * needs the search params.
 */
export default function LoginPage() {
  return (
    <React.Suspense fallback={<LoginFormSkeleton />}>
      <LoginForm />
    </React.Suspense>
  );
}

function LoginFormSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Enter your credentials to access your NurseryVerse AI account.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="h-9 animate-pulse rounded-sm bg-muted" />
        <div className="h-9 animate-pulse rounded-sm bg-muted" />
        <div className="h-9 animate-pulse rounded-sm bg-muted" />
      </CardContent>
    </Card>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const loginMutation = useLoginMutation();
  const [formError, setFormError] = React.useState<{ kind: LoginErrorKind; message: string } | null>(null);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  function onSubmit(values: LoginFormValues) {
    setFormError(null);
    loginMutation.mutate(values, {
      onSuccess: () => {
        const next = searchParams.get("next");
        // Only ever follow a same-origin relative path -- `next` comes
        // from a URL query param an attacker could craft, so this must
        // never be treated as a full redirect target (open-redirect
        // prevention).
        const destination = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
        router.replace(destination);
      },
      onError: (error) => setFormError(classifyLoginError(error)),
    });
  }

  const errorCopy = formError ? ERROR_COPY[formError.kind] : undefined;
  const ErrorIcon = errorCopy?.icon ?? AlertTriangle;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Enter your credentials to access your NurseryVerse AI account.</CardDescription>
      </CardHeader>
      <CardContent>
        {formError && (
          <Alert variant={formError.kind === "account_locked" ? "warning" : "destructive"} className="mb-4">
            <ErrorIcon />
            <AlertTitle>{errorCopy?.title ?? "Sign-in failed"}</AlertTitle>
            <AlertDescription>{formError.message}</AlertDescription>
          </Alert>
        )}

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
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center justify-between">
                    <FormLabel>Password</FormLabel>
                    <Link href="/forgot-password" className="text-body-sm text-muted-foreground hover:underline">
                      Forgot password?
                    </Link>
                  </div>
                  <FormControl>
                    <Input type="password" autoComplete="current-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="w-full" disabled={loginMutation.isPending} aria-busy={loginMutation.isPending}>
              {loginMutation.isPending && <Spinner />}
              Sign in
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
