import type { ArtifactVisibility } from "@/types"

export interface NormalizedArtifactShareGrants {
  allowedUserIds: string[]
  allowedRoleIds: string[]
}

export function normalizeArtifactShareGrants(
  visibility: ArtifactVisibility,
  allowedUserIds: readonly string[],
  allowedRoleIds: readonly string[],
): NormalizedArtifactShareGrants {
  const allowsExplicitAudience = visibility === "role"
  return {
    allowedUserIds: allowsExplicitAudience ? [...allowedUserIds] : [],
    allowedRoleIds: allowsExplicitAudience ? [...allowedRoleIds] : [],
  }
}
