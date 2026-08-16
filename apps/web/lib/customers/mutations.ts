"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as customersApi from "@/lib/api/customers";
import { customerKeys } from "@/lib/customers/queries";
import { toast } from "@/lib/toast";

export function useCreateCustomerMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: customersApi.createCustomer,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...customerKeys.all, "list"] });
      toast.success("Customer created");
    },
  });
}

export function useUpdateCustomerMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.UpdateCustomerRequest) => customersApi.updateCustomer(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: [...customerKeys.all, "list"] });
      toast.success("Customer updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useAddCustomerContactMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.CreateCustomerContactRequest) => customersApi.addCustomerContact(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.contacts(id) });
      toast.success("Contact added");
    },
  });
}

export function useAddCustomerAddressMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.CreateCustomerAddressRequest) => customersApi.addCustomerAddress(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.addresses(id) });
      toast.success("Address added");
    },
  });
}

export function useAddCustomerTagMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.AddCustomerTagRequest) => customersApi.addCustomerTag(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.tags(id) });
      toast.success("Tag added");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useRemoveCustomerTagMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tag: string) => customersApi.removeCustomerTag(id, tag),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: customerKeys.tags(id) });
      toast.success("Tag removed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useAddCustomerNoteMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.CreateCustomerNoteRequest) => customersApi.addCustomerNote(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...customerKeys.all, "notes", id] });
      toast.success("Note added");
    },
  });
}

export function useLogCustomerCommunicationMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: customersApi.LogCommunicationRequest) => customersApi.logCustomerCommunication(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...customerKeys.all, "communications", id] });
      toast.success("Communication logged");
    },
  });
}
