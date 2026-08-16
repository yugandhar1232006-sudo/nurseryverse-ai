/**
 * Must run BEFORE test/setup.ts: zustand's `persist` middleware resolves
 * its storage via `createJSONStorage(() => window.localStorage)` at
 * store-creation time, and setup.ts imports the persisted stores
 * (ui-store, branch-context-store) at module top level -- before any
 * `beforeAll`/`afterEach` hook could run. So this bridging has to happen
 * here, at this file's module scope, ahead of those imports.
 *
 * Why it is needed: Node 26+ defines `globalThis.localStorage` /
 * `sessionStorage` as undefined properties (see `node
 * --localstorage-file`), and vitest 4's `populateGlobal` skips any jsdom
 * window key that already exists on the Node global unless it is in
 * vitest's hardcoded KEYS list -- which `localStorage` is not. The jsdom
 * Storage objects therefore never make it onto the test global, and the
 * persist middleware ends up closing over an undefined `storage`, so
 * every persisted setState throws `Cannot read properties of undefined
 * (reading 'setItem')`. Bridging jsdom's real Storage objects over
 * explicitly is the same category as the matchMedia / ResizeObserver /
 * WebSocket stubs in setup.ts: a missing browser API in the test
 * environment, not a change to app behavior.
 */
const jsdomWindow = (
  globalThis as {
    jsdom?: { window?: { localStorage?: Storage; sessionStorage?: Storage } };
  }
).jsdom?.window;

if (jsdomWindow?.localStorage && typeof window.localStorage === "undefined") {
  Object.defineProperty(window, "localStorage", {
    value: jsdomWindow.localStorage,
    writable: true,
    configurable: true,
    enumerable: true,
  });
}

if (jsdomWindow?.sessionStorage && typeof window.sessionStorage === "undefined") {
  Object.defineProperty(window, "sessionStorage", {
    value: jsdomWindow.sessionStorage,
    writable: true,
    configurable: true,
    enumerable: true,
  });
}
