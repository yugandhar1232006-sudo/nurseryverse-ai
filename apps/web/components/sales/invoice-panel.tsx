"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useInvoiceDetailQuery, useInvoiceItemsQuery, useInvoicePaymentsQuery } from "@/lib/sales/queries";
import { useRecordPaymentMutation } from "@/lib/sales/mutations";
import { recordPaymentSchema, type RecordPaymentFormValues } from "@/lib/validation/sales";
import type { InvoiceStatus } from "@/lib/api/sales";

const STATUS_TONE: Record<InvoiceStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  draft: "neutral",
  sent: "info",
  paid: "success",
  overdue: "warning",
  void: "danger",
};

const DEFAULT_VALUES: RecordPaymentFormValues = { amount: "", method: "cash", reference: "" };

/**
 * `Invoice.amount_paid`/`payment_status` are derived live (sum of
 * Payments vs. total_amount), never stored columns -- this panel always
 * reads them straight off `GET /invoices/{id}`'s response rather than
 * computing a client-side running total, so a page reload or a payment
 * recorded from elsewhere is always reflected correctly.
 */
export function InvoicePanel({ invoiceId }: { invoiceId: string }) {
  const invoiceQuery = useInvoiceDetailQuery(invoiceId);
  const itemsQuery = useInvoiceItemsQuery(invoiceId);
  const paymentsQuery = useInvoicePaymentsQuery(invoiceId);
  const [payOpen, setPayOpen] = React.useState(false);

  if (invoiceQuery.isLoading) return <Skeleton className="h-48 w-full" />;
  if (invoiceQuery.isError) {
    return <ErrorState error={invoiceQuery.error} onRetry={() => invoiceQuery.refetch()} retrying={invoiceQuery.isFetching} />;
  }
  const invoice = invoiceQuery.data;
  if (!invoice) return null;

  const remaining = Number(invoice.total_amount) - Number(invoice.amount_paid);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 className="text-h4 font-semibold text-foreground">Invoice {invoice.invoice_number}</h2>
            <p className="text-body-sm text-muted-foreground">Due: {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : "—"}</p>
          </div>
          <div className="flex gap-2">
            <Badge tone={STATUS_TONE[invoice.status]} className="capitalize">
              {invoice.status}
            </Badge>
            <Badge tone="neutral" className="capitalize">
              {invoice.payment_status.replace("_", " ")}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
          <span>
            Total: <span className="text-foreground">₹{Number(invoice.total_amount).toFixed(2)}</span>
          </span>
          <span>
            Paid: <span className="text-foreground">₹{Number(invoice.amount_paid).toFixed(2)}</span>
          </span>
          <span>
            Remaining: <span className="text-foreground">₹{remaining.toFixed(2)}</span>
          </span>
        </div>
        {invoice.status !== "void" && remaining > 0 && (
          <PermissionGate permission="invoices:write">
            <div>
              <Button type="button" size="sm" onClick={() => setPayOpen(true)}>
                Record payment
              </Button>
            </div>
          </PermissionGate>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-3 text-body font-semibold text-foreground">Line items</h3>
        {itemsQuery.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Unit price</TableHead>
                <TableHead className="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(itemsQuery.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-foreground">{item.description}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right">₹{Number(item.unit_price).toFixed(2)}</TableCell>
                  <TableCell className="text-right font-medium text-foreground">₹{Number(item.line_total).toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-3 text-body font-semibold text-foreground">Payment history</h3>
        {paymentsQuery.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : !paymentsQuery.data || paymentsQuery.data.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No payments recorded yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {paymentsQuery.data.map((payment) => (
              <li key={payment.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-body-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground">₹{Number(payment.amount).toFixed(2)}</span>
                  <Badge tone="neutral" className="capitalize">
                    {payment.method}
                  </Badge>
                  {payment.reference && <span className="text-muted-foreground">Ref: {payment.reference}</span>}
                </div>
                <span className="text-caption text-muted-foreground">{new Date(payment.received_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <RecordPaymentDialog invoiceId={invoiceId} open={payOpen} onOpenChange={setPayOpen} />
    </div>
  );
}

function RecordPaymentDialog({ invoiceId, open, onOpenChange }: { invoiceId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const mutation = useRecordPaymentMutation(invoiceId);
  const form = useForm<RecordPaymentFormValues>({ resolver: zodResolver(recordPaymentSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: RecordPaymentFormValues) {
    mutation.mutate(
      { amount: Number(values.amount), method: values.method, reference: values.reference || null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Record payment</DialogTitle>
          <DialogDescription>Records a full or partial payment against this invoice. A real 409 is returned if the invoice is void.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Amount</FormLabel>
                  <FormControl>
                    <Input inputMode="decimal" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="method"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Method</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="upi">UPI</SelectItem>
                      <SelectItem value="card">Card</SelectItem>
                      <SelectItem value="bank_transfer">Bank transfer</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reference"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reference (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Record payment
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
