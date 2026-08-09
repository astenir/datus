<script setup lang="ts">
import { useRouter } from "vue-router"
import { useChatPanelActions } from "@/composables/useChatPanelActions"
import { useChatPanelDisplay } from "@/composables/useChatPanelDisplay"
import { usePermission } from "@/composables/usePermission"
import { useSuccessStory } from "@/composables/useSuccessStory"
import type { ArtifactViewTab } from "@/features/workspace/types"
import type { ChatWorkspaceChatContract } from "@/features/workspace/workspace-contracts"
import ChatComposerArea from "@/features/chat/ChatComposerArea.vue"
import ChatConversationArea from "@/features/chat/ChatConversationArea.vue"
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
const display = useChatPanelDisplay({
  workspace: props.workspace,
  router,
  permission: {
    isAdmin: () => permission.isAdmin(),
    hasPermission: (permissionCode) => permission.hasPermission(permissionCode),
  },
})

function emitOpenArtifact(tab: ArtifactViewTab, slug: string) {
  emit("openArtifact", tab, slug)
}

function saveSuccessStorySource(source: SuccessStorySource) {
  void successStory.save(source)
}

const actions = useChatPanelActions({
  workspace: props.workspace,
  activeInteraction: display.activeInteraction,
  onOpenArtifact: emitOpenArtifact,
  onSaveSuccessStory: saveSuccessStorySource,
})

const {
  displayMessages,
  activeTodoExecution,
  streamingMessageId,
  canSaveSuccessStory,
  successStorySessionLink,
  activeInteractionKey,
  dockedInteraction,
} = display
const {
  pendingInteractionKey,
  send,
  sendSuggestion,
  selectModel,
  updateAgent,
  submitInteraction,
  openArtifact,
  saveSuccessStory,
} = actions
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
