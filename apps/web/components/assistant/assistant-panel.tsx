"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Send, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormMessage } from "@/components/ui/form";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useAssistantConversationQuery } from "@/lib/ai-assistant/queries";
import { useConfirmAssistantActionMutation, useSendAssistantMessageMutation } from "@/lib/ai-assistant/mutations";
import { sendAssistantMessageSchema, type SendAssistantMessageFormValues } from "@/lib/validation/ai";
import { useAssistantStore } from "@/store/assistant-store";
import { useUiStore } from "@/store/ui-store";
import type { AssistantMessageResponse, ProposedAction } from "@/lib/api/ai-assistant";
import { cn } from "@/lib/utils";

const SEND_DEFAULTS: SendAssistantMessageFormValues = { content: "" };

function ProposedActionCard({ message, conversationId }: { message: AssistantMessageResponse; conversationId: string }) {
  const confirmMutation = useConfirmAssistantActionMutation(conversationId);
  const action = message.proposed_action as unknown as ProposedAction | null;
  const isPending = message.action_status === "pending_confirmation";

  if (!action) return null;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-ai-accent-200 bg-ai-accent-50 p-3">
      <div className="flex items-center gap-2">
        <Badge tone="ai">Proposed action</Badge>
        {message.action_status === "confirmed" && <Badge tone="success">Confirmed</Badge>}
        {message.action_status === "cancelled" && <Badge tone="neutral">Cancelled</Badge>}
      </div>
      <p className="text-body-sm text-foreground">{action.summary}</p>
      {isPending && (
        <PermissionGate
          permission="ai_assistant:confirm_write"
          fallback={<p className="text-caption text-muted-foreground">You don&apos;t have permission to confirm this action.</p>}
        >
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={confirmMutation.isPending}
              onClick={() => confirmMutation.mutate({ messageId: message.id, confirm: true })}
            >
              {confirmMutation.isPending && <Spinner className="text-current" />}
              Confirm
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={confirmMutation.isPending}
              onClick={() => confirmMutation.mutate({ messageId: message.id, confirm: false })}
            >
              Cancel
            </Button>
          </div>
        </PermissionGate>
      )}
    </div>
  );
}

function MessageBubble({ message, conversationId }: { message: AssistantMessageResponse; conversationId: string }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex flex-col gap-2", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-md px-3 py-2 text-body-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
        )}
      >
        {message.content}
      </div>
      {!isUser && message.proposed_action && (
        <div className="w-[85%]">
          <ProposedActionCard message={message} conversationId={conversationId} />
        </div>
      )}
    </div>
  );
}

/**
 * FR-9.1-9.4 -- the AI Assistant's persistent header overlay (per
 * nav-config.ts's docstring: "Notifications and AI Assistant are
 * deliberately NOT [sidebar destinations] ... they're persistent header
 * overlays"). Same `Sheet` + shared `useUiStore` open-state pattern as
 * `NotificationCenter` (components/layout/notification-center.tsx),
 * triggered from `TopNav`.
 *
 * Handles the real "no conversation list route" gap documented in
 * lib/api/ai-assistant.ts: if the persisted `conversationId` 404s (stale,
 * deleted, or belongs to a different account sharing this browser), that
 * id is cleared and the panel falls back to its real empty "start a
 * conversation" state rather than surfacing a raw error for state the
 * user never directly caused.
 */
export function AssistantPanel() {
  const open = useUiStore((state) => state.assistantPanelOpen);
  const setOpen = useUiStore((state) => state.setAssistantPanelOpen);

  const conversationId = useAssistantStore((state) => state.conversationId);
  const setConversationId = useAssistantStore((state) => state.setConversationId);

  const conversationQuery = useAssistantConversationQuery(conversationId);
  const sendMutation = useSendAssistantMessageMutation();

  React.useEffect(() => {
    if (conversationQuery.isError && conversationId !== null) {
      setConversationId(null);
    }
  }, [conversationQuery.isError, conversationId, setConversationId]);

  const form = useForm<SendAssistantMessageFormValues>({ resolver: zodResolver(sendAssistantMessageSchema), defaultValues: SEND_DEFAULTS });

  function onSubmit(values: SendAssistantMessageFormValues) {
    sendMutation.mutate(
      { conversationId, content: values.content },
      { onSuccess: () => form.reset(SEND_DEFAULTS) },
    );
  }

  const messages = conversationQuery.data?.messages ?? [];
  const showEmptyState = conversationId === null && !sendMutation.isPending;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="ghost" size="icon" aria-label="AI Assistant">
          <Sparkles className="size-5" aria-hidden="true" />
        </Button>
      </SheetTrigger>

      <SheetContent side="right" className="flex w-full max-w-sm flex-col p-0" aria-describedby={undefined}>
        <SheetHeader className="border-b border-border">
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-ai-accent-700" aria-hidden="true" />
            AI Assistant
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {conversationId !== null && conversationQuery.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : conversationQuery.isError && conversationId !== null ? (
            <ErrorState error={conversationQuery.error} onRetry={() => conversationQuery.refetch()} retrying={conversationQuery.isFetching} />
          ) : showEmptyState ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <Sparkles className="size-8 text-muted-foreground" aria-hidden="true" />
              <p className="text-body-sm font-medium text-foreground">Ask me anything about your nursery</p>
              <p className="text-caption text-muted-foreground">
                I can answer questions about your plants, inventory, and sales, scoped to your role&apos;s real permissions.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} conversationId={conversationId as string} />
              ))}
              {sendMutation.isPending && (
                <div className="flex items-center gap-2 text-caption text-muted-foreground">
                  <Spinner className="text-current" /> Thinking…
                </div>
              )}
            </div>
          )}
        </div>

        <PermissionGate
          permission="ai_assistant:use"
          fallback={<p className="border-t border-border p-4 text-caption text-muted-foreground">You don&apos;t have permission to use the AI Assistant.</p>}
        >
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex items-end gap-2 border-t border-border p-3" noValidate>
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl>
                      <Textarea
                        {...field}
                        rows={2}
                        placeholder="Type a message…"
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            form.handleSubmit(onSubmit)();
                          }
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" size="icon" disabled={sendMutation.isPending} aria-label="Send message" aria-busy={sendMutation.isPending}>
                {sendMutation.isPending ? <Spinner className="text-current" /> : <Send className="size-4" aria-hidden="true" />}
              </Button>
            </form>
          </Form>
        </PermissionGate>
      </SheetContent>
    </Sheet>
  );
}
