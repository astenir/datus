import { describe, expect, it } from "vitest";

import { parsePermissionRequest } from "./interaction-display";

describe("parsePermissionRequest", () => {
  it("extracts tool name and JSON args from markdown permission prompts", () => {
    expect(
      parsePermissionRequest(
        '### Permission Request **Tool:** `tools.stock_info_get_info` **Args:** `{"api_name": "getEqu"}`',
      ),
    ).toEqual({
      toolName: "tools.stock_info_get_info",
      serverName: "tools",
      operationName: "stock_info_get_info",
      argsText: '{"api_name": "getEqu"}',
      argsRows: [{ key: "api_name", value: "getEqu" }],
    });
  });

  it("keeps non-JSON args visible as a fallback row", () => {
    expect(
      parsePermissionRequest(
        "Permission Request\nTool: filesystem.read_file\nArgs: /tmp/report.md",
      ),
    ).toEqual({
      toolName: "filesystem.read_file",
      serverName: "filesystem",
      operationName: "read_file",
      argsText: "/tmp/report.md",
      argsRows: [{ key: "Args", value: "/tmp/report.md" }],
    });
  });

  it("ignores normal interaction copy", () => {
    expect(parsePermissionRequest("请选择是否继续")).toBeNull();
  });
});
