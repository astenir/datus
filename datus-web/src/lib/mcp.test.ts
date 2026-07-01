import { describe, expect, it } from "vitest";

import { buildMcpServerInfo, buildRemoteMcpHeaders, createDefaultMcpServerForm } from "./mcp";

describe("MCP helpers", () => {
  it("builds an Authorization header from a remote MCP token", () => {
    expect(buildRemoteMcpHeaders({ token: "abc123" })).toEqual({
      headers: { Authorization: "Bearer abc123" },
    });
  });

  it("keeps a pasted Bearer token unchanged", () => {
    expect(buildRemoteMcpHeaders({ token: "Bearer abc123" })).toEqual({
      headers: { Authorization: "Bearer abc123" },
    });
  });

  it("lets the token field override Authorization from custom headers", () => {
    expect(
      buildRemoteMcpHeaders({
        token: "new-token",
        headersJson: '{"Authorization":"Bearer old-token","X-API-Key":"key"}',
      }),
    ).toEqual({
      headers: {
        Authorization: "Bearer new-token",
        "X-API-Key": "key",
      },
    });
  });

  it("returns no headers when both inputs are empty", () => {
    expect(buildRemoteMcpHeaders({ token: "", headersJson: "" })).toEqual({});
  });

  it("rejects invalid headers JSON", () => {
    expect(buildRemoteMcpHeaders({ headersJson: "not json" }).error).toBe("Headers 必须是合法的 JSON 对象");
  });

  it("rejects non-string header values", () => {
    expect(buildRemoteMcpHeaders({ headersJson: '{"X-Retry":3}' }).error).toBe(
      "Headers 必须是键和值均为字符串的 JSON 对象",
    );
  });

  it("builds a stdio server from form input", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "filesystem",
        command: "npx",
        argsText: "-y, @modelcontextprotocol/server-filesystem\n/tmp",
        envJson: '{"NODE_OPTIONS":"--no-warnings"}',
        cwd: "/workspace",
      }),
    ).toEqual({
      server: {
        name: "filesystem",
        type: "stdio",
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        env: { NODE_OPTIONS: "--no-warnings" },
        cwd: "/workspace",
      },
    });
  });

  it("builds a remote HTTP server from form input", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        token: "token",
        headersJson: '{"X-Project":"demo"}',
        timeoutText: "30",
      }),
    ).toEqual({
      server: {
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        headers: {
          Authorization: "Bearer token",
          "X-Project": "demo",
        },
        timeout: 30,
      },
    });
  });

  it("requires a command for stdio servers", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "filesystem",
      }).error,
    ).toBe("stdio MCP 需要填写启动命令");
  });

  it("requires a URL for remote servers", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "sse",
      }).error,
    ).toBe("sse MCP 需要填写 URL");
  });

  it("rejects invalid env JSON", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "filesystem",
        command: "python",
        envJson: "not json",
      }).error,
    ).toBe("Env 必须是合法的 JSON 对象");
  });

  it("rejects invalid timeout values", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        timeoutText: "0",
      }).error,
    ).toBe("Timeout 必须是大于 0 的数字");
  });
});
