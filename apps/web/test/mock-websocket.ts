/**
 * jsdom does not implement `WebSocket` (it's on jsdom's own documented
 * "unimplemented" list) -- any test that renders a component reaching
 * `lib/notifications/use-notification-socket.ts` needs a real
 * constructable stand-in rather than crashing on `new WebSocket(...)`.
 *
 * This intentionally mimics only what that hook actually uses
 * (`onopen`/`onmessage`/`onclose`/`onerror`, `close()`, the URL it was
 * constructed with) -- not a full WebSocket implementation. Tests that
 * need to simulate the real Module 11 hub pushing a frame grab the most
 * recent instance via `MockWebSocket.instances` and call
 * `.emitMessage(json)` / `.emitOpen()` / `.emitClose()` directly; nothing
 * here opens a real network connection.
 */
export class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.closed = true;
    this.emitClose();
  }

  emitOpen() {
    this.onopen?.();
  }

  emitMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  emitClose() {
    this.onclose?.();
  }

  static reset() {
    MockWebSocket.instances = [];
  }
}
