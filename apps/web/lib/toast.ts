import { toast as sonnerToast } from "sonner";

import { isApiError, messageForStatus } from "@/lib/api/error";

/**
 * Thin, opinionated wrapper over sonner's `toast()` so call sites never
 * have to know how to turn an `ApiError` into copy -- `apiError()` is
 * the one function every mutation's `onError` should call. Plain
 * `success`/`info`/`error` pass through for everything else, per
 * docs/design/02-component-library.md's Toast component spec (success/
 * error/info/with-undo variants).
 */
export const toast = {
  success: (message: string, opts?: { description?: string }) =>
    sonnerToast.success(message, opts),

  error: (message: string, opts?: { description?: string }) =>
    sonnerToast.error(message, opts),

  info: (message: string, opts?: { description?: string }) => sonnerToast.info(message, opts),

  /**
   * Never auto-dismisses when an undo action is supplied (design spec:
   * "never auto-dismisses if it contains an undo action the user might
   * still need").
   */
  withUndo: (message: string, onUndo: () => void, opts?: { description?: string }) =>
    sonnerToast(message, {
      description: opts?.description,
      duration: Infinity,
      action: { label: "Undo", onClick: onUndo },
    }),

  /**
   * Maps an ApiError (or any unknown error, defensively) to a toast the
   * way NFR-6.2's "plain language, no raw stack traces" requires. 422
   * validation errors are intentionally *not* surfaced here -- those
   * belong on the specific form fields (see
   * lib/forms/use-api-form-errors.ts), not as a generic toast, so this
   * function shows the field-error case only as a fallback when the
   * caller has no form to attach them to.
   */
  apiError: (error: unknown, opts?: { fallbackMessage?: string }) => {
    if (isApiError(error)) {
      sonnerToast.error(error.message || messageForStatus(error.status), {
        description: error.requestId ? `Reference: ${error.requestId}` : undefined,
      });
      return;
    }
    sonnerToast.error(opts?.fallbackMessage ?? "Something went wrong. Please try again.");
  },
};
