import { afterEach, describe, expect, it, vi } from "vitest";
import { readLocalStorage, writeLocalStorage } from "./local-storage";

function installLocalStorage(storage: Pick<Storage, "getItem" | "setItem">) {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
}

describe("local storage helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("reads and writes available local storage", () => {
    const storage = {
      getItem: vi.fn(() => "saved"),
      setItem: vi.fn(),
    };
    installLocalStorage(storage);

    expect(readLocalStorage("key")).toBe("saved");
    expect(writeLocalStorage("key", "next")).toBe(true);
    expect(storage.getItem).toHaveBeenCalledWith("key");
    expect(storage.setItem).toHaveBeenCalledWith("key", "next");
  });

  it("falls back when local storage is unavailable", () => {
    expect(readLocalStorage("key")).toBeNull();
    expect(writeLocalStorage("key", "value")).toBe(false);
  });

  it("falls back when resolving local storage throws", () => {
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("storage blocked");
      },
    });

    expect(readLocalStorage("key")).toBeNull();
    expect(writeLocalStorage("key", "value")).toBe(false);
  });

  it("falls back when storage operations throw", () => {
    installLocalStorage({
      getItem: vi.fn(() => {
        throw new Error("read blocked");
      }),
      setItem: vi.fn(() => {
        throw new Error("write blocked");
      }),
    });

    expect(readLocalStorage("key")).toBeNull();
    expect(writeLocalStorage("key", "value")).toBe(false);
  });
});
