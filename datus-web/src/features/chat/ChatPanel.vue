<script setup lang="ts">
import { computed, defineAsyncComponent, shallowRef } from "vue"
import type { ChatStatus } from "ai"
import { ChevronDownIcon, CpuIcon, Loader2Icon, SquareIcon } from "@lucide/vue"
import { toast } from "vue-sonner"
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
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
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion"
import { activeStreamingMessageId, mergeToolExecutionMessages } from "@/lib/chat"
import { useConnection } from "@/composables/useConnection"
import { artifactHtml, createArtifactPreviewUrl } from "@/composables/useArtifacts"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { ArtifactViewTab } from "@/features/workspace/types"
import type { SelectOption } from "@/types"
import ChatContextPicker from "@/features/chat/ChatContextPicker.vue"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const ChatMessageItem = defineAsyncComponent(() => import("@/features/chat/ChatMessageItem.vue"))
const DEFAULT_MODEL_VALUE = "__datus_default_model__"

type ModelOptionGroup = {
  provider: string
  label: string
  options: SelectOption[]
}

const displayMessages = computed(() => mergeToolExecutionMessages(props.workspace.messages.value))
const currentStatus = computed<ChatStatus>(() => props.workspace.isStreaming.value ? "streaming" : "ready")
const streamingMessageId = computed(() =>
  props.workspace.isStreaming.value ? activeStreamingMessageId(props.workspace.messages.value) : null,
)
const modelSelectorOpen = shallowRef(false)
const schemaOptions = computed(() => props.workspace.schemaOptions.value)
const selectedModelValue = computed({
  get: () => props.workspace.selectedModel.value || DEFAULT_MODEL_VALUE,
  set: (value: string) => {
    props.workspace.selectedModel.value = value === DEFAULT_MODEL_VALUE ? "" : value
  },
})
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
const pendingInteractionKey = shallowRef<string | null>(null)
const { effectiveBase } = useConnection()

const promptSuggestions = [
  "帮我分析基金持仓的关键变化",
  "列出当前数据源有哪些表",
  "运行 SQL 查询近 10 条记录",
  "查看 MCP 工具连接状态",
  "生成一份数据质量检查思路",
  "帮我总结这个会话的重点",
]

function send(payload: PromptInputMessage) {
  const text = payload.text.trim()
  if (!text) return
  props.workspace.handleSend(text)
}

function sendSuggestion(suggestion: string) {
  props.workspace.handleSend(suggestion)
}

function optionLabel(value: string, options: readonly SelectOption[]) {
  if (!value) return ""
  return options.find((option) => option.value === value)?.label ?? value
}

function providerKey(option: SelectOption) {
  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim().toLowerCase()

  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim().toLowerCase()

  return "other"
}

function providerLabel(option: SelectOption) {
  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim()

  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim()

  return "其他模型"
}

