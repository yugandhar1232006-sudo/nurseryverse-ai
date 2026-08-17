# 7J — Sales & CRM

## Route Structure

```
app/(app)/sales/page.tsx                  sales:read — 6-tab hub (Quotations, Orders, Sales,
                                                     Returns, Refunds, Reports)
app/(app)/sales/[id]/page.tsx             sales:read — generic sale detail
app/(app)/sales/quotations/[id]/page.tsx  sales:read — quotation detail
app/(app)/sales/orders/[id]/page.tsx      sales:read — order detail
app/(app)/sales/returns/[id]/page.tsx     sales:read — return detail
app/(app)/customers/page.tsx              customers:read — customer list
app/(app)/customers/[id]/page.tsx         customers:read — 7-tab customer detail
```

`/sales` is a 6-tab hub: Quotations, Orders, Sales (completed), Returns, Refunds, Reports.
Each tab has its own list view. Detail routes are split by entity type for deep-linkability.
`/customers` is a separate top-level route with its own 7-tab detail page (Overview, Orders,
Quotations, Returns, Activity, Notes, Passport).

## Architecture

```
lib/api/sales.ts                 Typed wrappers for Module 9 /sales/* routes
lib/api/customers.ts             Typed wrappers for Module 9 /customers/* routes
lib/sales/queries.ts             salesKeys factory + per-endpoint query hooks
lib/sales/mutations.ts           Mutation hooks for sales lifecycle + records
lib/customer/queries.ts          customerKeys factory + per-endpoint query hooks
lib/customer/mutations.ts        Mutation hooks for customer CRUD
lib/validation/sales.ts          Zod schemas for sales forms
lib/validation/customer.ts       Zod schemas for customer forms

components/sales/
  sales-content.tsx              6-tab orchestrator for /sales hub
  quotations-panel.tsx           Quotation list with status filter
  orders-panel.tsx               Order list with status filter
  sales-panel.tsx                Completed sales list
  returns-panel.tsx              Returns list
  refunds-panel.tsx              Refunds list
  reports-panel.tsx              Sales reports
  create-sales-order-dialog.tsx  New order form with line items
  quotation-header.tsx           Quotation identity + status + actions
  sales-order-header.tsx         Order identity + status + actions
  sale-header.tsx                Completed sale identity
  return-header.tsx              Return identity + status + actions
  invoice-panel.tsx              Invoice display (order detail only)
  create-return-dialog.tsx       Return request form
  create-refund-dialog.tsx       Refund processing form
  line-items-field-array.tsx     useFieldArray-driven line item editor
  payment-record-dialog.tsx      Record payment against order/sale

components/customers/
  customers-list.tsx             Paginated customer table with search
  customer-header.tsx            Customer identity + contact info
  create-customer-dialog.tsx     New customer form
  customer-orders-tab.tsx        Customer's order history
  customer-quotations-tab.tsx    Customer's quotation history
  customer-returns-tab.tsx       Customer's return history
  customer-activity-tab.tsx      Activity feed
  customer-notes-tab.tsx         Notes (free text)
  customer-passport-tab.tsx      Linked plant passports
```

## Components

`LineItemsFieldArray` is the first use of react-hook-form's `useFieldArray` in this project.
Each line item has: product name, quantity, unit price, discount, tax rate, and subtotal
(computed). The array supports add/remove rows with real-time subtotal recalculation.

`CreateSalesOrderDialog` builds on `LineItemsFieldArray` with customer selection (lookup from
`/customers`), branch, notes, and optional quotation link. Branch cascades from the logged-in
user's context.

`InvoicePanel` appears only on order detail (`/sales/orders/[id]`), not on the generic sale
detail or quotation pages. It renders invoice line items, tax totals, and payment status.

`CreateReturnDialog` accepts an order reference, return reason, and line-item selection (which
items and quantities to return). `CreateRefundDialog` handles the financial side: refund
amount, method, and reason.

Plant-linked line items (tying a line item to a specific plant instance for tracking) are
deferred -- the data model supports it but no UI form captures it yet.

## Lifecycle Machines

Three distinct state machines govern the sales flow:

**Quotation:**
```
DRAFT -> SENT -> ACCEPTED -> CONVERTED (to Order)
DRAFT/SENT/ACCEPTED -> REJECTED
DRAFT/SENT/ACCEPTED -> EXPIRED
```

