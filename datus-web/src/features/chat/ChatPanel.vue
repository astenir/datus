<script setup lang="ts">
import { computed, shallowRef } from "vue"
import type { ChatStatus } from "ai"
import { Loader2Icon, PlusIcon, SquareIcon } from "@lucide/vue"
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
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { dashboardApi, reportApi } from "@/lib/api"
import { activeStreamingMessageId, mergeToolExecutionMessages } from "@/lib/chat"
import { useConnection } from "@/composables/useConnection"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import ChatMessageItem from "@/features/chat/ChatMessageItem.vue"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const displayMessages = computed(() => mergeToolExecutionMessages(props.workspace.messages.value))
const currentStatus = computed<ChatStatus>(() => props.workspace.isStreaming.value ? "streaming" : "ready")
const streamingMessageId = computed(() =>
  props.workspace.isStreaming.value ? activeStreamingMessageId(props.workspace.messages.value) : null,
)
const schemaOptions = computed(() => props.workspace.schemaOptions.value)
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

function openArtifact(kind: string, slug: string) {
  const base = effectiveBase()
  const url = kind === "report"
    ? reportApi.htmlUrl(base, slug)
    : dashboardApi.htmlUrl(base, slug)
  window.open(url, "_blank", "noopener,noreferrer")
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
          @submit-interaction="submitInteraction"
          @open-artifact="openArtifact"
        />
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>

    <footer class="shrink-0 px-4 pb-5 pt-3 md:px-8 md:pb-7">
      <div class="mx-auto max-w-[52rem]">
        <div
          v-if="workspace.isLoadingModels.value || workspace.isLoadingCatalog.value"
          class="mb-2 flex items-center justify-center gap-2 text-xs text-muted-foreground"
        >
          <Loader2Icon class="size-3 animate-spin" />
          <span>正在刷新模型或数据目录</span>
        </div>

        <PromptInput
          class="[&_[data-slot=input-group]]:min-h-32 [&_[data-slot=input-group]]:rounded-[30px] [&_[data-slot=input-group]]:border [&_[data-slot=input-group]]:border-ring/35 [&_[data-slot=input-group]]:bg-background [&_[data-slot=input-group]]:shadow-2xl [&_[data-slot=input-group]]:shadow-muted"
          @submit="send"
        >
          <PromptInputBody>
            <PromptInputTextarea
              placeholder="发消息..."
              class="min-h-16 px-5 pt-5 text-sm"
            />
          </PromptInputBody>
          <Separator />
          <PromptInputFooter class="flex-wrap px-4 py-3">
            <PromptInputTools class="min-w-0 flex-wrap gap-1.5">
              <PromptInputButton
                size="sm"
                type="button"
                class="text-sm"
                @click="workspace.clearMessages"
              >
                <PlusIcon data-icon="inline-start" />
                新会话
              </PromptInputButton>

              <PromptInputButton
                v-if="workspace.isStreaming.value"
                variant="outline"
                size="sm"
                type="button"
                class="text-sm"
                @click="workspace.stopSession"
              >
                <SquareIcon data-icon="inline-start" />
                停止
              </PromptInputButton>

              <Select v-model="workspace.selectedAgent.value">
                <SelectTrigger class="h-9 w-36 rounded-full text-sm">
                  <SelectValue placeholder="Agent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="agent in workspace.agentOptions.value"
                      :key="agent.value"
                      :value="agent.value"
                      class="text-sm"
                    >
                      {{ agent.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

              <Select v-model="workspace.selectedModel.value">
                <SelectTrigger class="hidden h-9 w-44 rounded-full text-sm sm:inline-flex">
                  <SelectValue :placeholder="workspace.defaultModelLabel.value || 'Model'" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="model in workspace.modelOptions.value"
                      :key="model.value"
                      :value="model.value"
                      class="text-sm"
                    >
                      {{ model.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

              <Select
                :model-value="workspace.database.value"
                @update:model-value="(value) => workspace.setDatabase(String(value))"
              >
                <SelectTrigger class="hidden h-9 w-40 rounded-full text-sm lg:inline-flex">
                  <SelectValue placeholder="Database" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="database in workspace.databaseOptions.value"
                      :key="database.value"
                      :value="database.value"
                      class="text-sm"
                    >
                      {{ database.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

              <Select
                :model-value="workspace.schema.value"
                @update:model-value="(value) => workspace.setSchema(String(value))"
              >
                <SelectTrigger class="hidden h-9 w-36 rounded-full text-sm xl:inline-flex">
                  <SelectValue placeholder="Schema" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="schema in schemaOptions"
                      :key="schema.value"
                      :value="schema.value"
                      class="text-sm"
                    >
                      {{ schema.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </PromptInputTools>
            <PromptInputSubmit :status="currentStatus" />
          </PromptInputFooter>
        </PromptInput>
      </div>
    </footer>
  </section>
</template>
