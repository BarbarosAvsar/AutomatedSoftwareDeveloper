import "@testing-library/jest-dom";

class MockEventSource {
  constructor(_url: string) {}

  onmessage: ((event: MessageEvent<string>) => void) | null = null;

  onerror: ((event: Event) => void) | null = null;

  close(): void {
    // no-op for tests
  }
}

Object.defineProperty(window, "EventSource", {
  writable: true,
  value: MockEventSource,
});