**Sales Order:**
```
DRAFT -> CONFIRMED -> PROCESSING -> FULFILLED
DRAFT/CONFIRMED/PROCESSING -> CANCELLED (not after FULFILLED)
```

**Return:**
```
REQUESTED -> APPROVED -> COMPLETED
REQUESTED -> REJECTED
```

All transitions are server-side. The frontend renders only valid transition buttons based on
the current status, matching 7G's pattern: ask the server what transitions are available, don't
compute them client-side.

## API Endpoints

```
Sales (30+ endpoints):
  GET/POST   /sales/quotations                  Quotation list + create
  GET/PUT    /sales/quotations/{id}             Quotation detail + update
  POST       /sales/quotations/{id}/send        Send quotation
  POST       /sales/quotations/{id}/accept      Accept quotation
  POST       /sales/quotations/{id}/reject      Reject quotation

  GET/POST   /sales/orders                      Order list + create
  GET/PUT    /sales/orders/{id}                 Order detail + update
  POST       /sales/orders/{id}/confirm         Confirm order
  POST       /sales/orders/{id}/process         Begin processing
  POST       /sales/orders/{id}/fulfill         Mark fulfilled
  POST       /sales/orders/{id}/cancel          Cancel order

  GET        /sales/sales                       Completed sales list
  GET        /sales/sales/{id}                  Completed sale detail

  GET/POST   /sales/invoices                    Invoice list + create
  GET        /sales/invoices/{id}               Invoice detail

  POST       /sales/payments                    Record payment

  GET/POST   /sales/returns                     Return list + create
  GET        /sales/returns/{id}                Return detail
  POST       /sales/returns/{id}/approve        Approve return
  POST       /sales/returns/{id}/complete       Complete return
  POST       /sales/returns/{id}/reject         Reject return

  GET/POST   /sales/refunds                     Refund list + create
  GET        /sales/refunds/{id}                Refund detail

Customers (18 endpoints):
  GET/POST   /customers                         Customer list + create
  GET/PUT    /customers/{id}                    Customer detail + update
  DELETE     /customers/{id}                    Soft-delete customer
  GET        /customers/{id}/orders             Customer's orders
  GET        /customers/{id}/quotations         Customer's quotations
  GET        /customers/{id}/returns            Customer's returns
  GET        /customers/{id}/activity           Activity feed
  POST       /customers/{id}/notes              Add note
  GET        /customers/{id}/passports          Linked passports
  ... (additional customer sub-resource endpoints)
```

## Query Keys & Mutations

```
salesKeys.all                                       ['sales-module']
salesKeys.quotations(filters?)                      ['sales-module', 'quotations', filters]
salesKeys.quotationDetail(id)                       ['sales-module', 'quotation', id]
salesKeys.orders(filters?)                          ['sales-module', 'orders', filters]
salesKeys.orderDetail(id)                           ['sales-module', 'order', id]
salesKeys.sales(filters?)                           ['sales-module', 'sales', filters]
salesKeys.saleDetail(id)                            ['sales-module', 'sale', id]
salesKeys.returns(filters?)                         ['sales-module', 'returns', filters]
salesKeys.returnDetail(id)                          ['sales-module', 'return', id]
salesKeys.refunds(filters?)                         ['sales-module', 'refunds', filters]
salesKeys.refundDetail(id)                          ['sales-module', 'refund', id]
salesKeys.invoices(filters?)                        ['sales-module', 'invoices', filters]
salesKeys.invoiceDetail(id)                         ['sales-module', 'invoice', id]

customerKeys.all                                    ['customers']
customerKeys.list(filters?)                         ['customers', 'list', filters]
customerKeys.detail(id)                             ['customers', 'detail', id]
customerKeys.orders(id)                             ['customers', 'orders', id]
customerKeys.quotations(id)                         ['customers', 'quotations', id]
customerKeys.returns(id)                            ['customers', 'returns', id]
customerKeys.activity(id)                           ['customers', 'activity', id]
```

Sales mutations: `useCreateQuotationMutation`, `useSendQuotationMutation`,
`useAcceptQuotationMutation`, `useRejectQuotationMutation`, `useCreateOrderMutation`,
`useConfirmOrderMutation`, `useProcessOrderMutation`, `useFulfillOrderMutation`,
`useCancelOrderMutation`, `useRecordPaymentMutation`, `useCreateReturnMutation`,
`useApproveReturnMutation`, `useCompleteReturnMutation`, `useRejectReturnMutation`,
`useCreateRefundMutation`.

