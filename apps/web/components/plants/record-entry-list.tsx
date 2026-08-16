"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Shared list scaffold for 7G's five immutable record tabs (Growth,
 * Health, Watering, Fertilizer, Environmental) -- every one of them is
 * "a permission-gated 'Record X' button, a real paginated list of
 * immutable entries, loading/empty/error states, per-entry rendering
 * that differs only in which fields it shows." Factored out once here
 * rather than five near-identical Card+Table scaffolds, so a UI fix
 * (e.g. the empty-state copy, pagination controls) only needs to change
 * in one place across all five tabs plus any future record type 7H-7O
 * introduces.
 */
export function RecordEntryList<T extends { id: string }>({
  icon,
  emptyTitle,
  emptyDescription,
  items,
  isLoading,
  isError,
  error,
  onRetry,
  retrying,
  renderItem,
  page,
  totalPages,
  onPageChange,
}: {
  icon: LucideIcon;
  emptyTitle: string;
  emptyDescription: string;
  items: T[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  retrying?: boolean;
  renderItem: (item: T) => React.ReactNode;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorState error={error} onRetry={onRetry} retrying={retrying} />;
  }

  if (items.length === 0) {
    return <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-md border border-border p-3">
            {renderItem(item)}
          </li>
        ))}
      </ul>
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-body-sm text-muted-foreground">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              Previous
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
