<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { ChevronDownIcon, CpuIcon, Loader2Icon, SquareIcon } from "@lucide/vue"
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorShortcut,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector"
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
import ChatMoreSettingsMenu from "@/features/chat/ChatMoreSettingsMenu.vue"
import TodoExecutionDock from "@/features/chat/TodoExecutionDock.vue"
import type { ActiveUserInteraction, SelectOption } from "@/types"
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

const DEFAULT_MODEL_VALUE = "__datus_default_model__"

type ModelOptionGroup = {
  provider: string
  label: string
  options: SelectOption[]
}

const modelSelectorOpen = shallowRef(false)
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
const selectedModelValue = computed(() =>
  props.workspace.selectedModel.value || DEFAULT_MODEL_VALUE,
)
const defaultModelLabel = computed(() =>
  props.workspace.defaultModelLabel.value ? `默认：${props.workspace.defaultModelLabel.value}` : "默认模型",
)
const selectedModelLabel = computed(() =>
  optionLabel(props.workspace.selectedModel.value, props.workspace.modelOptions.value),
)
const modelTriggerLabel = computed(() => selectedModelLabel.value || defaultModelLabel.value)
const modelOptionGroups = computed(() => groupModelOptions(props.workspace.modelOptions.value))
const modelSelectorContentClass = [
  "gap-0 overflow-hidden rounded-2xl border-border/70 shadow-2xl sm:max-w-md",
  "[&_[data-slot=command]]:rounded-2xl [&_[data-slot=command]]:p-1",
  "[&_[data-slot=command-input-wrapper]]:p-1 [&_[data-slot=command-input-wrapper]]:pb-1",
  "[&_[data-slot=input-group]]:h-9 [&_[data-slot=input-group]]:rounded-xl",
  "[&_[data-slot=command-group]]:p-1",
  "[&_[data-slot=command-group-heading]]:px-2.5 [&_[data-slot=command-group-heading]]:py-1.5",
].join(" ")

function handleSubmit(payload: PromptInputMessage) {
  emit("submit", payload)
}

function handleInteractionSubmit(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function selectModel(value: string) {
  emit("selectModel", value)
  modelSelectorOpen.value = false
}

function optionLabel(value: string, options: readonly SelectOption[]): string {
  if (!value) return ""
  return options.find(option => option.value === value)?.label ?? value
}

function providerKey(option: SelectOption): string {
  if (option.group) return option.group
  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim().toLowerCase()

  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim().toLowerCase()

  return "other"
}

function providerLabel(option: SelectOption): string {
  if (option.group) return option.group
  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim()

  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim()

  return "其他模型"
}

function groupModelOptions(options: readonly SelectOption[]): ModelOptionGroup[] {
  const groups = new Map<string, ModelOptionGroup>()

  for (const option of options) {
    const key = providerKey(option)
    const group = groups.get(key)

    if (group) {
      group.options.push(option)
      continue
    }

    groups.set(key, {
      provider: key,
      label: providerLabel(option),
      options: [option],
    })
  }

  return Array.from(groups.values())
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

            <ModelSelector v-model:open="modelSelectorOpen">
              <ModelSelectorTrigger as-child>
                <PromptInputButton
                  type="button"
                  aria-label="选择 Model"
                  title="Model"
                  :disabled="workspace.isLoadingModels.value"
                  class="h-8 max-w-44 justify-start rounded-full px-2 text-sm sm:max-w-56"
                >
                  <Loader2Icon
                    v-if="workspace.isLoadingModels.value"
                    data-icon="inline-start"
                    class="animate-spin"
                  />
                  <CpuIcon
                    v-else
                    data-icon="inline-start"
                  />
                  <span class="truncate">{{ modelTriggerLabel }}</span>
                  <ChevronDownIcon data-icon="inline-end" />
                </PromptInputButton>
              </ModelSelectorTrigger>

              <ModelSelectorContent
                title="选择模型"
                :show-close-button="false"
                :class="modelSelectorContentClass"
              >
                <ModelSelectorInput
                  placeholder="搜索模型..."
                  class="h-9 py-0"
                />
                <ModelSelectorList class="max-h-80 px-1 pb-1">
                  <ModelSelectorEmpty class="py-6 text-sm">
                    没有匹配的模型
                  </ModelSelectorEmpty>

                  <ModelSelectorGroup heading="默认">
                    <ModelSelectorItem
                      :value="DEFAULT_MODEL_VALUE"
                      class="min-h-9 rounded-xl px-2.5 py-1.5"
                      @select.prevent="selectModel(DEFAULT_MODEL_VALUE)"
                    >
                      <CpuIcon data-icon="inline-start" />
                      <ModelSelectorName>
                        {{ defaultModelLabel }}
                      </ModelSelectorName>
                      <ModelSelectorShortcut v-if="selectedModelValue === DEFAULT_MODEL_VALUE">
                        当前
                      </ModelSelectorShortcut>
                    </ModelSelectorItem>
                  </ModelSelectorGroup>

                  <ModelSelectorGroup
                    v-for="group in modelOptionGroups"
                    :key="group.provider"
                    :heading="group.label"
                  >
                    <ModelSelectorItem
                      v-for="model in group.options"
                      :key="model.value"
                      :value="model.value"
                      class="min-h-9 rounded-xl px-2.5 py-1.5"
                      @select.prevent="selectModel(model.value)"
                    >
                      <CpuIcon data-icon="inline-start" />
                      <ModelSelectorName>
                        {{ model.label }}
                      </ModelSelectorName>
                      <ModelSelectorShortcut v-if="selectedModelValue === model.value">
                        当前
                      </ModelSelectorShortcut>
                    </ModelSelectorItem>
                  </ModelSelectorGroup>
                </ModelSelectorList>
              </ModelSelectorContent>
            </ModelSelector>

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
