import { describe, expect, it } from "vitest"

import { normalizeArtifactShareGrants } from "./artifactSharePolicy"

describe("normalizeArtifactShareGrants", () => {
  it("drops explicit users and roles for private visibility", () => {
    expect(normalizeArtifactShareGrants("private", ["viewer-1"], ["analyst"])).toEqual({
      allowedUserIds: [],
      allowedRoleIds: [],
    })
  })

  it("keeps explicit users and roles for role visibility", () => {
    expect(normalizeArtifactShareGrants("role", ["viewer-1"], ["analyst"])).toEqual({
      allowedUserIds: ["viewer-1"],
      allowedRoleIds: ["analyst"],
    })
  })

  it("drops explicit users and roles for enterprise visibility", () => {
    expect(normalizeArtifactShareGrants("enterprise", ["viewer-1"], ["analyst"])).toEqual({
      allowedUserIds: [],
      allowedRoleIds: [],
    })
  })
})
