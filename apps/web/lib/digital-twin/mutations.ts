"use client";

import { useMutation } from "@tanstack/react-query";

import * as twinApi from "@/lib/api/digital-twin";

/**
 * `verifyTwinConsistency` is a `GET` on the wire (a read-only diagnostic,
 * see lib/api/digital-twin.ts's docstring) -- modeled as a mutation here
 * anyway, not a `useQuery`, because it's semantically an on-demand
 * *action* ("replay and check now") triggered by a button click, not a
 * cacheable read keyed on stable inputs. Nothing is written server-side;
 * this just matches the UI verb, not the HTTP verb.
 */
export function useVerifyTwinConsistencyMutation(plantId: string) {
  return useMutation({
    mutationFn: () => twinApi.verifyTwinConsistency(plantId),
  });
}
