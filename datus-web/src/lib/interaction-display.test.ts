import { describe, expect, it } from "vitest";

import {
  clearPersonalMcpDisplayNames,
  setPersonalMcpDisplayNames,
} from "./personal-mcp-display";
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

  it("resolves a personal MCP alias to its display name in permission requests", () => {
    const id = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
    const alias = `personal_${id}`;
    setPersonalMcpDisplayNames([{ id, displayName: "我的搜索服务" }]);
    try {
      expect(
        parsePermissionRequest(
          `### Permission Request **Tool:** \`mcp.${alias}.search_docs\` **Args:** \`{"query": "年报"}\``,
        ),
      ).toEqual({
        toolName: "mcp.我的搜索服务.search_docs",
        serverName: "mcp.我的搜索服务",
        operationName: "search_docs",
        argsText: '{"query": "年报"}',
        argsRows: [{ key: "query", value: "年报" }],
      });
    } finally {
      clearPersonalMcpDisplayNames();
    }
  });
});
