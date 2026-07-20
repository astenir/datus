import { renderToString } from "@vue/server-renderer";
import { createSSRApp } from "vue";
import { describe, expect, it } from "vitest";

import ArtifactCollectionGrid from "./ArtifactCollectionGrid.vue";
import type { ArtifactManifest } from "@/types";

async function renderGrid(item: ArtifactManifest): Promise<string> {
  const app = createSSRApp(ArtifactCollectionGrid, {
    items: [item],
    emptyTitle: "暂无产物",
    loading: false,
    openingSlug: null,
    sharingSlug: null,
    editingSlug: null,
    editEnabled: true,
  });
  return renderToString(app);
}

describe("ArtifactCollectionGrid", () => {
  it("does not expose edit when the owner can share but lacks edit capability", async () => {
    const html = await renderGrid({
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      can_manage_share: true,
      can_edit: false,
    });

    expect(html).toContain("分享");
    expect(html).not.toContain("编辑");
  });

  it("exposes edit when the backend grants artifact edit capability", async () => {
    const html = await renderGrid({
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      can_manage_share: true,
      can_edit: true,
    });

    expect(html).toContain("编辑");
  });
});
