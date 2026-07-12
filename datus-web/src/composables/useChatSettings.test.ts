import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

function installLocalStorage(value: string | null, writeError = false) {
  const storage = {
    getItem: vi.fn(() => value),
    setItem: vi.fn(() => {
      if (writeError) throw new Error("write blocked");
    }),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
  return storage;
}

describe("useChatSettings", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("uses defaults for malformed stored JSON", async () => {
    installLocalStorage("{");

    const { useChatSettings } = await import("./useChatSettings");
    const settings = useChatSettings();

    expect(settings.language.value).toBe("zh");
    expect(settings.permissionMode.value).toBe("normal");
    expect(settings.planMode.value).toBe(false);
  });

  it("validates each stored field before using it", async () => {
    installLocalStorage(JSON.stringify({
      language: 42,
      permissionMode: null,
      planMode: "yes",
    }));

    const { useChatSettings } = await import("./useChatSettings");
    const settings = useChatSettings();

    expect(settings.language.value).toBe("zh");
    expect(settings.permissionMode.value).toBe("normal");
    expect(settings.planMode.value).toBe(false);
  });

  it("preserves valid settings and persists updates", async () => {
    const storage = installLocalStorage(JSON.stringify({
      language: "en",
      permissionMode: "elevated",
      planMode: true,
    }));

    const { useChatSettings } = await import("./useChatSettings");
    const settings = useChatSettings();

    expect(settings.language.value).toBe("en");
    expect(settings.permissionMode.value).toBe("elevated");
    expect(settings.planMode.value).toBe(true);

    settings.setPlanMode(false);
    await nextTick();

    expect(storage.setItem).toHaveBeenLastCalledWith("datus-chat-settings", JSON.stringify({
      language: "en",
      permissionMode: "elevated",
      planMode: false,
    }));
  });

  it("keeps reactive state when persistence fails", async () => {
    installLocalStorage(null, true);

    const { useChatSettings } = await import("./useChatSettings");
    const settings = useChatSettings();

    settings.setLanguage("en");
    await nextTick();

    expect(settings.language.value).toBe("en");
  });
});
