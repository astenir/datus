import { describe, expect, it } from "vitest";

import viewerSource from "./ArtifactViewerFrame.vue?raw";
import artifactsPanelSource from "./ArtifactsPanel.vue?raw";
import chatSource from "../chat/ChatPanel.vue?raw";
import workspaceSource from "../workspace/DatusWorkspace.vue?raw";

describe("artifact preview security boundary", () => {
  it("keeps the embedded preview sandboxed with no referrer", () => {
    expect(viewerSource).toContain('sandbox="allow-scripts allow-downloads"');
    expect(viewerSource).not.toContain("allow-same-origin");
    expect(viewerSource).toContain('referrerpolicy="no-referrer"');
    expect(viewerSource).toContain('window.addEventListener("message", handleWindowMessage)');
    expect(viewerSource).toContain('window.removeEventListener("message", handleWindowMessage)');
    expect(viewerSource).toContain("previewController.abort()");
    expect(viewerSource).toContain("[props.url, props.dashboardSlug, props.query]");
    expect(viewerSource).toContain("artifactRenderErrorFromMessage");
  });

  it("routes render repair through a slug-locked edit session and the chat workspace", () => {
    expect(viewerSource).toContain("emit('repair', renderError)");
    expect(viewerSource).toContain("交给专用 Agent 修复");
    expect(viewerSource).not.toContain("clipboard");
    expect(artifactsPanelSource).toContain("artifacts.createArtifactEditSession(tab, normalizedSlug)");
    expect(artifactsPanelSource).toContain('emit("repair-artifact", session, artifactRepairPrompt');
    expect(workspaceSource).toContain('@repair-artifact="startArtifactRepair"');
    expect(workspaceSource).toContain("workspace.startArtifactEditSession(session)");
    expect(workspaceSource).toContain("workspace.handleSend(prompt)");
  });

  it("routes chat artifact clicks through the workspace instead of a blob window", () => {
    expect(chatSource).toContain('emit("openArtifact", tab, slug)');
    expect(chatSource).not.toContain("window.open(");
    expect(chatSource).not.toContain("getCurrentAccessToken");
    expect(workspaceSource).toContain('@open-artifact="openArtifactDetail"');
  });
});
