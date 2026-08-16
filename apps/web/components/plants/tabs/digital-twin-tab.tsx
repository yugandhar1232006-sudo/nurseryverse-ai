"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TwinOverview } from "@/components/digital-twin/twin-overview";
import { TwinTimelinePanel } from "@/components/digital-twin/twin-timeline-panel";
import { VersionHistoryPanel } from "@/components/digital-twin/version-history-panel";
import { EventHistoryPanel } from "@/components/digital-twin/event-history-panel";

/**
 * 7H's flagship UI: the real, event-driven Digital Twin for one plant.
 * Nested inside the Plant Profile's own top-level Tabs as a single
 * "Digital Twin" tab (gated on `plants:read`, the same permission the
 * whole page already requires -- Module 7 mints no separate permission
 * code, see lib/api/digital-twin.ts's docstring) rather than four
 * separate top-level tabs, since Overview/Timeline/Versions/Events are
 * all views of the *same* twin, not independent record types the way
 * Growth/Health/Watering are.
 */
export function DigitalTwinTab({ plantId }: { plantId: string }) {
  return (
    <Tabs defaultValue="overview">
      <TabsList aria-label="Digital Twin views">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="timeline">Timeline</TabsTrigger>
        <TabsTrigger value="versions">Versions</TabsTrigger>
        <TabsTrigger value="events">Events</TabsTrigger>
      </TabsList>
      <TabsContent value="overview">
        <TwinOverview plantId={plantId} />
      </TabsContent>
      <TabsContent value="timeline">
        <TwinTimelinePanel plantId={plantId} />
      </TabsContent>
      <TabsContent value="versions">
        <VersionHistoryPanel plantId={plantId} />
      </TabsContent>
      <TabsContent value="events">
        <EventHistoryPanel plantId={plantId} />
      </TabsContent>
    </Tabs>
  );
}
