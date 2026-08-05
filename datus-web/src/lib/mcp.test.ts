import { describe, expect, it } from "vitest";

import {
  buildMcpServerInfo,
  buildRemoteMcpHeaders,
  createDefaultMcpServerForm,
  createMcpServerForm,
  friendlyMcpConnectionError,
} from "./mcp";

describe("MCP helpers", () => {
  it("explains an expired remote MCP endpoint without exposing the raw URL", () => {
    const error = new Error(
      "Failed to list tools on server 'china-stock-mcp': Failed to connect to MCP server "
      + "'streamable_http: https://mcp.api-inference.modelscope.net/private/mcp': HTTP error 410 (Gone)",
    );

    const result = friendlyMcpConnectionError(error, "china-stock-mcp");

    expect(result).toEqual({
      title: "MCP Server 地址已失效",
      description: "“china-stock-mcp”对应的远程服务已下线或 URL 已过期，请更新配置后重试。",
    });
    expect(JSON.stringify(result)).not.toContain("mcp.api-inference.modelscope.net");
  });

  it("gives actionable guidance for MCP connection timeouts", () => {
    expect(friendlyMcpConnectionError(new Error("httpcore.ConnectTimeout: Connection timeout"), "quotes")).toEqual({
      title: "MCP Server 连接超时",
      description: "暂时无法连接“quotes”，请检查服务地址、网络、代理或防火墙后重试。",
    });
  });

  it("describes remote MCP authentication failures without exposing backend details", () => {
    expect(friendlyMcpConnectionError(new Error("HTTP error 403 (Forbidden) for https://private.example/mcp"), "quotes")).toEqual({
      title: "MCP Server 认证失败",
      description: "“quotes”拒绝了连接，请检查 Token、Headers 和远程服务权限。",
    });
  });

  it("uses a safe fallback for unknown MCP connection errors", () => {
    const result = friendlyMcpConnectionError(new Error("RuntimeError: /srv/private/mcp.py failed"), "quotes");

    expect(result).toEqual({
      title: "无法连接 MCP Server",
      description: "暂时无法连接“quotes”，请检查服务地址、认证信息和网络连接后重试。",
    });
    expect(JSON.stringify(result)).not.toContain("/srv/private/mcp.py");
  });

  it("leaves expired login feedback to the global authentication handler", () => {
    expect(friendlyMcpConnectionError({ status: 401 }, "quotes")).toBeNull();
  });

  it("rejects Authorization in custom headers", () => {
    expect(buildRemoteMcpHeaders({ headersJson: '{"authorization":"Bearer old-value"}' }).error).toBe(
      "Authorization 请通过认证方式配置，不能写入 Headers JSON",
    );
  });

  it("returns no headers when the JSON input is empty", () => {
    expect(buildRemoteMcpHeaders({ headersJson: "" })).toEqual({});
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

  it("hydrates an edit form from an existing MCP server", () => {
    expect(
      createMcpServerForm({
        name: "filesystem",
        type: "stdio",
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        env: { NODE_OPTIONS: "--no-warnings" },
        cwd: "/workspace",
      }),
    ).toEqual({
      ...createDefaultMcpServerForm(),
      name: "filesystem",
      type: "stdio",
      command: "npx",
      argsText: "-y\n@modelcontextprotocol/server-filesystem\n/tmp",
      envJson: JSON.stringify({ NODE_OPTIONS: "--no-warnings" }, null, 2),
      cwd: "/workspace",
    });
  });

  it("builds a remote HTTP server from form input", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        headersJson: '{"X-Project":"demo"}',
        timeoutText: "30",
      }),
    ).toEqual({
      server: {
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        headers: {
          "X-Project": "demo",
        },
        auth: { mode: "request_bearer" },
        timeout: 30,
      },
    });
  });

  it("builds a remote server with a fixed token outside custom headers", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "sse",
        url: "https://example.com/sse",
        authMode: "static_bearer",
        token: "Bearer fixed-value",
      }),
    ).toEqual({
      server: {
        name: "remote",
        type: "sse",
        url: "https://example.com/sse",
        auth: { mode: "static_bearer", token: "Bearer fixed-value" },
      },
    });
  });

  it("requires a fixed token when creating manual authentication", () => {
    expect(
      buildMcpServerInfo({
        ...createDefaultMcpServerForm(),
        name: "remote",
        type: "http",
        url: "https://example.com/mcp",
        authMode: "static_bearer",
      }).error,
    ).toBe("手动认证需要填写固定 Bearer Token");
  });

  it("preserves a configured fixed token when editing with an empty field", () => {
    const form = createMcpServerForm({
      name: "remote",
      type: "http",
      url: "https://example.com/mcp",
      auth: { mode: "static_bearer", credential_configured: true },
    });

    expect(form.token).toBe("");
    expect(buildMcpServerInfo(form).server?.auth).toEqual({ mode: "static_bearer" });
  });

  it("hydrates request authentication without exposing a token", () => {
    const form = createMcpServerForm({
      name: "remote",
      type: "http",
      url: "https://example.com/mcp",
      auth: { mode: "request_bearer", credential_configured: true },
    });

    expect(form.authMode).toBe("request_bearer");
    expect(form.token).toBe("");
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
