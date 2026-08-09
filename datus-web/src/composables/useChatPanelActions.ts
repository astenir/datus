import { shallowRef, type Ref } from "vue"
import { toast } from "vue-sonner"

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input/types"
import type { ActiveUserInteraction, SuccessStorySource } from "@/types"
import { shouldExitPlanModeAfterInteraction } from "@/lib/chat"
import type { ArtifactViewTab } from "@/features/workspace/types"
import type { ChatWorkspaceChatContract } from "@/features/workspace/workspace-contracts"

const DEFAULT_MODEL_VALUE = "__datus_default_model__"

export type ChatPanelActionWorkspaceContract = {
  handleInsert: ChatWorkspaceChatContract["handleInsert"]
  handleSend: ChatWorkspaceChatContract["handleSend"]
  isStreaming: Readonly<Ref<boolean>>
  selectedAgent: Ref<string>
  selectedModel: Ref<string>
  sendInteraction: ChatWorkspaceChatContract["sendInteraction"]
  setPlanMode: ChatWorkspaceChatContract["setPlanMode"]
}

export type ChatPanelActionOptions = {
  workspace: ChatPanelActionWorkspaceContract
  activeInteraction: Readonly<Ref<ActiveUserInteraction | null>>
  onOpenArtifact: (tab: ArtifactViewTab, slug: string) => void
  onSaveSuccessStory: (source: SuccessStorySource) => void
}

export function useChatPanelActions(options: ChatPanelActionOptions) {
  const pendingInteractionKey = shallowRef<string | null>(null)

  async function send(payload: PromptInputMessage): Promise<void> {
    const text = payload.text.trim()
    if (!text) return

    if (!options.workspace.isStreaming.value) {
      options.workspace.handleSend(text)
      return
    }

    try {
      const result = await options.workspace.handleInsert(text)
      const queueHint = result.queued_count > 0 ? `（队列中 ${result.queued_count} 条）` : ""
      toast.success(`已加入当前任务${queueHint}`)
    } catch (error) {
      console.error("Failed to insert message:", error)
      toast.error("未能加入当前任务，请重试")
      throw error
    }
  }

  function sendSuggestion(suggestion: string) {
    options.workspace.handleSend(suggestion)
  }

  function selectModel(value: string) {
    options.workspace.selectedModel.value = value === DEFAULT_MODEL_VALUE ? "" : value
  }

  function updateAgent(value: string) {
    options.workspace.selectedAgent.value = value
  }

  async function submitInteraction(interactionKey: string, answers: string[][]) {
    if (pendingInteractionKey.value) return

    const exitsPlanMode = shouldExitPlanModeAfterInteraction(
      options.activeInteraction.value,
      interactionKey,
      answers,
    )

    pendingInteractionKey.value = interactionKey
    try {
      await options.workspace.sendInteraction(interactionKey, answers)
      if (exitsPlanMode) options.workspace.setPlanMode(false)
    } catch (error) {
      console.error("Failed to submit interaction:", error)
      toast.error("提交交互失败，请重试")
    } finally {
      pendingInteractionKey.value = null
    }
  }

  function openArtifact(kind: string, slug: string) {
    const tab: ArtifactViewTab = kind === "report" ? "report" : "dashboard"
    options.onOpenArtifact(tab, slug)
  }

  function saveSuccessStory(source: SuccessStorySource) {
    options.onSaveSuccessStory(source)
  }

  return {
    pendingInteractionKey,
    send,
    sendSuggestion,
    selectModel,
    updateAgent,
    submitInteraction,
    openArtifact,
    saveSuccessStory,
  }
}
