<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { Loader2Icon, PlusIcon, SquareIcon } from "@lucide/vue"
import { toast } from "vue-sonner"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input"
import type { PromptInputMessage } from "@/components/ai-elements/prompt-input/types"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { mergeToolExecutionMessages } from "@/lib/chat"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import ChatMessageItem from "@/features/chat/ChatMessageItem.vue"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const displayMessages = computed(() => mergeToolExecutionMessages(props.workspace.messages.value))
const currentStatus = computed(() => props.workspace.isStreaming.value ? "streaming" : "ready")
const schemaOptions = computed(() => props.workspace.schemaOptions.value)
const pendingInteractionKey = shallowRef<string | null>(null)

function send(payload: PromptInputMessage) {
  const text = payload.text.trim()
  if (!text) return
  props.workspace.handleSend(text)
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
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col">
    <header class="flex flex-wrap items-center gap-3 border-b px-4 py-3">
      <Button
        variant="outline"
        size="sm"
        @click="workspace.clearMessages"
      >
        <PlusIcon data-icon="inline-start" />
        新会话
      </Button>

      <Select v-model="workspace.selectedAgent.value">
        <SelectTrigger class="w-40">
          <SelectValue placeholder="Agent" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="agent in workspace.agentOptions.value"
              :key="agent.value"
              :value="agent.value"
            >
              {{ agent.label }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>

      <Select v-model="workspace.selectedModel.value">
        <SelectTrigger class="w-48">
          <SelectValue :placeholder="workspace.defaultModelLabel.value || 'Model'" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="model in workspace.modelOptions.value"
              :key="model.value"
              :value="model.value"
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
        <SelectTrigger class="w-44">
          <SelectValue placeholder="Database" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="database in workspace.databaseOptions.value"
              :key="database.value"
              :value="database.value"
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
        <SelectTrigger class="w-40">
          <SelectValue placeholder="Schema" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="schema in schemaOptions"
              :key="schema.value"
              :value="schema.value"
            >
              {{ schema.label }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>

      <div class="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon
          v-if="workspace.isLoadingModels.value || workspace.isLoadingCatalog.value"
          class="size-4 animate-spin"
        />
        <span>{{ displayMessages.length }} messages</span>
      </div>
    </header>

    <Conversation class="min-h-0">
      <ConversationContent class="gap-5 px-5 py-6">
        <ConversationEmptyState
          v-if="displayMessages.length === 0"
          title="Datus"
          description="Ask a question against the configured datasource."
        />
        <ChatMessageItem
          v-for="message in displayMessages"
          v-else
          :key="message.id"
          :message="message"
          :streaming="workspace.isStreaming.value"
          :interaction-disabled="Boolean(pendingInteractionKey)"
          @submit-interaction="submitInteraction"
        />
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>

    <footer class="border-t p-4">
      <PromptInput
        class="mx-auto max-w-4xl"
        @submit="send"
      >
        <PromptInputBody>
          <PromptInputTextarea placeholder="输入问题，Enter 发送，Shift+Enter 换行" />
        </PromptInputBody>
        <Separator />
        <PromptInputFooter>
          <PromptInputTools>
            <Button
              v-if="workspace.isStreaming.value"
              variant="outline"
              size="sm"
              type="button"
              @click="workspace.stopSession"
            >
              <SquareIcon data-icon="inline-start" />
              停止
            </Button>
          </PromptInputTools>
          <PromptInputSubmit :status="currentStatus as never" />
        </PromptInputFooter>
      </PromptInput>
    </footer>
  </section>
</template>
