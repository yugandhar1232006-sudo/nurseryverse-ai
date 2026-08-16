"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PlantHeader } from "@/components/plants/plant-header";
import { OverviewTab } from "@/components/plants/tabs/overview-tab";
import { GrowthTab } from "@/components/plants/tabs/growth-tab";
import { HealthTab } from "@/components/plants/tabs/health-tab";
import { WateringTab } from "@/components/plants/tabs/watering-tab";
import { FertilizerTab } from "@/components/plants/tabs/fertilizer-tab";
import { EnvironmentalTab } from "@/components/plants/tabs/environmental-tab";
import { MovementTab } from "@/components/plants/tabs/movement-tab";
import { TimelineTab } from "@/components/plants/tabs/timeline-tab";
import { ImagesTab } from "@/components/plants/tabs/images-tab";
import { DigitalTwinTab } from "@/components/plants/tabs/digital-twin-tab";
import { PassportTab } from "@/components/plants/tabs/passport-tab";
import { AiPredictionsTab } from "@/components/plants/tabs/ai-predictions-tab";
import { usePlantDetailQuery } from "@/lib/plants/queries";

/**
 * The Plant Profile page -- the first dynamic route in this app
 * (`/plants/[id]`). Uses `useParams()` rather than the Server Component
 * `params` prop because this whole page is client-rendered (every tab
 * below needs TanStack Query + permission-aware hooks); Next 16 makes
 * `params` a Promise for Server Components, which would add an async
 * boundary this page has no other reason to need.
 *
 * Each tab is independently permission-gated (`growth:read`, `health:read`,
 * `watering:read`, `environmental:read` -- fertilizer reuses `watering:read`,
 * see lib/api/plant-records.ts's docstring) since a Horticulturist and a
 * Sales Staff member looking at the same plant see a different set of tabs
 * entirely (Sales Staff has none of growth/health/disease/environmental/
 * watering per docs/ux/07-role-permission-matrix.md).
 */
export default function PlantDetailPage() {
  const params = useParams<{ id: string }>();
  const plantId = params.id;

  const plantQuery = usePlantDetailQuery(plantId);

  return (
    <PermissionGate permission="plants:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {plantQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}
        {plantQuery.isError && (
          <ErrorState variant="full-page" error={plantQuery.error} onRetry={() => plantQuery.refetch()} retrying={plantQuery.isFetching} />
        )}
        {plantQuery.data && (
          <>
            <PlantHeader plant={plantQuery.data} />

            <Tabs defaultValue="overview">
              <TabsList className="flex-wrap">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <PermissionGate permission="growth:read">
                  <TabsTrigger value="growth">Growth</TabsTrigger>
                </PermissionGate>
                <PermissionGate permission="health:read">
                  <TabsTrigger value="health">Health</TabsTrigger>
                </PermissionGate>
                <PermissionGate permission="watering:read">
                  <TabsTrigger value="watering">Watering</TabsTrigger>
                </PermissionGate>
                <PermissionGate permission="watering:read">
                  <TabsTrigger value="fertilizer">Fertilizer</TabsTrigger>
                </PermissionGate>
                <PermissionGate permission="environmental:read">
                  <TabsTrigger value="environmental">Environment</TabsTrigger>
                </PermissionGate>
                <TabsTrigger value="movement">Movement</TabsTrigger>
                <TabsTrigger value="images">Images</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
                <TabsTrigger value="digital-twin">Digital Twin</TabsTrigger>
                <PermissionGate permission="passport:read">
                  <TabsTrigger value="passport">Passport</TabsTrigger>
                </PermissionGate>
                <PermissionGate permission="ai_predictions:read">
                  <TabsTrigger value="ai-predictions">AI Predictions</TabsTrigger>
                </PermissionGate>
              </TabsList>

              <TabsContent value="overview">
                <OverviewTab plant={plantQuery.data} />
              </TabsContent>
              <PermissionGate permission="growth:read">
                <TabsContent value="growth">
                  <GrowthTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <PermissionGate permission="health:read">
                <TabsContent value="health">
                  <HealthTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <PermissionGate permission="watering:read">
                <TabsContent value="watering">
                  <WateringTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <PermissionGate permission="watering:read">
                <TabsContent value="fertilizer">
                  <FertilizerTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <PermissionGate permission="environmental:read">
                <TabsContent value="environmental">
                  <EnvironmentalTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <TabsContent value="movement">
                <MovementTab plantId={plantId} />
              </TabsContent>
              <TabsContent value="images">
                <ImagesTab plantId={plantId} />
              </TabsContent>
              <TabsContent value="timeline">
                <TimelineTab plantId={plantId} />
              </TabsContent>
              <TabsContent value="digital-twin">
                <DigitalTwinTab plantId={plantId} />
              </TabsContent>
              <PermissionGate permission="passport:read">
                <TabsContent value="passport">
                  <PassportTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
              <PermissionGate permission="ai_predictions:read">
                <TabsContent value="ai-predictions">
                  <AiPredictionsTab plantId={plantId} />
                </TabsContent>
              </PermissionGate>
            </Tabs>
          </>
        )}
      </div>
    </PermissionGate>
  );
}
