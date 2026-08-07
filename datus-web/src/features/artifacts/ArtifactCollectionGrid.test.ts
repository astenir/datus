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
  it("keeps artifact cards at a fixed width instead of stretching to three columns", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
    }]);

    expect(html).toContain("flex flex-wrap items-start gap-3");
    expect(html).toContain("h-52 w-80 max-w-full flex-none");
    expect(html).not.toContain("xl:grid-cols-3");
  });

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

  it("shows the artifact owner display name", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      owner_user_id: "owner-1",
      owner_display_name: "Owner User",
    }]);

    expect(html).toContain("作者");
    expect(html).toContain("Owner User");
    expect(html).toContain("作者：Owner User（owner-1）");
  });

  it("falls back to the owner id when the display name is unavailable", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      owner_user_id: "owner-1",
    }]);

    expect(html).toContain("owner-1");
    expect(html).toContain("作者：owner-1");
  });

  it("shows an honest fallback when the artifact has no owner metadata", async () => {
    const html = await renderGrid([{
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
    }]);

    expect(html).toContain("未知作者");
    expect(html).toContain("作者：未知");
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
