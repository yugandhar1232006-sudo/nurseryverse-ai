import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";

import { server } from "./msw/server";
import { useSessionStore } from "@/store/session-store";
import { useNotificationStore } from "@/store/notification-store";
import { useUiStore } from "@/store/ui-store";
import { useBranchContextStore } from "@/store/branch-context-store";
import { MockWebSocket } from "./mock-websocket";

/**
 * `globals: false` in vitest.config.ts (deliberate -- explicit imports
 * over ambient globals) means every lifecycle hook, including this
 * file's, has to import from "vitest" itself rather than relying on
 * ambient `beforeAll`/`afterEach`.
 */

// MSW: real network-layer interception (see test/msw/handlers.ts's
// docstring for why this, not mocking lib/api/auth.ts directly).
// `onUnhandledRequest: "error"` deliberately -- a test that hits a route
// with no handler should fail loudly, not silently pass through to a
// real network call (there is no real backend in this environment) or
// return an opaque MSW warning buried in test output.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// RTL doesn't auto-cleanup when `globals: false` -- do it explicitly so
// one test's rendered tree never bleeds into the next.
afterEach(() => cleanup());

// Every auth test starts from a clean slate: no user, no tokens, and
// critically `status: "resolving"` reset back to its real initial value
// (several tests assert behavior that depends specifically on the
// resolving -> authenticated/unauthenticated transition, which would be
// invisible if a prior test's terminal state leaked in).
afterEach(() => {
  // Deliberately a *partial* merge, not `setState(x, true)` (full
  // replace): both stores hold their action functions (setSession,
  // clearSession, etc.) on this same state object, not external to it.
  // A full replace with only the data fields would wipe those functions
  // out along with the data, breaking every subsequent test in the file
  // with "clearSession is not a function".
  useSessionStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    accessTokenExpiresAt: null,
    status: "resolving",
  });
  useNotificationStore.setState({ notifications: [], unreadCount: 0, connectionStatus: "disconnected" });
  // 7C's shell-chrome stores: a collapsed sidebar, an open mobile drawer,
  // an open command palette, an open notification panel, or a
  // previously-selected branch id from one test must never leak into the
  // next test's initial render.
  useUiStore.setState({
    sidebarCollapsed: false,
    mobileNavOpen: false,
    commandPaletteOpen: false,
    notificationCenterOpen: false,
  });
  useBranchContextStore.setState({ selectedBranchId: null });
  MockWebSocket.reset();
  // lib/auth/session-marker.ts's cookie -- jsdom's `document` persists
  // across tests within one file, so a marker set by one test would
  // otherwise leak into the next and skew proxy/route-guard-adjacent
  // assertions that read `document.cookie`.
  document.cookie = "nv_has_session=; path=/; max-age=0; samesite=lax";
});

// Radix primitives (Avatar, Tooltip, etc. rendered via AppHeader) probe
// `window.matchMedia` and `ResizeObserver` during mount; jsdom implements
// neither. Stubbing both once here is simpler than every test file that
// touches a Radix-based component reinventing the same polyfill.
beforeAll(() => {
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  }
  if (!("ResizeObserver" in window)) {
    class ResizeObserverStub {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    // @ts-expect-error -- test-only polyfill, not a full implementation.
    window.ResizeObserver = ResizeObserverStub;
  }
  // Radix's Select (used by BranchSelector, DashboardScopeSelect, and
  // every future filter/form Select in 7E-7O) calls the Pointer Events
  // capture API and `scrollIntoView` on its trigger/items -- neither
  // exists in jsdom (confirmed: jsdom implements no Pointer Events
  // capture methods at all, and `scrollIntoView` is a documented no-op
  // gap), which surfaces as a real `TypeError: target.hasPointerCapture
  // is not a function` the first time a test actually opens a Select via
  // `userEvent.click`, rather than only asserting its closed-state
  // trigger text. Same category of gap as `matchMedia`/`ResizeObserver`
  // above -- a missing browser API, not a change to this app's own
  // behavior -- so it gets the same treatment: a minimal, test-only stub.
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
  // jsdom's WebSocket is a read-only getter (a plain assignment throws
  // "Cannot assign to read only property"), so it needs `defineProperty`,
  // not `window.WebSocket = ...`. Always overridden (not
  // `if (!window.WebSocket)` like the two stubs above) since jsdom's own
  // implementation is present but non-functional (on jsdom's documented
  // "unimplemented" list), not simply absent.
  Object.defineProperty(window, "WebSocket", {
    value: MockWebSocket,
    writable: true,
    configurable: true,
  });
});
