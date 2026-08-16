"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as salesApi from "@/lib/api/sales";
import { salesKeys } from "@/lib/sales/queries";
import { toast } from "@/lib/toast";

// ------------------------------------------------------------------
// Quotations
// ------------------------------------------------------------------

export function useCreateQuotationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesApi.createQuotation,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "quotation-list"] });
      toast.success("Quotation created");
    },
  });
}

export function useChangeQuotationStatusMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: salesApi.QuotationStatusChangeRequest) => salesApi.changeQuotationStatus(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.quotationDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "quotation-list"] });
      toast.success("Quotation status updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useConvertQuotationMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => salesApi.convertQuotation(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.quotationDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "quotation-list"] });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "order-list"] });
      toast.success("Quotation converted to a sales order");
    },
    onError: (error) => toast.apiError(error),
  });
}

// ------------------------------------------------------------------
// Sales Orders
// ------------------------------------------------------------------

export function useCreateSalesOrderMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesApi.createSalesOrder,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "order-list"] });
      toast.success("Sales order created");
    },
  });
}

/** A real `insufficient_stock` 409 is possible here -- same discriminated-context `ConflictError` 7I's dialogs handle. */
export function useConfirmSalesOrderMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => salesApi.confirmSalesOrder(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.orderDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "order-list"] });
      toast.success("Order confirmed -- stock reserved");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCancelSalesOrderMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: salesApi.CancelOrderRequest) => salesApi.cancelSalesOrder(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.orderDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "order-list"] });
      toast.success("Order cancelled");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** Idempotent server-side -- a duplicate click while a prior checkout is still in flight is safe, but the button is still disabled during `isPending` to avoid firing a redundant request. */
export function useCheckoutSalesOrderMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => salesApi.checkoutSalesOrder(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.orderDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "order-list"] });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "sale-list"] });
      toast.success("Checkout complete -- sale and invoice generated");
    },
    onError: (error) => toast.apiError(error),
  });
}

// ------------------------------------------------------------------
// Invoices + Payments
// ------------------------------------------------------------------

/** A real 409 (`context.reason === "invoice_void"`) is possible if the invoice was voided. */
export function useRecordPaymentMutation(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: salesApi.RecordPaymentRequest) => salesApi.recordPayment(invoiceId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.invoiceDetail(invoiceId) });
      void queryClient.invalidateQueries({ queryKey: salesKeys.invoicePayments(invoiceId) });
      toast.success("Payment recorded");
    },
    onError: (error) => toast.apiError(error),
  });
}

// ------------------------------------------------------------------
// Returns
// ------------------------------------------------------------------

/**
 * `CreateReturnDialog` manages its own selection state rather than an RHF
 * form (see that file's docstring), so it never calls
 * `useApiFormErrors`'s `handleApiError` -- this mutation's own `onError`
 * is therefore the only place a 422 (e.g. a requested quantity exceeding
 * the sale item's own quantity) gets surfaced to the user at all.
 */
export function useCreateReturnMutation(saleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: salesApi.CreateReturnRequest) => salesApi.createReturn(saleId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "return-list"] });
      toast.success("Return requested");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useApproveReturnMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => salesApi.approveReturn(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.returnDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "return-list"] });
      toast.success("Return approved");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useRejectReturnMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: salesApi.RejectReturnRequest) => salesApi.rejectReturn(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.returnDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "return-list"] });
      toast.success("Return rejected");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCompleteReturnMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => salesApi.completeReturn(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: salesKeys.returnDetail(id) });
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "return-list"] });
      toast.success("Return completed -- stock restocked");
    },
    onError: (error) => toast.apiError(error),
  });
}

// ------------------------------------------------------------------
// Refunds
// ------------------------------------------------------------------

export function useProcessRefundMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesApi.processRefund,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...salesKeys.all, "refund-list"] });
      toast.success("Refund processed");
    },
  });
}
