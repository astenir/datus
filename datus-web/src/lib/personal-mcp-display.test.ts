import { afterEach, describe, expect, it } from "vitest";

import {
  clearPersonalMcpDisplayNames,
  personalMcpDisplayName,
  resolvePersonalMcpDisplayName,
  setPersonalMcpDisplayNames,
} from "./personal-mcp-display";

const ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
const ALIAS = `personal_${ID}`;

describe("personal-mcp-display", () => {
  afterEach(() => {
    clearPersonalMcpDisplayNames();
  });

  it("resolves a registered alias back to the display name", () => {
    setPersonalMcpDisplayNames([{ id: ID, displayName: "我的搜索服务" }]);

    expect(personalMcpDisplayName(ALIAS)).toBe("我的搜索服务");
    expect(personalMcpDisplayName(ALIAS.toUpperCase())).toBe("我的搜索服务");
    expect(personalMcpDisplayName(`personal_${ID.toUpperCase()}`)).toBe("我的搜索服务");
  });

  it("replaces personal_<id> segments inside tool-style names", () => {
    setPersonalMcpDisplayNames([{ id: ID, displayName: "我的搜索服务" }]);

    expect(resolvePersonalMcpDisplayName(`mcp.${ALIAS}.connect`)).toBe("mcp.我的搜索服务.connect");
    expect(resolvePersonalMcpDisplayName(`mcp.${ALIAS}.search_docs`)).toBe("mcp.我的搜索服务.search_docs");
    expect(resolvePersonalMcpDisplayName(ALIAS)).toBe("我的搜索服务");
  });

  it("keeps unknown aliases and unrelated text unchanged", () => {
    setPersonalMcpDisplayNames([{ id: ID, displayName: "我的搜索服务" }]);

    expect(resolvePersonalMcpDisplayName("mcp.filesystem.read_file")).toBe("mcp.filesystem.read_file");
    expect(resolvePersonalMcpDisplayName(`mcp.personal_${'b'.repeat(32)}.connect`))
      .toBe(`mcp.personal_${'b'.repeat(32)}.connect`);
    expect(resolvePersonalMcpDisplayName("")).toBe("");
  });

  it("merges entries and ignores invalid ones", () => {
    setPersonalMcpDisplayNames([{ id: ID, displayName: "旧名称" }]);
    setPersonalMcpDisplayNames([
      { id: ID, displayName: "新名称" },
      { id: "not-a-32-hex-id", displayName: "无效 ID" },
      { id: "b".repeat(32), displayName: "  " },
    ]);

    expect(personalMcpDisplayName(ALIAS)).toBe("新名称");
    expect(personalMcpDisplayName(`personal_${'b'.repeat(32)}`)).toBeUndefined();
  });

  it("returns undefined before any entry is registered", () => {
    expect(personalMcpDisplayName(ALIAS)).toBeUndefined();
    expect(resolvePersonalMcpDisplayName(`mcp.${ALIAS}.connect`)).toBe(`mcp.${ALIAS}.connect`);
  });
});
