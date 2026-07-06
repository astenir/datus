import { describe, expect, it } from "vitest";

import { canViewSubjectTree, type KnowledgePermissionAdapter } from "./knowledge-access";

function permissionAdapter(options: {
  modulePermission?: boolean;
  featurePermission?: boolean;
} = {}): KnowledgePermissionAdapter {
  return {
    hasPermission: (permission) => permission === "module.datasource_catalog" && options.modulePermission === true,
    hasFeaturePermission: (feature) => feature === "datasource_catalog" && options.featurePermission === true,
  };
}

describe("knowledge access", () => {
  it("allows subject-tree UI only with datasource catalog capability", () => {
    expect(canViewSubjectTree(permissionAdapter())).toBe(false);
    expect(canViewSubjectTree(permissionAdapter({ modulePermission: true }))).toBe(true);
    expect(canViewSubjectTree(permissionAdapter({ featurePermission: true }))).toBe(true);
  });
});
