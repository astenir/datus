<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { toast } from "vue-sonner"
import { useRouter } from "vue-router"
import {
  activeStreamingMessageId,
  activeUserInteractionRequest,
  mergeToolExecutionMessages,
  shouldExitPlanModeAfterInteraction,
} from "@/lib/chat"
import { parsePermissionRequest } from "@/lib/interaction-display"
import { usePermission } from "@/composables/usePermission"
import { useSuccessStory } from "@/composables/useSuccessStory"
import { workspaceRouteNames } from "@/features/workspace/types"
import type { ArtifactViewTab } from "@/features/workspace/types"
import type { ChatWorkspaceChatContract } from "@/features/workspace/workspace-contracts"
import ChatComposerArea from "@/features/chat/ChatComposerArea.vue"
import ChatConversationArea from "@/features/chat/ChatConversationArea.vue"
import { deriveTodoExecutionDisplay } from "@/lib/todo-execution"
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input/types"
import type { SuccessStorySource } from "@/types"

const props = defineProps<{
  workspace: ChatWorkspaceChatContract
}>()
const emit = defineEmits<{
  openArtifact: [tab: ArtifactViewTab, slug: string]
}>()

const router = useRouter()
const permission = usePermission()
const successStory = useSuccessStory()
const DEFAULT_MODEL_VALUE = "__datus_default_model__"

const todoDisplay = computed(() => deriveTodoExecutionDisplay(
  mergeToolExecutionMessages(props.workspace.messages.value),
  { isStreaming: props.workspace.isStreaming.value },
))
const displayMessages = computed(() => todoDisplay.value.messages)
const activeTodoExecution = computed(() => todoDisplay.value.activeExecution)
const streamingMessageId = computed(() =>
  props.workspace.isStreaming.value ? activeStreamingMessageId(props.workspace.messages.value) : null,
)
const canSaveSuccessStory = computed(() => permission.isAdmin() || permission.hasPermission("module.kb"))
const successStorySessionLink = computed(() => {
  const sessionId = props.workspace.selectedSession.value
  if (!sessionId) return undefined
  return router.resolve({
    name: workspaceRouteNames.chatSession,
    params: { sessionId },
  }).href
})
const activeInteractionKey = computed(() => props.workspace.activeInteractionKey.value)
const activeInteraction = computed(() =>
  activeUserInteractionRequest(props.workspace.messages.value, activeInteractionKey.value),
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
const pendingInteractionKey = shallowRef<string | null>(null)

async function send(payload: PromptInputMessage): Promise<void> {
  const text = payload.text.trim()
  if (!text) return

  if (!props.workspace.isStreaming.value) {
    props.workspace.handleSend(text)
    return
  }

  try {
    const result = await props.workspace.handleInsert(text)
    const queueHint = result.queued_count > 0 ? `（队列中 ${result.queued_count} 条）` : ""
    toast.success(`已加入当前任务${queueHint}`)
  } catch (error) {
    console.error("Failed to insert message:", error)
    toast.error("未能加入当前任务，请重试")
    throw error
  }
}

function sendSuggestion(suggestion: string) {
  props.workspace.handleSend(suggestion)
}

function selectModel(value: string) {
  props.workspace.selectedModel.value = value === DEFAULT_MODEL_VALUE ? "" : value
}

function updateAgent(value: string) {
  props.workspace.selectedAgent.value = value
}

async function submitInteraction(interactionKey: string, answers: string[][]) {
  if (pendingInteractionKey.value) return

  const exitsPlanMode = shouldExitPlanModeAfterInteraction(
    activeInteraction.value,
    interactionKey,
    answers,
  )

  pendingInteractionKey.value = interactionKey
  try {
    await props.workspace.sendInteraction(interactionKey, answers)
    if (exitsPlanMode) props.workspace.setPlanMode(false)
  } catch (error) {
    console.error("Failed to submit interaction:", error)
    toast.error("提交交互失败，请重试")
  } finally {
    pendingInteractionKey.value = null
  }
}

function openArtifact(kind: string, slug: string) {
  const tab: ArtifactViewTab = kind === "report" ? "report" : "dashboard"
  emit("openArtifact", tab, slug)
}

function saveSuccessStory(source: SuccessStorySource) {
  void successStory.save(source)
}
</script>

<template>
  <section class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
    <ChatConversationArea
      :display-messages="displayMessages"
      :is-streaming="workspace.isStreaming.value"
      :streaming-message-id="streamingMessageId"
      :interaction-pending="Boolean(pendingInteractionKey)"
      :active-interaction-key="activeInteractionKey"
      :docked-interaction-key="dockedInteraction?.interactionKey ?? null"
      :datasource-name="workspace.currentDatasource.value"
      :datasource-options="workspace.visibleDatasourceOptions.value"
      :database-name="workspace.database.value"
      :success-story-session-id="workspace.selectedSession.value ?? undefined"
      :success-story-session-link="successStorySessionLink"
      :can-save-success-story="canSaveSuccessStory"
      :success-story-version="successStory.version.value"
      :is-success-story-saving="successStory.isSaving"
      :is-success-story-saved="successStory.isSaved"
      :active-todo-execution="activeTodoExecution"
      :stream-activity="workspace.streamActivity.value"
      @send-suggestion="sendSuggestion"
      @submit-interaction="submitInteraction"
      @open-artifact="openArtifact"
      @save-success-story="saveSuccessStory"
      @stop="workspace.stopSession"
    />

    <ChatComposerArea
      :workspace="workspace"
      :active-todo-execution="activeTodoExecution"
      :docked-interaction="dockedInteraction"
      :interaction-pending="Boolean(pendingInteractionKey)"
      @submit="send"
      @dismiss-error="workspace.clearTransportError"
      @stop="workspace.stopSession"
      @submit-interaction="submitInteraction"
      @select-model="selectModel"
      @update-agent="updateAgent"
      @set-default-agent="workspace.setDefaultAgent"
      @request-agents="workspace.loadAgentOptions"
      @toggle-mcp="workspace.personalMcp.toggleSelection"
      @update-datasource="workspace.handleDatasourceSwitch"
      @update-database="workspace.setDatabase"
      @update-schema="workspace.setSchema"
      @request-catalog="workspace.ensureCatalogLoaded"
    />
  </section>
</template>
