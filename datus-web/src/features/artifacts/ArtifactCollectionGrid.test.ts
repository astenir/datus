import { renderToString } from "@vue/server-renderer";
import { createSSRApp } from "vue";
import { describe, expect, it } from "vitest";

import ArtifactCollectionGrid from "./ArtifactCollectionGrid.vue";
import type { ArtifactManifest } from "@/types";

async function renderGrid(items: ArtifactManifest[], loading = false): Promise<string> {
  const app = createSSRApp(ArtifactCollectionGrid, {
    items,
    emptyTitle: "暂无产物",
    loading,
    openingSlug: null,
    sharingSlug: null,
    editingSlug: null,
    editEnabled: true,
  });
  return renderToString(app);
}

describe("ArtifactCollectionGrid", () => {
  it("does not expose edit when the owner can share but lacks edit capability", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      can_manage_share: true,
      can_edit: false,
    }]);

    expect(html).toContain("分享");
    expect(html).not.toContain("编辑");
  });

  it("exposes edit when the backend grants artifact edit capability", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      can_manage_share: true,
      can_edit: true,
    }]);

    expect(html).toContain("编辑");
  });

  it("shows a loading state instead of the empty state during the initial request", async () => {
    const html = await renderGrid([], true);

    expect(html).toContain("正在加载产物列表...");
    expect(html).not.toContain("暂无产物");
    expect(html).not.toContain("当前后端没有返回可浏览的产物");
  });

  it("keeps existing cards visible while refreshing the list", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
    }], true);

    expect(html).toContain("Fund Overview");
    expect(html).toContain("正在刷新产物列表...");
    expect(html).not.toContain("暂无产物");
  });
});
