import { afterEach, describe, expect, it, vi } from "vitest";

function installLocalStorage(value: string | null = null) {
  const storage = {
    getItem: vi.fn(() => value),
    setItem: vi.fn(),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
  return storage;
}

describe("useConnection", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("uses the injected chatbot origin when no local API base is configured", async () => {
    installLocalStorage("");
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "https://embed.example.test/api/",
    }));

    const { useConnection } = await import("./useConnection");
    const { effectiveBase } = useConnection();

    expect(effectiveBase()).toBe("https://embed.example.test/api");
  });
});
