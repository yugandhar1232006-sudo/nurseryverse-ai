"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Building2 } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { FormActions } from "@/components/form/form-actions";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useCreateOrganizationMutation } from "@/lib/organization/mutations";
import { createOrganizationSchema, type CreateOrganizationFormValues } from "@/lib/validation/organization";

/**
 * Onboarding: `POST /orgs` (see lib/api/organizations.ts's docstring).
 * This is a real, previously-missing gap this phase fills -- a freshly
 * signed-up user (`org_id: null`, `permissions: []`) had no way to reach
 * this backend route from the UI at all before 7E; see
 * docs/frontend/09-organization-management.md's Architecture section.
 * Rendered by app/(app)/settings/page.tsx in place of the tabbed
 * settings UI whenever `user.org_id` is `null` -- there is nothing to
 * manage yet, only an org to create.
 */
export function CreateOrganizationForm() {
  const mutation = useCreateOrganizationMutation();
  const form = useForm<CreateOrganizationFormValues>({
    resolver: zodResolver(createOrganizationSchema),
    defaultValues: { name: "", contact_email: "", contact_phone: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: CreateOrganizationFormValues) {
    mutation.mutate({
      name: values.name,
      contact_email: values.contact_email,
      contact_phone: values.contact_phone || null,
    }, { onError: handleApiError });
  }

  return (
    <Card className="mx-auto max-w-lg">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Building2 className="size-5 text-muted-foreground" aria-hidden="true" />
          <CardTitle>Set up your organization</CardTitle>
        </div>
        <CardDescription>
          You&apos;re signed in, but not yet part of an organization. Create one to become its Owner and unlock the
          rest of NurseryVerse.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Organization name</FormLabel>
                  <FormControl>
                    <Input autoComplete="organization" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="contact_email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Contact email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="contact_phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Contact phone (optional)</FormLabel>
                  <FormControl>
                    <Input type="tel" autoComplete="tel" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormActions primaryLabel="Create organization" submitting={mutation.isPending} />
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
