import { z } from "zod";

/**
 * Client-side validation for 7L's AI Experience forms -- UX only,
 * mirroring apps/api/app/schemas/ai.py's real constraints
 * (`RunDiseaseDetectionRequest.image_url`: 1-1000 chars;
 * `SendAssistantMessageRequest.content`: 1-4000 chars).
 *
 * Disease scan image submission is a URL-registration form, matching
 * 7G's `uploadPlantImageSchema` precedent (`lib/validation/plants.ts`) --
 * there is no binary file-upload endpoint anywhere in this backend
 * (Module 10's `RunDiseaseDetectionRequest` takes an already-hosted
 * `image_url`, not raw bytes), so this is an honest URL field, not a
 * fake camera-capture UI with a client-side-only preview.
 */

export const runDiseaseDetectionSchema = z.object({
  image_url: z.string().min(1, "An image URL is required.").url("Enter a valid URL.").max(1000),
});
export type RunDiseaseDetectionFormValues = z.infer<typeof runDiseaseDetectionSchema>;

export const sendAssistantMessageSchema = z.object({
  content: z.string().min(1, "Type a message before sending.").max(4000, "Messages are limited to 4000 characters."),
});
export type SendAssistantMessageFormValues = z.infer<typeof sendAssistantMessageSchema>;
