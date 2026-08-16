import { useCallback } from "react";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { isApiError } from "@/lib/api/error";
import { toast } from "@/lib/toast";

/**
 * Bridges the real backend's 422 response (see lib/api/error.ts's
 * ApiError.fieldErrors, flattened from FastAPI's own
 * RequestValidationError.errors() shape) into react-hook-form's
 * `setError`, so a submit handler's `onError` can just do:
 *
 *   onError: (error) => handleApiFormError(error, form.setError)
 *
 * and have the exact fields the backend rejected show their exact
 * message inline (via FormMessage), with everything else (401/403/409/
 * 500/etc.) falling back to a toast instead of a phantom field error.
 */
export function useApiFormErrors<TFieldValues extends FieldValues>(
  setError: UseFormSetError<TFieldValues>,
) {
  return useCallback(
    (error: unknown) => {
      if (isApiError(error) && error.status === 422 && error.fieldErrors) {
        let matchedAny = false;
        for (const [field, messages] of Object.entries(error.fieldErrors)) {
          setError(field as Path<TFieldValues>, { type: "server", message: messages.join(" ") });
          matchedAny = true;
        }
        if (matchedAny) return;
      }
      toast.apiError(error);
    },
    [setError],
  );
}
