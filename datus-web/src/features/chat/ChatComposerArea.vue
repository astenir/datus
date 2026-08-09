<script setup lang="ts">
import { computed } from "vue"
import { Loader2Icon, SquareIcon } from "@lucide/vue"
import {
  PromptInput,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input"
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input/types"
import type { ChatWorkspaceComposerContract } from "@/features/workspace/workspace-contracts"
import ActiveInteractionDock from "@/features/chat/ActiveInteractionDock.vue"
import ChatContextPicker from "@/features/chat/ChatContextPicker.vue"
import ChatErrorBlock from "@/features/chat/ChatErrorBlock.vue"
import ChatModelSelector from "@/features/chat/ChatModelSelector.vue"
import ChatMoreSettingsMenu from "@/features/chat/ChatMoreSettingsMenu.vue"
import TodoExecutionDock from "@/features/chat/TodoExecutionDock.vue"
import type { ActiveUserInteraction } from "@/types"
import type { TodoExecutionState } from "@/lib/todo-execution"

const props = defineProps<{
  workspace: ChatWorkspaceComposerContract
  activeTodoExecution: TodoExecutionState | null
  dockedInteraction: ActiveUserInteraction | null
  interactionPending: boolean
}>()

const emit = defineEmits<{
  submit: [payload: PromptInputMessage]
  dismissError: []
  stop: []
  submitInteraction: [interactionKey: string, answers: string[][]]
  selectModel: [value: string]
  updateAgent: [value: string]
  setDefaultAgent: [value: string]
  requestAgents: []
  toggleMcp: [mcpId: string]
  updateDatasource: [value: string]
  updateDatabase: [value: string]
  updateSchema: [value: string]
  requestCatalog: []
}>()

const isWaitingForSession = computed(() =>
  props.workspace.isStreaming.value && !props.workspace.isInsertReady.value,
)
const promptSubmitDisabled = computed(() =>
  isWaitingForSession.value || props.workspace.isStopping.value,
)
const promptSubmitLabel = computed(() => {
  if (props.workspace.isStopping.value) return "正在停止当前任务"
  if (isWaitingForSession.value) return "正在建立会话"
  return props.workspace.isStreaming.value ? "补充当前任务" : "发送"
})
const promptPlaceholder = computed(() => {
  if (!props.workspace.isStreaming.value) return "有什么想了解的？"
  if (props.workspace.isStopping.value) return "正在停止…"
  return isWaitingForSession.value ? "正在建立会话…" : "补充当前任务，按 Enter 发送"
})
const streamStatusLabel = computed(() => {
  if (props.workspace.isStopping.value) return "正在停止当前任务"
  return isWaitingForSession.value ? "正在建立会话" : "AI 正在生成，按 Enter 补充当前任务"
})
const stopButtonLabel = computed(() =>
  props.workspace.isStopping.value ? "正在停止当前任务" : "AI 正在生成，点击停止",
)
function handleSubmit(payload: PromptInputMessage) {
  emit("submit", payload)
}

function handleInteractionSubmit(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function selectModel(value: string) {
  emit("selectModel", value)
}

function handleUpdateAgent(value: string) {
  emit("updateAgent", value)
}

function handleSetDefaultAgent(value: string) {
  emit("setDefaultAgent", value)
}

function handleRequestAgents() {
  emit("requestAgents")
}

function handleToggleMcp(mcpId: string) {
  emit("toggleMcp", mcpId)
}

function handleUpdateDatasource(value: string) {
  emit("updateDatasource", value)
}

function handleUpdateDatabase(value: string) {
  emit("updateDatabase", value)
}

function handleUpdateSchema(value: string) {
  emit("updateSchema", value)
}

function handleRequestCatalog() {
  emit("requestCatalog")
}

function handleDismissError() {
  emit("dismissError")
}

function handleStop() {
  emit("stop")
}
</script>

<template>
  <footer class="shrink-0 px-4 pb-5 pt-3 md:px-8 md:pb-7">
    <div class="mx-auto max-w-[52rem]">
      <ChatErrorBlock
        v-if="workspace.transportError.value"
        :block="workspace.transportError.value"
        dismissible
        class="mb-3"
        @dismiss="handleDismissError"
      />

      <TodoExecutionDock
        :execution="activeTodoExecution"
        @stop="handleStop"
      />

      <ActiveInteractionDock
        :interaction="dockedInteraction"
        :disabled="interactionPending"
        @submit="handleInteractionSubmit"
      />

      <PromptInput
        :global-drop="false"
        :multiple="false"
        accept=""
        class="[&_[data-slot=input-group]]:min-h-28 [&_[data-slot=input-group]]:rounded-4xl [&_[data-slot=input-group]]:border [&_[data-slot=input-group]]:border-ring/30 [&_[data-slot=input-group]]:bg-background [&_[data-slot=input-group]]:shadow-xl [&_[data-slot=input-group]]:shadow-muted/70"
        @submit="handleSubmit"
      >
        <PromptInputBody>
          <PromptInputTextarea
            name="message"
            aria-label="消息内容"
            :placeholder="promptPlaceholder"
            :rows="2"
            autocomplete="off"
            autocapitalize="sentences"
            spellcheck="true"
            enterkeyhint="send"
            class="max-h-44 min-h-16 px-5 pt-5 text-sm leading-6"
          />
        </PromptInputBody>

        <PromptInputFooter class="flex-wrap items-center gap-2 px-3 py-3 sm:px-4">
          <PromptInputTools class="min-w-0 flex-1 flex-wrap items-center gap-1.5">
            <ChatMoreSettingsMenu
              :selected-agent="workspace.selectedAgent.value"
              :default-agent-id="workspace.defaultAgentId.value"
              :user-default-agent-id="workspace.userDefaultAgentId.value"
              :agent-options="workspace.agentOptions.value"
              :loading-agents="workspace.isLoadingAgents.value"
              :saving-default-agent="workspace.isSavingDefaultAgent.value"
              :agent-disabled="workspace.isStreaming.value"
              :show-personal-mcp="workspace.showPersonalMcpPicker.value"
              :servers="workspace.personalMcp.servers.value"
              :selected-ids="workspace.personalMcp.selectedIds.value"
              :mcp-locked="workspace.personalMcp.selectionLocked.value"
              :loading-mcp="workspace.personalMcp.loading.value || workspace.personalMcp.bindingLoading.value"
              :mcp-disabled="workspace.isStreaming.value && !workspace.personalMcp.selectionLocked.value"
              :max-selected="workspace.personalMcp.maxSelected.value"
              :agent-allows-personal-mcp="workspace.agentAllowsPersonalMcp.value"
              :organization-available="workspace.personalMcp.isAvailable.value"
              @update-agent="handleUpdateAgent"
              @set-default-agent="handleSetDefaultAgent"
              @request-agents="handleRequestAgents"
              @toggle-mcp="handleToggleMcp"
            />
            <ChatContextPicker
              :datasource="workspace.currentDatasource.value"
              :database="workspace.database.value"
              :schema="workspace.schema.value"
              :datasource-options="workspace.visibleDatasourceOptions.value"
              :datasource-statuses="workspace.datasourceStatuses.value"
              :database-options="workspace.databaseOptions.value"
              :schema-options="workspace.schemaOptions.value"
              :loading-catalog="workspace.isLoadingCatalog.value"
              :loading-databases="workspace.isLoadingDatabases.value"
              :loading-schemas="workspace.isLoadingSchemas.value"
              :switching-datasource="workspace.isPrewarmingCurrentDatasource.value"
              :disabled="workspace.isStreaming.value"
              @update-datasource="handleUpdateDatasource"
              @update-database="handleUpdateDatabase"
              @update-schema="handleUpdateSchema"
              @request-catalog="handleRequestCatalog"
            />
          </PromptInputTools>

          <div class="ml-auto flex min-w-0 shrink-0 items-center gap-1.5">
            <span
              v-if="workspace.isStreaming.value"
              role="status"
              aria-live="polite"
              class="sr-only"
            >
              {{ streamStatusLabel }}
            </span>

            <ChatModelSelector
              :model-options="workspace.modelOptions.value"
              :selected-model="workspace.selectedModel.value"
              :default-model-name="workspace.defaultModelLabel.value"
              :loading="workspace.isLoadingModels.value"
              @select-model="selectModel"
            />

            <PromptInputSubmit
              v-show="!workspace.isStreaming.value"
              status="ready"
              :disabled="promptSubmitDisabled"
              :aria-label="promptSubmitLabel"
              :title="promptSubmitLabel"
              class="size-10 shrink-0 rounded-full shadow-none"
            />
            <PromptInputButton
              v-if="workspace.isStreaming.value"
              variant="default"
              size="icon-sm"
              type="button"
              :disabled="workspace.isStopping.value"
              :aria-label="stopButtonLabel"
              :title="stopButtonLabel"
              class="size-10 shrink-0 rounded-full shadow-none"
              @click="handleStop"
            >
              <Loader2Icon
                v-if="workspace.isStopping.value"
                class="animate-spin"
              />
              <SquareIcon v-else />
            </PromptInputButton>
          </div>
        </PromptInputFooter>
      </PromptInput>
    </div>
  </footer>
</template>
