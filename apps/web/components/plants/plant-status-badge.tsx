import { Badge } from "@/components/ui/badge";
import type { PlantStatus } from "@/lib/api/plants";

/**
 * Maps the backend's real `PlantStatus` enum (`plants.py`'s state
 * machine: in_production -> ready_for_sale -> under_treatment/sold/
 * deceased) to a tone -- purely presentational, never used to validate a
 * transition client-side (the backend's `POST /plants/{id}/status`
 * enforces the real state machine and returns 409 on an illegal move).
 */
const STATUS_LABEL: Record<PlantStatus, string> = {
  in_production: "In production",
  ready_for_sale: "Ready for sale",
  under_treatment: "Under treatment",
  sold: "Sold",
  deceased: "Deceased",
};

const STATUS_TONE: Record<PlantStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  in_production: "info",
  ready_for_sale: "success",
  under_treatment: "warning",
  sold: "neutral",
  deceased: "danger",
};

export function PlantStatusBadge({ status }: { status: PlantStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}
