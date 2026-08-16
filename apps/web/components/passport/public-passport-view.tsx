"use client";

import type { ElementType, ReactNode } from "react";
import { BadgeCheck, Droplet, Leaf, Sprout } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { usePublicPassportQuery, useQrScanQuery } from "@/lib/public-passport/queries";
import type { PassportContent } from "@/lib/api/public-passport";

/**
 * The customer-facing certificate + live care view for one Passport
 * token. Two independent reads, deliberately: `usePublicPassportQuery`
 * (the frozen, factual `content_snapshot` -- species/provenance/health-at-
 * generation-time/purchase info, per docs/ux/15-plant-passport-workflow.md's
 * "factual, point-in-time document, not a live dashboard, no AI
 * predictions") renders the certificate itself, and `useQrScanQuery` (the
 * separate "what does this plant need right now" live read, which is
 * also what records the scan analytics event) renders a distinct "Current
 * care" section below it. A missing/expired/tampered token fails both the
 * same generic way -- the backend returns an identical 404 regardless of
 * which of the three failure modes occurred, by design, so this shows one
 * unified not-found state rather than trying to distinguish them.
 */
export function PublicPassportView({ token }: { token: string }) {
  const passportQuery = usePublicPassportQuery(token);
  const scanQuery = useQrScanQuery(token);

  if (passportQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (passportQuery.isError) {
    return (
      <ErrorState
        variant="full-page"
        error={passportQuery.error}
        message="This passport link is invalid or has expired. Double-check the link, or ask the nursery for a fresh one."
        onRetry={() => passportQuery.refetch()}
        retrying={passportQuery.isFetching}
      />
    );
  }

  const passport = passportQuery.data;
  if (!passport) return null;
  const content = passport.content as unknown as PassportContent;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-5 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-success-light text-success-dark">
          <BadgeCheck className="size-6" aria-hidden="true" />
        </div>
        <h1 className="text-h2 font-semibold text-foreground">{content.plant_origin.common_label ?? content.plant_origin.species ?? "Plant Passport"}</h1>
        <p className="text-body-sm text-muted-foreground">
          Passport {passport.passport_number} · Version {passport.version}
        </p>
        <p className="text-caption text-muted-foreground">Generated {new Date(passport.generated_at).toLocaleDateString()}</p>
      </div>

      <Section title="Origin" icon={Sprout}>
        <Field label="Species" value={content.plant_origin.species} />
        <Field label="Botanical name" value={content.plant_origin.botanical_name} italic />
        <Field label="Variety" value={content.plant_origin.variety} />
        <Field label="Batch number" value={content.plant_origin.batch_number} />
        <Field label="Planted" value={content.plant_origin.planted_at ? new Date(content.plant_origin.planted_at).toLocaleDateString() : null} />
      </Section>

      <Section title="Nursery" icon={Leaf}>
        <Field label="Nursery" value={content.nursery_information.name} />
        <Field label="Branch" value={content.nursery_information.branch_name} />
        <Field label="Contact" value={content.nursery_information.contact_email} />
      </Section>

      <Section title="Care guide" icon={Droplet}>
        <Field label="Light" value={content.care_guide.light_requirement} />
        <Field label="Soil type" value={content.care_guide.soil_type} />
        <Field
          label="Water baseline"
          value={content.care_guide.water_baseline_ml_per_week !== null ? `${content.care_guide.water_baseline_ml_per_week} mL/week` : null}
        />
        <Field
          label="Temperature range"
          value={
            content.care_guide.temperature_min_celsius !== null && content.care_guide.temperature_max_celsius !== null
              ? `${content.care_guide.temperature_min_celsius}–${content.care_guide.temperature_max_celsius}°C`
              : null
          }
        />
      </Section>

      {content.health_timeline.length > 0 && (
        <Section title="Health history at time of issue">
          <ul className="flex flex-col gap-1">
            {content.health_timeline.map((entry, i) => (
              <li key={i} className="flex justify-between text-body-sm">
                <span className="text-foreground">{entry.status_label ?? "—"}</span>
                <span className="text-muted-foreground">{entry.recorded_at ? new Date(entry.recorded_at).toLocaleDateString() : "—"}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.purchase_information && (
        <Section title="Purchase">
          <Field label="Purchased" value={content.purchase_information.sold_at ? new Date(content.purchase_information.sold_at).toLocaleDateString() : null} />
        </Section>
      )}

      {/*
        AI care recommendations are always [] until Module 10 writes them
        -- see lib/api/public-passport.ts's docstring. This section is
        only shown once real recommendations exist, never a placeholder,
        per the "no fake/mock content" requirement.
      */}
      {content.ai_care_recommendations.length > 0 && (
        <Section title="AI care recommendations">
          <p className="text-body-sm text-muted-foreground">Recommendations available.</p>
        </Section>
      )}

      <CurrentCareSection scanQuery={scanQuery} />
    </div>
  );
}

function CurrentCareSection({ scanQuery }: { scanQuery: ReturnType<typeof useQrScanQuery> }) {
  if (scanQuery.isLoading) return <Skeleton className="h-32 w-full" />;
  if (scanQuery.isError || !scanQuery.data) return null; // The certificate above already rendered successfully -- a live-data hiccup here shouldn't hide it.

  const scan = scanQuery.data;

  return (
    <Section title="Current care status" badge="Live">
      {scan.health_status && (
        <Field
          label="Health"
          value={scan.health_status.status_label ?? (scan.health_status.health_score !== null ? `Score: ${scan.health_status.health_score}` : null)}
        />
      )}
      {scan.water_schedule && (
        <Field
          label="Watering"
          value={scan.water_schedule.baseline_ml_per_week !== null ? `${scan.water_schedule.baseline_ml_per_week} mL/week baseline` : null}
        />
      )}
      {scan.fertilizer_schedule && (
        <Field
          label="Fertilizer"
          value={`${scan.fertilizer_schedule.product_name}${scan.fertilizer_schedule.next_application_date ? ` · next ${new Date(scan.fertilizer_schedule.next_application_date).toLocaleDateString()}` : ""}`}
        />
      )}
      {!scan.health_status && !scan.water_schedule && !scan.fertilizer_schedule && (
        <p className="text-body-sm text-muted-foreground">No current care data recorded for this plant yet.</p>
      )}
    </Section>
  );
}

function Section({ title, icon: Icon, badge, children }: { title: string; icon?: ElementType; badge?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
        <h2 className="text-h4 font-semibold text-foreground">{title}</h2>
        {badge && <Badge tone="info">{badge}</Badge>}
      </div>
      <div className="flex flex-col gap-1">{children}</div>
    </div>
  );
}

function Field({ label, value, italic = false }: { label: string; value: string | null; italic?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-4 text-body-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={italic ? "italic text-foreground" : "text-foreground"}>{value}</span>
    </div>
  );
}
