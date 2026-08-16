"use client";

import { useQuery } from "@tanstack/react-query";

import * as twinApi from "@/lib/api/digital-twin";

/** Query key factory for 7H's Plant Digital Twin reads. */
export const twinKeys = {
  all: ["digital-twin"] as const,
  current: (plantId: string) => [...twinKeys.all, "current", plantId] as const,
  timeline: (plantId: string, page: number) => [...twinKeys.all, "timeline", plantId, page] as const,
  versions: (plantId: string, page: number) => [...twinKeys.all, "versions", plantId, page] as const,
  version: (plantId: string, version: number) => [...twinKeys.all, "version", plantId, version] as const,
  compare: (plantId: string, versionA: number, versionB: number) =>
    [...twinKeys.all, "compare", plantId, versionA, versionB] as const,
  snapshotByDate: (plantId: string, asOf: string) => [...twinKeys.all, "snapshot-by-date", plantId, asOf] as const,
  events: (plantId: string, page: number) => [...twinKeys.all, "events", plantId, page] as const,
  list: (params: twinApi.ListDigitalTwinsParams) => [...twinKeys.all, "list", params] as const,
};

export function useCurrentTwinQuery(plantId: string | null) {
  return useQuery({
    queryKey: twinKeys.current(plantId ?? "none"),
    queryFn: () => twinApi.getCurrentTwin(plantId as string),
    enabled: plantId !== null,
    staleTime: 15 * 1000,
  });
}

export function useTwinTimelineQuery(plantId: string | null, page: number) {
  return useQuery({
    queryKey: twinKeys.timeline(plantId ?? "none", page),
    queryFn: () => twinApi.getTwinTimeline(plantId as string, page),
    enabled: plantId !== null,
  });
}

export function useVersionHistoryQuery(plantId: string | null, page: number) {
  return useQuery({
    queryKey: twinKeys.versions(plantId ?? "none", page),
    queryFn: () => twinApi.getVersionHistory(plantId as string, page),
    enabled: plantId !== null,
  });
}

/** On-demand only -- fetched when the Version History tab's "View snapshot" action opens a specific version. */
export function useVersionQuery(plantId: string | null, version: number | null) {
  return useQuery({
    queryKey: twinKeys.version(plantId ?? "none", version ?? 0),
    queryFn: () => twinApi.getVersion(plantId as string, version as number),
    enabled: plantId !== null && version !== null,
  });
}

/** On-demand only -- fetched once the user has picked two real versions to compare. */
export function useVersionCompareQuery(plantId: string | null, versionA: number | null, versionB: number | null) {
  return useQuery({
    queryKey: twinKeys.compare(plantId ?? "none", versionA ?? 0, versionB ?? 0),
    queryFn: () => twinApi.compareVersions(plantId as string, versionA as number, versionB as number),
    enabled: plantId !== null && versionA !== null && versionB !== null,
  });
}

export function useEventHistoryQuery(plantId: string | null, page: number) {
  return useQuery({
    queryKey: twinKeys.events(plantId ?? "none", page),
    queryFn: () => twinApi.getEventHistory(plantId as string, page),
    enabled: plantId !== null,
  });
}

export function useDigitalTwinsListQuery(params: twinApi.ListDigitalTwinsParams) {
  return useQuery({
    queryKey: twinKeys.list(params),
    queryFn: () => twinApi.listDigitalTwins(params),
  });
}