Customer mutations: `useCreateCustomerMutation`, `useUpdateCustomerMutation`,
`useDeleteCustomerMutation`, `useAddCustomerNoteMutation`.

Status transitions invalidate both the specific detail key and the parent list key to keep
counts and filters current.

## Validation

```
createQuotationSchema       customer_id, branch_id, line_items[], valid_until?, notes?
createSalesOrderSchema      customer_id, branch_id, line_items[], quotation_id?, notes?
recordPaymentSchema         order_id, amount, payment_method, reference?, notes?
createReturnSchema          order_id, items[{order_item_id, quantity, reason}], notes?
processRefundSchema         return_id, amount, refund_method, reason, notes?
createCustomerSchema        name, email?, phone?, address?, type (individual/business)
updateCustomerSchema        name?, email?, phone?, address?
```

7 additional customer schemas for address management, contact records, and notes. All
line-item schemas share a common `LineItemInput` type: `product_name, quantity, unit_price,
discount?, tax_rate?`.

## Permission Gates

```
sales:read          Route-level gate on /sales and all /sales/* routes
                    Customer list + detail visibility
sales:write         Create quotations, orders, returns; record payments; transitions
sales:void          Void invoices, cancel orders (destructive actions)
invoices:read       Invoice tab visibility on order detail
invoices:write      Generate/create invoices
customers:read      Route-level gate on /customers and /customers/*
customers:write     Create/update/delete customers
```

`sales:write` covers most write actions. `sales:void` is a separate, more restrictive
permission for destructive financial actions (voiding an already-issued invoice, cancelling
an order in PROCESSING or later). This separation means a Branch Manager can create orders
but cannot void invoices -- only Owner/Org Admin can.

## Patterns

- **First use of `useFieldArray`.** `LineItemsFieldArray` uses react-hook-form's `useFieldArray`
  for dynamic line item management. This is the project's first instance; the pattern will be
  reused in purchase orders (if/when implemented) and any other multi-line-item forms.
- **Money as strings.** All monetary values pass through the API as strings (e.g., `"1250.00"`),
  not numbers. This avoids floating-point precision issues. The frontend parses to `number` only
  for display formatting and chart rendering.
- **Branch cascading.** Order/quotation forms cascade branch selection from the user's current
  context, matching 7E's pattern for branch-scoped selectors.
- **InvoicePanel only on order detail.** Invoices are tied to orders, not to generic sales or
  quotations. The invoice panel only renders on `/sales/orders/[id]`.
- **Plant-linked lines deferred.** The data model supports tying a line item to a specific plant
  instance (for tracking provenance), but no form UI captures this yet. The backend accepts the
  field; the frontend simply doesn't send it.
- **No payment gateway integration.** Payments are recorded manually (amount, method, reference).
  There is no Stripe/PayPal/etc. integration. Payment recording is an administrative action,
  not a checkout flow.

## Known Limitations

- No payment gateway integration. Payments are manual records only.
- Plant-linked line items (product provenance tracking) have backend support but no UI.
- Customer soft-delete has no undo mechanism. Once deleted, a customer can only be re-created.
- The Reports tab on `/sales` is a placeholder for Module 7N's report-generation scope.
  Sales-specific report endpoints exist but the tab currently shows summary statistics only,
  not full report generation/export.
- Quotation expiry is server-timed. The frontend shows `valid_until` but does not countdown or
  auto-transition -- the server handles expiration on its own schedule.

## Test Coverage

- **Playwright** (`e2e/sales-crm.spec.ts`, 3 tests): create a customer and see them in the
  list; create a quotation, convert to order, record payment, verify completed sale exists;
  create a return request and approve it. All use real org creation via `POST /orgs`. Written
  and collected; **not execution-verified** in this sandbox.
- **Vitest/RTL**:
  - `components/sales/__tests__/sales.test.tsx` (8 tests): quotation list rendering, order
    status transitions, line item add/remove via useFieldArray, invoice panel rendering on
    order detail, payment record form, return dialog validation, refund form, permission gating
    on void actions
  - `components/customers/__tests__/customers.test.tsx` (7 tests): customer list with search,
    create customer form, customer detail tab navigation, order history tab, add note, delete
    confirmation dialog, permission gating on customer write
- **Full regression**: all prior suites plus the new 15 tests pass. `npx tsc --noEmit` clean.
  `npx eslint .` clean.
