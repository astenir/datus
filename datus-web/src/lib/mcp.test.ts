import { describe, expect, it } from "vitest";

import { buildRemoteMcpHeaders } from "./mcp";

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
});
