"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReportHistoryPanel } from "@/components/reports/report-history-panel";
import { ScheduledReportsPanel } from "@/components/reports/scheduled-reports-panel";

/**
 * 7N -- real `/reports` route content, replacing 7C's `ComingSoon`
 * placeholder. Two tabs matching the two distinct real workflows Module
 * 12's report routes support: on-demand generation (Catalog + Generate +
 * Status/History/Download) and Scheduled Reports CRUD. Dashboards/
 * Analytics are NOT here -- those are 7D's finished `/` route (see
 * docs/frontend/18-reports-analytics.md's Scope section for why this
 * phase doesn't duplicate that work).
 */
export function ReportsContent() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-h2 font-semibold text-foreground">Reports</h1>

      <Tabs defaultValue="reports">
        <TabsList>
          <TabsTrigger value="reports">Reports</TabsTrigger>
          <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
        </TabsList>

        <TabsContent value="reports">
          <ReportHistoryPanel />
        </TabsContent>

        <TabsContent value="scheduled">
          <ScheduledReportsPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
