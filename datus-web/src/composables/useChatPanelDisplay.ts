import { computed, type Ref } from "vue"

import { activeStreamingMessageId, activeUserInteractionRequest, mergeToolExecutionMessages } from "@/lib/chat"
import { parsePermissionRequest } from "@/lib/interaction-display"
import { deriveTodoExecutionDisplay } from "@/lib/todo-execution"
import { workspaceRouteNames } from "@/features/workspace/types"
import type { ChatMessage } from "@/types"

export type ChatPanelDisplayWorkspaceContract = {
  activeInteractionKey: Readonly<Ref<string | null>>
  isStreaming: Readonly<Ref<boolean>>
  messages: Readonly<Ref<readonly ChatMessage[]>>
  selectedSession: Readonly<Ref<string | null>>
}

export type ChatPanelPermissionContract = {
  isAdmin: () => boolean
  hasPermission: (permissionCode: string) => boolean
}

export type ChatPanelRouterContract = {
  resolve: (to: { name: string; params: { sessionId: string } }) => { href: string }
}

export type ChatPanelDisplayOptions = {
  workspace: ChatPanelDisplayWorkspaceContract
  router: ChatPanelRouterContract
  permission: ChatPanelPermissionContract
}

export function useChatPanelDisplay(options: ChatPanelDisplayOptions) {
  const todoDisplay = computed(() => deriveTodoExecutionDisplay(
    mergeToolExecutionMessages(options.workspace.messages.value),
    { isStreaming: options.workspace.isStreaming.value },
  ))
  const displayMessages = computed(() => todoDisplay.value.messages)
  const activeTodoExecution = computed(() => todoDisplay.value.activeExecution)
  const streamingMessageId = computed(() =>
    options.workspace.isStreaming.value ? activeStreamingMessageId(options.workspace.messages.value) : null,
  )
  const canSaveSuccessStory = computed(() =>
    options.permission.isAdmin() || options.permission.hasPermission("module.kb"),
  )
  const successStorySessionLink = computed(() => {
    const sessionId = options.workspace.selectedSession.value
    if (!sessionId) return undefined
    return options.router.resolve({
      name: workspaceRouteNames.chatSession,
      params: { sessionId },
    }).href
  })
  const activeInteractionKey = computed(() => options.workspace.activeInteractionKey.value)
  const activeInteraction = computed(() =>
    activeUserInteractionRequest(options.workspace.messages.value, activeInteractionKey.value),
  )
  const dockedInteraction = computed(() => {
    const interaction = activeInteraction.value
    const requests = interaction?.block.requests ?? []
    const request = requests.length === 1 ? requests[0] : null
    if (!interaction || !request) return null
    if (request.allowFreeText || request.multiSelect || request.options.length === 0) return null
    if (!parsePermissionRequest(request.content)) return null

    return interaction
  })

  return {
    todoDisplay,
    displayMessages,
    activeTodoExecution,
    streamingMessageId,
    canSaveSuccessStory,
    successStorySessionLink,
    activeInteractionKey,
    activeInteraction,
    dockedInteraction,
  }
}
