"use client";

import * as React from "react";
import { Building2, Plus } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BranchFormDialog } from "@/components/organization/branch-form-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useArchiveBranchMutation } from "@/lib/organization/mutations";
import type { BranchResponse } from "@/lib/api/branches";

export function BranchesPanel() {
  const query = useBranchesQuery();
  const archiveMutation = useArchiveBranchMutation();
  const [formOpen, setFormOpen] = React.useState(false);
  const [editingBranch, setEditingBranch] = React.useState<BranchResponse | null>(null);
  const [archivingBranch, setArchivingBranch] = React.useState<BranchResponse | null>(null);

  const branches = query.data ?? [];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Branches</CardTitle>
        <PermissionGate permission="branch:write">
          <Button
            type="button"
            size="sm"
            onClick={() => {
              setEditingBranch(null);
              setFormOpen(true);
            }}
          >
            <Plus className="size-4" aria-hidden="true" />
            New branch
          </Button>
        </PermissionGate>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : branches.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="No branches yet"
            description="Create your organization's first branch to start assigning employees, plants, and inventory."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map((branch) => (
                <TableRow key={branch.id}>
                  <TableCell className="font-medium text-foreground">{branch.name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {branch.city}
                    {branch.region ? `, ${branch.region}` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge tone={branch.status === "active" ? "success" : "neutral"}>{branch.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <PermissionGate permission="branch:write">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingBranch(branch);
                          setFormOpen(true);
                        }}
                      >
                        Edit
                      </Button>
                    </PermissionGate>
                    <PermissionGate permission="branch:delete">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        disabled={branch.status !== "active"}
                        onClick={() => setArchivingBranch(branch)}
                      >
                        Archive
                      </Button>
                    </PermissionGate>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <BranchFormDialog open={formOpen} onOpenChange={setFormOpen} branch={editingBranch} />

      <AlertDialog open={archivingBranch !== null} onOpenChange={(open) => !open && setArchivingBranch(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive {archivingBranch?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This branch will no longer accept new employee assignments, plants, or inventory. This can be reversed by
              your organization&apos;s Owner/Admin if needed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={archiveMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={archiveMutation.isPending}
              onClick={() => {
                if (!archivingBranch) return;
                archiveMutation.mutate(archivingBranch.id, { onSuccess: () => setArchivingBranch(null) });
              }}
            >
              Archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
