import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

describe("useTheme", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    vi.unstubAllGlobals();
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("falls back to the system theme when storage access fails", async () => {
    const toggle = vi.fn();
    const rootStyle = { colorScheme: "" };
    vi.stubGlobal("window", {
      matchMedia: () => ({ matches: true }),
    });
    vi.stubGlobal("document", {
      documentElement: {
        classList: { toggle },
        style: rootStyle,
      },
    });
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("storage blocked");
      },
    });

    const { useTheme } = await import("./useTheme");
    const theme = useTheme();

    expect(theme.theme.value).toBe("dark");
    expect(toggle).toHaveBeenCalledWith("dark", true);
    expect(rootStyle.colorScheme).toBe("dark");

    theme.toggleTheme();
    await nextTick();

    expect(theme.theme.value).toBe("light");
    expect(toggle).toHaveBeenLastCalledWith("dark", false);
    expect(rootStyle.colorScheme).toBe("light");
  });
});
