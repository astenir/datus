import { afterEach, describe, expect, it, vi } from "vitest";
import { copyTextToClipboard } from "./clipboard";

const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
const originalDocument = Object.getOwnPropertyDescriptor(globalThis, "document");

interface TextareaStub {
  focus: ReturnType<typeof vi.fn>
  parentNode: {
    removeChild: ReturnType<typeof vi.fn>
  }
  select: ReturnType<typeof vi.fn>
  setAttribute: ReturnType<typeof vi.fn>
  setSelectionRange: ReturnType<typeof vi.fn>
  style: CSSStyleDeclaration
  value: string
}

afterEach(() => {
  restoreGlobal("navigator", originalNavigator);
  restoreGlobal("document", originalDocument);
  vi.restoreAllMocks();
});

describe("copyTextToClipboard", () => {
  it("uses the modern Clipboard API when available", async () => {
    const writeText = vi.fn<Clipboard["writeText"]>().mockResolvedValue(undefined);
    setGlobal("navigator", {
      clipboard: { writeText },
    });

    await copyTextToClipboard("SELECT 1");

    expect(writeText).toHaveBeenCalledWith("SELECT 1");
  });

  it("falls back to execCommand when Clipboard API is unavailable", async () => {
    const execCommand = vi.fn<Document["execCommand"]>().mockReturnValue(true);
    const textarea = createTextareaStub();
    setGlobal("navigator", {});
    setGlobal("document", createDocumentStub({ execCommand, textarea }));

    await copyTextToClipboard("legacy browser");

    expect(textarea.value).toBe("legacy browser");
    expect(textarea.focus).toHaveBeenCalled();
    expect(textarea.select).toHaveBeenCalled();
    expect(textarea.setSelectionRange).toHaveBeenCalledWith(0, "legacy browser".length);
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(textarea.parentNode?.removeChild).toHaveBeenCalledWith(textarea);
  });

  it("falls back to execCommand when Clipboard API rejects", async () => {
    const writeText = vi.fn<Clipboard["writeText"]>().mockRejectedValue(new Error("denied"));
    const execCommand = vi.fn<Document["execCommand"]>().mockReturnValue(true);
    setGlobal("navigator", {
      clipboard: { writeText },
    });
    setGlobal("document", createDocumentStub({ execCommand, textarea: createTextareaStub() }));

    await copyTextToClipboard("fallback");

    expect(writeText).toHaveBeenCalledWith("fallback");
    expect(execCommand).toHaveBeenCalledWith("copy");
  });

  it("throws when neither copy path works", async () => {
    setGlobal("navigator", {});
    setGlobal("document", createDocumentStub({
      execCommand: vi.fn<Document["execCommand"]>().mockReturnValue(false),
      textarea: createTextareaStub(),
    }));

    await expect(copyTextToClipboard("nope")).rejects.toThrow("Clipboard copy failed");
  });
});

function setGlobal(name: "document" | "navigator", value: unknown) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    value,
  });
}

function restoreGlobal(name: "document" | "navigator", descriptor: PropertyDescriptor | undefined) {
  if (descriptor) {
    Object.defineProperty(globalThis, name, descriptor);
    return;
  }
  Reflect.deleteProperty(globalThis, name);
}

function createTextareaStub() {
  const style = {} as CSSStyleDeclaration;
  return {
    focus: vi.fn(),
    parentNode: {
      removeChild: vi.fn(),
    },
    select: vi.fn(),
    setAttribute: vi.fn(),
    setSelectionRange: vi.fn(),
    style,
    value: "",
  };
}

function createDocumentStub(options: {
  execCommand: Document["execCommand"];
  textarea: TextareaStub;
}) {
  const body = {
    appendChild: vi.fn(),
  };

  return {
    body,
    createElement: vi.fn(() => options.textarea),
    execCommand: options.execCommand,
    getSelection: vi.fn(() => null),
  };
}
