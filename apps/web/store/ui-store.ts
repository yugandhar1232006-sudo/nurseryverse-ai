import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Pure UI/chrome state -- never server data (that's TanStack Query's job,
 * see providers/query-provider.tsx's docstring). Sidebar/density/etc. are
 * layout preferences, not sensitive data, so persisting them to
 * localStorage is fine; this is a different category from the auth
 * tokens in store/session-store.ts, which are deliberately kept out of
 * any persistent storage.
 */
interface UiState {
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  commandPaletteOpen: boolean;
  notificationCenterOpen: boolean;
  assistantPanelOpen: boolean;
}

interface UiActions {
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setMobileNavOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setAssistantPanelOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState & UiActions>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      mobileNavOpen: false,
      commandPaletteOpen: false,
      // Lifted out of `NotificationCenter`'s own local state (rather than
      // kept there) so the mobile bottom tab bar's "Alerts" item
      // (components/layout/mobile-nav.tsx) can open the exact same
      // panel instance the header bell does, instead of the two
      // triggers accidentally growing two separate notification UIs --
      // which the 7C kickoff explicitly prohibits ("Do not create a
      // second notification system").
      notificationCenterOpen: false,
      // 7L's AI Assistant panel -- same lifted-to-shared-state reasoning
      // as `notificationCenterOpen` above: a persistent header overlay
      // (per nav-config.ts's docstring, "Notifications and AI Assistant
      // are deliberately NOT [sidebar destinations] ... they're
      // persistent header overlays"), triggered from `TopNav`, with
      // exactly one panel instance regardless of how many places might
      // ever open it.
      assistantPanelOpen: false,

      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
      setNotificationCenterOpen: (open) => set({ notificationCenterOpen: open }),
      setAssistantPanelOpen: (open) => set({ assistantPanelOpen: open }),
    }),
    {
      name: "nurseryverse-ui",
      // Only the durable layout preference is persisted -- transient
      // overlay-open flags reset to closed on every load, which is the
      // correct behavior (a reload shouldn't reopen a mobile nav sheet).
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    },
  ),
);
