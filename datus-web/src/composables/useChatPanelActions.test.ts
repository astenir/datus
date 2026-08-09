import { shallowRef, type Ref } from "vue"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input/types"
import type { ActiveUserInteraction, SuccessStorySource } from "@/types"

import {
  useChatPanelActions,
  type ChatPanelActionWorkspaceContract,
} from "./useChatPanelActions"
import { toast } from "vue-sonner"

vi.mock("vue-sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function prompt(text: string): PromptInputMessage {
  return { text, files: [] }
}

type ChatPanelActionWorkspaceFixture = ChatPanelActionWorkspaceContract & {
  isStreaming: Ref<boolean>
}

function createWorkspace(): ChatPanelActionWorkspaceFixture {
  return {
    handleInsert: vi.fn(async () => ({ session_id: "session-1", queued_count: 1 })),
    handleSend: vi.fn(),
    isStreaming: shallowRef(false),
    selectedAgent: shallowRef(""),
    selectedModel: shallowRef(""),
    sendInteraction: vi.fn(async () => undefined),
    setPlanMode: vi.fn(),
  }
}

function createActions(workspace = createWorkspace(), activeInteraction = shallowRef<ActiveUserInteraction | null>(null)) {
  const onOpenArtifact = vi.fn()
  const onSaveSuccessStory = vi.fn<(source: SuccessStorySource) => void>()
  const actions = useChatPanelActions({
    workspace,
    activeInteraction,
    onOpenArtifact,
    onSaveSuccessStory,
  })
  return { actions, onOpenArtifact, onSaveSuccessStory }
}

describe("useChatPanelActions", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("sends a normal prompt after trimming it", async () => {
    const workspace = createWorkspace()
    const { actions } = createActions(workspace)

    await actions.send(prompt("  查询当前数据  "))

    expect(workspace.handleSend).toHaveBeenCalledWith("查询当前数据")
    expect(workspace.handleInsert).not.toHaveBeenCalled()
  })

  it("inserts a prompt while streaming and reports the queue size", async () => {
    const workspace = createWorkspace()
    workspace.isStreaming.value = true
    const { actions } = createActions(workspace)

    await actions.send(prompt("补充筛选条件"))

    expect(workspace.handleInsert).toHaveBeenCalledWith("补充筛选条件")
    expect(toast.success).toHaveBeenCalledWith("已加入当前任务（队列中 1 条）")
  })

  it("guards interaction submissions and exits plan mode after confirmation", async () => {
    let resolveInteraction: (() => void) | undefined
    const workspace = createWorkspace()
    workspace.sendInteraction = vi.fn(() => new Promise<void>((resolve) => {
      resolveInteraction = resolve
    }))
    const interaction: ActiveUserInteraction = {
      interactionKey: "plan-1",
      messageId: "plan-message",
      block: {
        type: "user-interaction",
        interactionKey: "plan-1",
        actionType: "confirm_plan",
        requests: [],
      },
    }
    const activeInteraction = shallowRef<ActiveUserInteraction | null>(interaction)
    const { actions } = createActions(workspace, activeInteraction)

    const submission = actions.submitInteraction("plan-1", [["confirm"]])
    expect(actions.pendingInteractionKey.value).toBe("plan-1")

    await actions.submitInteraction("plan-2", [["allow"]])
    expect(workspace.sendInteraction).toHaveBeenCalledTimes(1)

    resolveInteraction?.()
    await submission

    expect(workspace.sendInteraction).toHaveBeenCalledWith("plan-1", [["confirm"]])
    expect(workspace.setPlanMode).toHaveBeenCalledWith(false)
    expect(actions.pendingInteractionKey.value).toBeNull()
  })

  it("maps artifact events and forwards success story sources", () => {
    const { actions, onOpenArtifact, onSaveSuccessStory } = createActions()
    const source: SuccessStorySource = {
      sessionId: "session-1",
      callToolId: "call-1",
    }

    actions.openArtifact("report", "report-1")
    actions.openArtifact("unknown", "dashboard-1")
    actions.saveSuccessStory(source)

    expect(onOpenArtifact).toHaveBeenNthCalledWith(1, "report", "report-1")
    expect(onOpenArtifact).toHaveBeenNthCalledWith(2, "dashboard", "dashboard-1")
    expect(onSaveSuccessStory).toHaveBeenCalledWith(source)
  })
})
