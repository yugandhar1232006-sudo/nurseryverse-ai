# Component Architecture — Phase 7A (Foundation)

## Layers

1. **`components/ui/`** — unstyled-behavior-plus-tokens primitives (Radix + `cva` + design tokens). One file per primitive, matching shadcn/ui's own file-per-component convention so it stays a drop-in-familiar structure for anyone who's worked in a shadcn codebase. Nothing here knows about the domain (plants, orgs, sales) or the backend.
2. **`components/form/`** — the design system's form layout wrappers (`FormSection`, `FormActions`) that compose `ui/` primitives per `docs/design/02-component-library.md`.
3. **`components/`** (root) — shared cross-domain feedback components (`ErrorState` so far; `EmptyState` lands when the first list view needs it in 7D+).
4. **Domain components** (not yet built) — land per-module starting in 7C, composed from layers 1–3 plus `lib/api`/`lib/auth`/`store/`.

## Primitives built in 7A

Button, Card, Input, Textarea, Label, Badge, Skeleton, Separator, Dialog, DropdownMenu, Tabs, Select, Tooltip, Popover, Avatar, Checkbox, Switch, RadioGroup, Progress, Alert, Table, Spinner, Sonner-based Toaster, and the RHF-bound Form primitives (`Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`).

Not yet built (deferred to the module that first needs them, per the "build module-by-module" instruction rather than speculatively now): `Sheet` (slide-over — Radix has no native primitive, built on `Dialog` when 7C's mobile nav needs it), `Combobox`/typeahead (SpeciesSelector/BranchSelector/etc. in 7E–7J), `PhotoUpload`/`CameraCapture` (7G), `QuantityStepper` (7I/7J), domain chart wrappers (7D/7N).

## Accessibility built into the primitives (not bolted on later)

- Every interactive primitive uses its Radix behavior primitive (focus trap, `aria-expanded`, `role`, keyboard nav) rather than a hand-rolled div — this was the point of building on Radix instead of raw HTML.
- `Form`'s `FormControl`/`FormLabel`/`FormMessage` wire `htmlFor`/`id`/`aria-describedby`/`aria-invalid` automatically from RHF's field state (see `components/ui/form.tsx`) — a consuming form never has to manage that wiring by hand, which is exactly the "Label programmatically associated via for/id; error messages linked via aria-describedby" requirement.
- `globals.css`'s `prefers-reduced-motion` block flattens animation/transition durations globally, with a scoped exception for `[role="status"]` (loading spinners) — reduced-motion targets vestibular-triggering motion, not "is something still loading," so freezing a spinner would make loading state ambiguous rather than accessible.

## Toast, Error, and Loading conventions

- **Toast**: `lib/toast.ts` wraps `sonner` with `success`/`error`/`info`/`withUndo` plus `apiError(error)`, which turns any `ApiError` into the plain-language copy NFR-6.2 requires (never a raw stack trace) and never auto-dismisses an undo toast. Mounted once in `app/layout.tsx`.
- **ErrorState** (`components/error-state.tsx`): `full-page` (route-level failure, used by `app/error.tsx`), `section` (default — one widget failed, rest of the page still usable), `ai-module` (NFR-3.3's "AI predictions temporarily unavailable" pattern — everything else keeps working).
- **Loading**: `app/loading.tsx` is the generic Suspense fallback; `components/ui/skeleton.tsx` is the shape-matching primitive feature routes compose into their own `loading.tsx` once they have a known final layout (a table skeleton for a list route, etc. — per the design doc's "shape/size matching the content it precedes").
- **Route-level error boundaries**: `app/error.tsx` (catches errors within the root layout's children) and `app/global-error.tsx` (catches errors in the root layout itself — has to render its own bare `<html>/<body>` since the thing that broke might be a provider).

## Form composition

`FormSection` (title/description, optional `collapsible` with `aria-expanded`) and `FormActions` (primary submit + optional cancel; `sticky` turns it into a bottom-anchored bar on mobile for long forms) are layout wrappers around the RHF-bound `Form` primitives. `lib/forms/use-api-form-errors.ts` is the bridge from a failed mutation back onto the form: a 422's `ApiError.fieldErrors` (flattened from the backend's real `RequestValidationError.errors()` shape — see `lib/api/error.ts`) gets mapped onto `form.setError` field-by-field; anything else (401/403/409/500/…) falls back to `toast.apiError()` instead of inventing a phantom field error.

A concrete domain form (login, plant record, etc.) is expected to look like:

```tsx
const form = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });
const handleApiError = useApiFormErrors(form.setError);

<Form {...form}>
  <form onSubmit={form.handleSubmit(onSubmit, () => {})}>
    <FormField control={form.control} name="email" render={({ field }) => (
      <FormItem>
        <FormLabel>Email</FormLabel>
        <FormControl><Input type="email" {...field} /></FormControl>
        <FormMessage />
      </FormItem>
    )} />
    <FormActions primaryLabel="Log in" submitting={mutation.isPending} />
  </form>
</Form>
```

with the mutation's `onError: handleApiError`. This pattern is documented here so 7B's actual login form doesn't have to invent it.
