import { beforeEach, describe, expect, it, vi } from "vitest";

const { toastError } = vi.hoisted(() => ({
  toastError: vi.fn(),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

import { handleError } from "./utils";

describe("handleError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps technical details in logs and out of the user toast", () => {
    const error = new Error("RuntimeError: https://private.example/mcp failed at /srv/app.py");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    handleError("加载失败", error);

    expect(consoleError).toHaveBeenCalledWith("加载失败", error);
    expect(toastError).toHaveBeenCalledWith("加载失败");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("private.example");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("/srv/app.py");
    consoleError.mockRestore();
  });

  it("leaves expired login feedback to the authentication handler", () => {
    const error = { status: 401 };
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    handleError("加载失败", error);

    expect(consoleError).toHaveBeenCalledWith("加载失败", error);
    expect(toastError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
