"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { LogOut, Monitor, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { FormActions } from "@/components/form/form-actions";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useSession } from "@/lib/auth/use-session";
import { useMeQuery, useSessionsQuery } from "@/lib/auth/queries";
import {
  useChangePasswordMutation,
  useLogoutAllMutation,
  useRevokeSessionMutation,
} from "@/lib/auth/mutations";
import { toast } from "@/lib/toast";
import { changePasswordSchema, type ChangePasswordFormValues } from "@/lib/validation/auth";

// As of 7C, `app/(app)/layout.tsx` renders every page here through
// `AppShell`, which already wraps `children` in `PageContainer` (the
// shared responsive padding/max-width primitive) and a real route-based
// breadcrumb trail -- this page no longer needs to provide its own outer
// padding, only the `max-w-2xl` narrowing appropriate to a form-heavy
// settings page.
export default function AccountPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <ProfileCard />
      <ChangePasswordCard />
      <SessionsCard />
    </div>
  );
}

function ProfileCard() {
  const { user } = useSession();
  // Keeps /auth/me fresh (e.g. after a permission change elsewhere) --
  // `useSession()` above already has the boot-time snapshot, this just
  // makes the page itself the source that revalidates it.
  useMeQuery();

  if (!user) return <Skeleton className="h-32 w-full" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your account</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-body-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Name</span>
          <span>{user.full_name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Email</span>
          <span className="flex items-center gap-2">
            {user.email}
            {!user.is_email_verified && (
              <Badge variant="tone" tone="warning">
                Unverified
              </Badge>
            )}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Role</span>
          <span>{user.role ?? "—"}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function ChangePasswordCard() {
  const router = useRouter();
  const mutation = useChangePasswordMutation();

  const form = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: ChangePasswordFormValues) {
    mutation.mutate(
      { current_password: values.currentPassword, new_password: values.newPassword },
      {
        onSuccess: () => {
          toast.success("Password changed", {
            description: "You've been signed out everywhere. Please sign in again.",
          });
          router.replace("/login");
        },
        onError: handleApiError,
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>Changing your password signs you out on every other device.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="currentPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="current-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
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
            <FormActions primaryLabel="Change password" submitting={mutation.isPending} />
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

function SessionsCard() {
  const sessionsQuery = useSessionsQuery();
  const revokeMutation = useRevokeSessionMutation();
  const logoutAllMutation = useLogoutAllMutation();
  const router = useRouter();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sessions &amp; security</CardTitle>
        <CardDescription>
          Devices currently signed in to your account.{" "}
          <span className="italic">
            Note: this list can&apos;t currently highlight which entry is your own device (see Known
            Limitations in the auth docs).
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {sessionsQuery.isLoading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {sessionsQuery.isError && (
          <ErrorState
            variant="section"
            error={sessionsQuery.error}
            onRetry={() => sessionsQuery.refetch()}
            retrying={sessionsQuery.isRefetching}
          />
        )}

        {sessionsQuery.data && sessionsQuery.data.length === 0 && (
          <p className="text-body-sm text-muted-foreground">No active sessions found.</p>
        )}

        {sessionsQuery.data?.map((session) => (
          <div key={session.id} className="flex items-center justify-between gap-3 rounded-md border border-border p-3">
            <div className="flex items-center gap-3">
              <Monitor className="size-4 text-muted-foreground" aria-hidden="true" />
              <div className="text-body-sm">
                <div>{session.device_name ?? "Unknown device"}</div>
                <div className="text-caption text-muted-foreground">
                  {session.ip_address ?? "Unknown IP"} · last used{" "}
                  {session.last_used_at ? new Date(session.last_used_at).toLocaleString() : "never"}
                </div>
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={revokeMutation.isPending}
              onClick={() =>
                revokeMutation.mutate(session.id, {
                  onSuccess: () => toast.success("Session revoked."),
                  onError: (error) => toast.apiError(error),
                })
              }
            >
              Revoke
            </Button>
          </div>
        ))}

        <Separator />

        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-body-sm text-muted-foreground">
            <ShieldAlert className="size-4" aria-hidden="true" />
            Signed in somewhere you don&apos;t recognize?
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            disabled={logoutAllMutation.isPending}
            onClick={() =>
              logoutAllMutation.mutate(undefined, {
                onSuccess: () => {
                  toast.success("Signed out of all devices.");
                  router.replace("/login");
                },
                onError: (error) => toast.apiError(error),
              })
            }
          >
            {logoutAllMutation.isPending ? <Spinner /> : <LogOut className="size-4" />}
            Sign out of all devices
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
