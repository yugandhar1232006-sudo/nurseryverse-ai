"use client";

import { Plus, Trash2 } from "lucide-react";
import { useFieldArray, type Control, type FieldValues, type Path } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useInventoryListQuery } from "@/lib/inventory/queries";

/**
 * Repeatable inventory-linked line-item builder, shared by
 * `CreateQuotationDialog` and `CreateSalesOrderDialog`. Every line built
 * here sets `LineItemRequest.inventory_id` (bulk-stock) and leaves
 * `plant_id` unset -- see docs/frontend/14-sales-crm.md's Known
 * Limitations for why plant-linked lines aren't built through this UI in
 * this initial phase.
 *
 * Real `useFieldArray` usage is new to this codebase as of 7J -- no prior
 * phase needed a repeatable form section.
 */
export function LineItemsFieldArray<TFieldValues extends FieldValues>({
  control,
  branchId,
  name,
}: {
  control: Control<TFieldValues>;
  branchId: string;
  name: Path<TFieldValues>;
}) {
  const { fields, append, remove } = useFieldArray({ control, name: name as never });
  const inventoryQuery = useInventoryListQuery({ branch_id: branchId || undefined, page: 1, page_size: 100 });
  const inventoryItems = inventoryQuery.data?.items ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        {/*
          This heading labels the whole repeatable section, not a single
          RHF-bound field -- `FormLabel` requires a `<FormField>`+
          `<FormItem>` ancestor (it calls `useFormField()` internally,
          which throws "must be used within <FormField>" otherwise). That
          was a real defect here: `FormLabel` was used bare, so opening
          either `CreateQuotationDialog` or `CreateSalesOrderDialog` threw
          at render time -- caught by the first Vitest test that actually
          opened one of these dialogs, not by `tsc`/`eslint`/`next build`,
          none of which execute component render logic. Plain `Label` is
          the correct primitive for a section heading like this.
        */}
        <Label>Line items</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!branchId}
          onClick={() => append({ inventory_id: "", description: "", quantity: "1", unit_price: "0", discount_amount: "" } as never)}
        >
          <Plus className="size-4" aria-hidden="true" />
          Add line
        </Button>
      </div>

      {!branchId ? (
        <p className="text-body-sm text-muted-foreground">Select a branch first.</p>
      ) : fields.length === 0 ? (
        <p className="text-body-sm text-muted-foreground">No line items yet -- add at least one.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {fields.map((field, index) => (
            <div key={field.id} className="grid grid-cols-1 gap-2 rounded-md border border-border p-3 tablet:grid-cols-[2fr_1fr_1fr_1fr_auto] tablet:items-end">
              <FormField
                control={control}
                name={`${name}.${index}.inventory_id` as Path<TFieldValues>}
                render={({ field: itemField }) => (
                  <FormItem>
                    <FormLabel className="tablet:sr-only">Inventory line</FormLabel>
                    {inventoryQuery.isLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Select value={itemField.value as string} onValueChange={itemField.onChange}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select inventory" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {inventoryItems.map((item) => (
                            <SelectItem key={item.id} value={item.id}>
                              {item.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={control}
                name={`${name}.${index}.quantity` as Path<TFieldValues>}
                render={({ field: itemField }) => (
                  <FormItem>
                    <FormLabel className="tablet:sr-only">Quantity</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" placeholder="Qty" {...itemField} value={itemField.value as string} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={control}
                name={`${name}.${index}.unit_price` as Path<TFieldValues>}
                render={({ field: itemField }) => (
                  <FormItem>
                    <FormLabel className="tablet:sr-only">Unit price</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="Unit price" {...itemField} value={itemField.value as string} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={control}
                name={`${name}.${index}.discount_amount` as Path<TFieldValues>}
                render={({ field: itemField }) => (
                  <FormItem>
                    <FormLabel className="tablet:sr-only">Discount</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="Discount" {...itemField} value={itemField.value as string} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="button" variant="ghost" size="sm" aria-label="Remove line" onClick={() => remove(index)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
