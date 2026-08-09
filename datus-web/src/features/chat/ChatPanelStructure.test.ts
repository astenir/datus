import { describe, expect, it } from "vitest"

import composerSource from "./ChatComposerArea.vue?raw"
import conversationSource from "./ChatConversationArea.vue?raw"
import panelSource from "./ChatPanel.vue?raw"

describe("ChatPanel presentation boundaries", () => {
  it("keeps the panel focused on workspace coordination", () => {
    expect(panelSource).toContain("<ChatConversationArea")
    expect(panelSource).toContain("<ChatComposerArea")
    expect(panelSource).toContain("shouldExitPlanModeAfterInteraction")
    expect(panelSource).toContain('emit("openArtifact", tab, slug)')
    expect(panelSource).not.toContain("<Conversation")
    expect(panelSource).not.toContain("<PromptInput")
    expect(panelSource).not.toContain("<ModelSelector")
  })

  it("keeps conversation rendering and composer controls in their feature sections", () => {
    expect(conversationSource).toContain("<ConversationContent")
    expect(conversationSource).toContain("<ChatMessageItem")
    expect(conversationSource).toContain("<ChatActivityStatus")
    expect(conversationSource).toContain('emit("submitInteraction"')

    expect(composerSource).toContain("<PromptInput")
    expect(composerSource).toContain("<ChatMoreSettingsMenu")
    expect(composerSource).toContain("<ChatContextPicker")
    expect(composerSource).toContain("<ModelSelector")
    expect(composerSource).toContain('emit("selectModel"')
  })
})
