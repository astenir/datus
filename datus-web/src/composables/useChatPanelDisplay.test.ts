import { shallowRef, type Ref } from "vue"
import { describe, expect, it, vi } from "vitest"

import type {
  ChatMessage,
  UserInteractionRequest,
} from "@/types"

import {
  useChatPanelDisplay,
  type ChatPanelDisplayWorkspaceContract,
  type ChatPanelPermissionContract,
  type ChatPanelRouterContract,
} from "./useChatPanelDisplay"

type ChatPanelDisplayWorkspaceFixture = ChatPanelDisplayWorkspaceContract & {
  activeInteractionKey: Ref<string | null>
  isStreaming: Ref<boolean>
  messages: Ref<readonly ChatMessage[]>
  selectedSession: Ref<string | null>
}

function createWorkspace(messages: readonly ChatMessage[] = []): ChatPanelDisplayWorkspaceFixture {
  return {
    activeInteractionKey: shallowRef<string | null>(null),
    isStreaming: shallowRef(false),
    messages: shallowRef<readonly ChatMessage[]>(messages),
    selectedSession: shallowRef<string | null>(null),
  }
}

function createPermission(overrides: Partial<ChatPanelPermissionContract> = {}): ChatPanelPermissionContract {
  return {
    isAdmin: () => false,
    hasPermission: () => false,
    ...overrides,
  }
}

function createRouter() {
  const resolve = vi.fn(({ params }: { name: string; params: { sessionId: string } }) => ({
    href: `/workspace/chat/${params.sessionId}`,
  }))
  const router: ChatPanelRouterContract = { resolve }
  return { resolve, router }
}

function permissionRequest(overrides: Partial<UserInteractionRequest> = {}): UserInteractionRequest {
  return {
    content: "Permission Request\nTool: filesystem.read_file\nArgs: /tmp/report.md",
    options: [
      { key: "allow", title: "允许" },
      { key: "deny", title: "拒绝" },
    ],
    allowFreeText: false,
    multiSelect: false,
    ...overrides,
  }
}

describe("useChatPanelDisplay", () => {
  it("derives streaming state, session links, and knowledge save access", () => {
    const workspace = createWorkspace([
      { id: "message-1", role: "assistant", content: "正在分析" },
    ])
    workspace.isStreaming.value = true
    workspace.selectedSession.value = "session-1"
    const { resolve, router } = createRouter()
    const permission = createPermission({ hasPermission: (code) => code === "module.kb" })

    const display = useChatPanelDisplay({ workspace, router, permission })

    expect(display.displayMessages.value).toEqual(workspace.messages.value)
    expect(display.streamingMessageId.value).toBe("message-1")
    expect(display.canSaveSuccessStory.value).toBe(true)
    expect(display.successStorySessionLink.value).toBe("/workspace/chat/session-1")
    expect(resolve).toHaveBeenCalledWith({
      name: "workspace-chat-session",
      params: { sessionId: "session-1" },
    })
  })

  it("only exposes a permission request in the compact dock", () => {
    const interactionKey = "permission-action-1"
    const workspace = createWorkspace([{
      id: "permission-message",
      role: "assistant",
      content: "需要确认",
      blocks: [{
        type: "user-interaction",
        interactionKey,
        actionType: "permission",
        requests: [permissionRequest()],
      }],
    }])
    workspace.isStreaming.value = true
    workspace.activeInteractionKey.value = interactionKey
    const { router } = createRouter()
    const display = useChatPanelDisplay({
      workspace,
      router,
      permission: createPermission(),
    })

    expect(display.activeInteraction.value?.interactionKey).toBe(interactionKey)
    expect(display.dockedInteraction.value?.messageId).toBe("permission-message")

    workspace.messages.value = [{
      id: "free-text-message",
      role: "assistant",
      content: "需要补充说明",
      blocks: [{
        type: "user-interaction",
        interactionKey,
        actionType: "permission",
        requests: [permissionRequest({ allowFreeText: true })],
      }],
    }]

    expect(display.activeInteraction.value?.messageId).toBe("free-text-message")
    expect(display.dockedInteraction.value).toBeNull()
  })
})
