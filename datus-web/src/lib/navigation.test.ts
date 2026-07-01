import { describe, expect, it } from "vitest";

import {
  DEVELOPER_VIEW_FEATURES,
  PRIMARY_DEVELOPER_VIEWS,
  ROLE_FEATURE_OPTIONS,
  SETTINGS_TOOL_DEVELOPER_VIEWS,
  developerViewFeature,
  normalizeFeaturePermissionCode,
} from "./navigation";

describe("developer navigation permissions", () => {
  it("maps user-facing views to their feature permissions", () => {
    expect(developerViewFeature("chat")).toBe("chat");
    expect(developerViewFeature("sql")).toBe("sql_generation");
    expect(developerViewFeature("dashboard")).toBe("dashboard");
    expect(developerViewFeature("report")).toBe("report");
  });

  it("keeps management views behind the admin feature", () => {
    expect(DEVELOPER_VIEW_FEATURES.knowledge).toBe("admin");
    expect(DEVELOPER_VIEW_FEATURES.mcp).toBe("admin");
  });

  it("keeps user-facing outcomes in the primary sidebar", () => {
    expect(PRIMARY_DEVELOPER_VIEWS).toEqual(["chat", "report", "dashboard"]);
  });

  it("moves lower-frequency tools into settings", () => {
    expect(SETTINGS_TOOL_DEVELOPER_VIEWS).toEqual(["sql", "knowledge", "mcp"]);
  });

  it("uses backend feature codes when configuring roles", () => {
    expect(ROLE_FEATURE_OPTIONS.map((option) => option.value)).toEqual([
      "chat",
      "sql_generation",
      "report",
      "dashboard",
      "admin",
    ]);
  });

  it("normalizes legacy role feature codes to the codes checked by navigation", () => {
    expect(normalizeFeaturePermissionCode("sql")).toBe("sql_generation");
    expect(normalizeFeaturePermissionCode("knowledge")).toBe("admin");
    expect(normalizeFeaturePermissionCode("mcp")).toBe("admin");
    expect(normalizeFeaturePermissionCode("report")).toBe("report");
  });
});
