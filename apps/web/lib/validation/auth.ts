import { z } from "zod";

/**
 * Client-side validation is UX only -- catches obvious mistakes before a
 * round-trip, exactly mirroring the backend's real rules
 * (apps/api/app/schemas/auth.py's `_validate_password_strength`,
 * `_PASSWORD_MIN_LENGTH = 12`) so a form never rejects something the
 * backend would accept or vice versa. The backend re-validates
 * everything regardless -- this doesn't replace that.
 */
export const passwordSchema = z
  .string()
  .min(12, "Password must be at least 12 characters long.")
  .refine((v) => /[A-Z]/.test(v), "Password must contain at least one uppercase letter.")
  .refine((v) => /[a-z]/.test(v), "Password must contain at least one lowercase letter.")
  .refine((v) => /[0-9]/.test(v), "Password must contain at least one digit.");

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

export const requestPasswordResetSchema = z.object({
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
});
export type RequestPasswordResetFormValues = z.infer<typeof requestPasswordResetSchema>;

export const confirmPasswordResetSchema = z
  .object({
    newPassword: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your new password."),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords don't match.",
    path: ["confirmPassword"],
  });
export type ConfirmPasswordResetFormValues = z.infer<typeof confirmPasswordResetSchema>;

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Current password is required."),
    newPassword: passwordSchema,
    confirmPassword: z.string().min(1, "Please confirm your new password."),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords don't match.",
    path: ["confirmPassword"],
  });
export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;
