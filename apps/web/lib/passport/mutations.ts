"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as passportApi from "@/lib/api/passport";
import { passportKeys } from "@/lib/passport/queries";
import { toast } from "@/lib/toast";

/** Append-only -- always creates a new version, never overwrites the previous one. */
export function useGeneratePassportMutation(plantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: passportApi.GeneratePassportRequest) => passportApi.generatePassport(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: passportKeys.plantList(plantId) });
      toast.success("Passport generated");
    },
    onError: (error) => toast.apiError(error),
  });
}
