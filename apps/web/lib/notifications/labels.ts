import type { NotificationCategory, NotificationChannel } from "@/lib/api/notifications";

/**
 * Human-readable labels for the real 22-value `NotificationCategory` enum
 * and the 4-value `NotificationChannel` enum (both from
 * `apps/api/app/db/enums.py`). Shared between 7M's own-preferences panel
 * and 7O's notification-template-authoring panel, which are the only two
 * screens in the app that need to render every possible category/channel
 * rather than just the ones present on a given record.
 */
export const CATEGORY_LABELS: Record<NotificationCategory, string> = {
  disease_confirmed: "Disease confirmed",
  watering_overdue: "Watering overdue",
  low_stock: "Low stock",
  ai_prediction_ready: "AI prediction ready",
  invoice_overdue: "Invoice overdue",
  employee_invite: "Employee invite",
  plant_transferred: "Plant transferred",
  purchase_order_received: "Purchase order received",
  password_reset: "Password reset",
  email_verification: "Email verification",
  plant_registered: "Plant registered",
  plant_ready_for_sale: "Plant ready for sale",
  plant_under_treatment: "Plant under treatment",
  plant_sold: "Plant sold",
  reservation_created: "Reservation created",
  reservation_expiring: "Reservation expiring",
  invoice_generated: "Invoice generated",
  payment_received: "Payment received",
  inventory_transfer: "Inventory transfer",
  system_alert: "System alert",
  ai_recommendation_ready: "AI recommendation ready",
  report_ready: "Report ready",
};

export const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as NotificationCategory[];

export const CHANNEL_LABELS: Record<NotificationChannel, string> = {
  in_app: "In-app",
  email: "Email",
  sms: "SMS",
  push: "Push",
};

export const ALL_CHANNELS = Object.keys(CHANNEL_LABELS) as NotificationChannel[];
