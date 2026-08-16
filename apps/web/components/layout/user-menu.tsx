"use client";

import { useRouter } from "next/navigation";
import { LogOut, Settings, UserRound } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useLogoutMutation } from "@/lib/auth/mutations";
import { useSession } from "@/lib/auth/use-session";

function initialsFor(fullName: string | undefined): string {
  if (!fullName) return "?";
  return fullName
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/**
 * Avatar-triggered dropdown carrying identity, settings access, and
 * logout -- the top-nav equivalent of the account/session controls 7B
 * built inline into `AppHeader`. `AppHeader` itself is retired by this
 * phase's `AppShell` (see components/layout/app-shell.tsx); this
 * component absorbs its permission-aware "Admin" badge example and its
 * logout handling verbatim.
 */
export function UserMenu() {
  const router = useRouter();
  const { user, isResolving } = useSession();
  const logoutMutation = useLogoutMutation();

  if (isResolving || !user) {
    return <Skeleton className="size-8 rounded-full" />;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Account menu for ${user.full_name}`}
        >
          <Avatar className="size-8">
            <AvatarFallback>{initialsFor(user.full_name)}</AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="flex flex-col gap-0.5 font-normal">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-foreground">{user.full_name}</span>
            <PermissionGate anyOf={["roles:manage", "employees:write"]}>
              <Badge variant="tone" tone="info">
                Admin
              </Badge>
            </PermissionGate>
          </div>
          <span className="truncate text-caption font-normal text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/account")}>
          <UserRound className="size-4" />
          Account
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/settings")}>
          <Settings className="size-4" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          disabled={logoutMutation.isPending}
          onSelect={(event) => {
            event.preventDefault();
            logoutMutation.mutate(undefined, {
              onSettled: () => router.replace("/login"),
            });
          }}
        >
          <LogOut className="size-4" />
          {logoutMutation.isPending ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