function groupModelOptions(options: readonly SelectOption[]) {
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

function selectModel(value: string) {
  selectedModelValue.value = value
  modelSelectorOpen.value = false
}

async function submitInteraction(interactionKey: string, answers: string[][]) {
  if (pendingInteractionKey.value) return

  pendingInteractionKey.value = interactionKey
  try {
    await props.workspace.sendInteraction(interactionKey, answers)
  } catch (error) {
    console.error("Failed to submit interaction:", error)
    toast.error("提交交互失败，请重试")
  } finally {
    pendingInteractionKey.value = null
  }
}

async function openArtifact(kind: string, slug: string) {
  const tab: ArtifactViewTab = kind === "report" ? "report" : "dashboard"
  const previewWindow = window.open("about:blank", "_blank")
  if (previewWindow) {
    previewWindow.opener = null
  }

  try {
    const html = await artifactHtml(effectiveBase(), tab, slug)
    const url = createArtifactPreviewUrl(html)
    if (previewWindow) {
      previewWindow.location.href = url
      return
    }
    window.open(url, "_blank", "noopener,noreferrer")
  } catch (error) {
    console.error("Failed to open artifact preview:", error)
    previewWindow?.close()
    toast.error("打开产物预览失败")
  }
}
</script>

<template>
  <section class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
    <div
      v-if="displayMessages.length === 0"
      class="flex min-h-0 w-full min-w-0 flex-1 flex-col items-center justify-center px-4 pb-28 pt-12 text-center md:pb-36"
    >
      <h1 class="max-w-full text-3xl font-bold leading-tight text-foreground md:text-4xl">
        有什么我能帮你的吗？
      </h1>

      <Suggestions class="mx-auto mt-8 flex w-full max-w-5xl flex-wrap justify-center gap-2 whitespace-normal px-1">
        <Suggestion
          v-for="(suggestion, index) in promptSuggestions"
          :key="suggestion"
          :suggestion="suggestion"
          variant="secondary"
          size="lg"
          :class="[
            'h-auto min-h-10 max-w-full rounded-2xl border-transparent bg-muted px-5 py-2.5 text-sm text-foreground hover:bg-muted/80 md:min-h-11',
            index > 1 ? 'hidden sm:inline-flex' : '',
          ]"
          @click="sendSuggestion"
        />
      </Suggestions>
    </div>

    <Conversation
      v-else
      class="min-h-0"
    >
      <ConversationContent class="gap-5 px-4 py-6 md:px-8">
        <ChatMessageItem
          v-for="message in displayMessages"
          :key="message.id"
          :message="message"
          :streaming="message.id === streamingMessageId"
          :interaction-disabled="Boolean(pendingInteractionKey)"
          :database-name="workspace.database.value"
          @submit-interaction="submitInteraction"
          @open-artifact="openArtifact"
        />
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>

    <footer class="shrink-0 px-4 pb-5 pt-3 md:px-8 md:pb-7">
      <div class="mx-auto max-w-[52rem]">
        <PromptInput
          :global-drop="false"
          :multiple="false"
          accept=""
          class="[&_[data-slot=input-group]]:min-h-28 [&_[data-slot=input-group]]:rounded-4xl [&_[data-slot=input-group]]:border [&_[data-slot=input-group]]:border-ring/30 [&_[data-slot=input-group]]:bg-background [&_[data-slot=input-group]]:shadow-xl [&_[data-slot=input-group]]:shadow-muted/70"
          @submit="send"
        >
          <PromptInputBody>
            <PromptInputTextarea
              name="message"
              aria-label="消息内容"
              placeholder="有什么想了解的？"
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
              <ChatContextPicker
                :datasource="workspace.currentDatasource.value"
                :database="workspace.database.value"
                :schema="workspace.schema.value"
                :selected-agent="workspace.selectedAgent.value"
                :datasource-options="workspace.visibleDatasourceOptions.value"
                :database-options="workspace.databaseOptions.value"
                :schema-options="schemaOptions"
                :agent-options="workspace.agentOptions.value"
                :loading-catalog="workspace.isLoadingCatalog.value"
                :switching-datasource="workspace.isLoadingCatalog.value"
                @update-datasource="workspace.handleDatasourceSwitch"
                @update-database="workspace.setDatabase"
                @update-schema="workspace.setSchema"
                @update-agent="(value) => { workspace.selectedAgent.value = value }"
              />
            </PromptInputTools>

            <div class="ml-auto flex min-w-0 shrink-0 items-center gap-1.5">
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
                v-if="!workspace.isStreaming.value"
                :status="currentStatus"
                :disabled="workspace.isStreaming.value"
                title="发送"
                class="size-10 shrink-0 rounded-full shadow-none"
              />
              <PromptInputButton
                v-else
                variant="default"
                size="icon-sm"
                type="button"
                aria-label="停止生成"
                title="停止生成"
                class="size-10 shrink-0 rounded-full shadow-none"
                @click="workspace.stopSession"
              >
                <SquareIcon />
              </PromptInputButton>
            </div>
          </PromptInputFooter>
        </PromptInput>
      </div>
    </footer>
  </section>
</template>
