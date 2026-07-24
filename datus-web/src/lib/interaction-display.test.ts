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

  it("extracts commands from bash permission prompts", () => {
    expect(
      parsePermissionRequest(
        "### Bash Command Permission\n\n```bash\ngit status\n```\n\n**Reason:** No bash command rule matched\n",
      ),
    ).toEqual({
      toolName: "bash_tools.bash",
      serverName: "bash_tools",
      operationName: "bash",
      argsText: "git status",
      argsRows: [{ key: "command", value: "git status" }],
    });
  });

  it("preserves multiline commands from bash permission prompts", () => {
    expect(
      parsePermissionRequest(
        "Bash Command Permission\n\n```sh\ncd /tmp\nprintf 'ready\\n'\n```",
      ),
    ).toMatchObject({
      argsText: "cd /tmp\nprintf 'ready\\n'",
      argsRows: [{ key: "command", value: "cd /tmp\nprintf 'ready\\n'" }],
    });
  });

  it("ignores normal interaction copy", () => {
    expect(parsePermissionRequest("请选择是否继续")).toBeNull();
  });
});
