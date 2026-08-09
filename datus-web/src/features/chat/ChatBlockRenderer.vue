<script setup lang="ts">
import type { BundledLanguage } from "shiki"
import { computed } from "vue"
import { CheckCircle2Icon, ExternalLinkIcon, WrenchIcon } from "@lucide/vue"
import {
  Artifact,
  ArtifactAction,
  ArtifactActions,
  ArtifactContent,
  ArtifactDescription,
  ArtifactHeader,
  ArtifactTitle,
} from "@/components/ai-elements/artifact"
import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockHeader,
  CodeBlockTitle,
} from "@/components/ai-elements/code-block"
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning"
import { MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import ChatErrorBlock from "@/features/chat/ChatErrorBlock.vue"
import InteractionSummaryBlock from "@/features/chat/InteractionSummaryBlock.vue"
import ChatCodeBlockCopyButton from "@/features/chat/ChatCodeBlockCopyButton.vue"
import ChatToolExecutionBlock from "@/features/chat/ChatToolExecutionBlock.vue"
import PlanConfirmationBlock from "@/features/chat/PlanConfirmationBlock.vue"
import PlanPreviewBlock from "@/features/chat/PlanPreviewBlock.vue"
import SubagentSummaryBlock from "@/features/chat/SubagentSummaryBlock.vue"
import TodoExecutionSummaryBlock from "@/features/chat/TodoExecutionSummaryBlock.vue"
import UserInteractionBlock from "@/features/chat/UserInteractionBlock.vue"
import { parsePermissionRequest } from "@/lib/interaction-display"
import { isToolDisplayBlock } from "@/lib/tool-presentation"
import type { MessageDisplayBlock, SelectOption, SuccessStorySource } from "@/types"

const props = defineProps<{
  block: MessageDisplayBlock
  streaming?: boolean
  executionActive?: boolean
  interactionDisabled?: boolean
  activeInteractionKey?: string | null
  dockedInteractionKey?: string | null
  datasourceName?: string
  datasourceOptions?: readonly SelectOption[]
  databaseName?: string
  successStorySessionId?: string
  successStorySessionLink?: string
  canSaveSuccessStory?: boolean
  successStoryVersion?: number
  isSuccessStorySaving?: (source: SuccessStorySource) => boolean
  isSuccessStorySaved?: (source: SuccessStorySource) => boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
  openArtifact: [kind: string, slug: string]
  saveSuccessStory: [source: SuccessStorySource]
}>()

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function openArtifact(kind: string, slug: string) {
  if (!slug) return
  emit("openArtifact", kind, slug)
}

function saveSuccessStory(source: SuccessStorySource) {
  emit("saveSuccessStory", source)
}

const toolBlock = computed(() => isToolDisplayBlock(props.block) ? props.block : null)

function codeLanguage(language: string) {
  return (language.trim().toLowerCase() || "text") as BundledLanguage
}

function artifactKindLabel(kind: string) {
  return kind === "report" ? "报表" : "仪表盘"
}

function artifactModeLabel(mode: string | undefined) {
  if (mode === "new") return "新建"
  if (mode === "edit") return "编辑"
  return mode ?? ""
}

function isDockedInteraction(block: MessageDisplayBlock) {
  return block.type === "user-interaction" &&
    Boolean(props.dockedInteractionKey) &&
    block.interactionKey === props.dockedInteractionKey
}

function isReadOnlyInteraction(block: MessageDisplayBlock) {
  return block.type === "user-interaction" &&
    block.interactionKey !== props.activeInteractionKey
}

function userInteractionSummary(block: MessageDisplayBlock) {
  if (block.type !== "user-interaction") return "用户交互"

  const request = block.requests[0]
  if (!request) return "用户交互"

  const permissionRequest = parsePermissionRequest(request.content)
  return permissionRequest?.operationName ?? permissionRequest?.toolName ?? request.title ?? request.content
}

function readOnlyInteractionDescription() {
  return props.executionActive ? "已提交，工具调用继续执行中" : "此交互请求已处理或已失效"
}
</script>

<template>
  <MessageResponse
    v-if="block.type === 'markdown'"
    :content="block.content"
    :streaming="streaming"
  />

  <PlanPreviewBlock
    v-else-if="block.type === 'plan-preview'"
    :content="block.content"
  />

  <PlanConfirmationBlock
    v-else-if="block.type === 'plan-confirmation'"
    :block="block"
    :active="Boolean(block.interaction && block.interaction.interactionKey === activeInteractionKey)"
    :pending="Boolean(interactionDisabled && block.interaction?.interactionKey === activeInteractionKey)"
    @submit="submitInteraction"
  />

  <ChatErrorBlock
    v-else-if="block.type === 'error'"
    :block="block"
  />

  <Reasoning
    v-else-if="block.type === 'thinking'"
    :is-streaming="streaming"
  >
    <ReasoningTrigger />
    <ReasoningContent :content="block.content" />
  </Reasoning>

  <CodeBlock
    v-else-if="block.type === 'code'"
    :code="block.content"
    :language="codeLanguage(block.language)"
  >
    <CodeBlockHeader>
      <CodeBlockTitle>{{ block.language }}</CodeBlockTitle>
      <CodeBlockActions>
        <ChatCodeBlockCopyButton :code="block.content" />
      </CodeBlockActions>
    </CodeBlockHeader>
  </CodeBlock>

  <TodoExecutionSummaryBlock
    v-else-if="block.type === 'todo-execution-summary'"
    :block="block"
  />

  <ChatToolExecutionBlock
    v-else-if="toolBlock"
    :block="toolBlock"
    :streaming="streaming"
    :execution-active="executionActive"
    :datasource-name="datasourceName"
    :datasource-options="datasourceOptions"
    :database-name="databaseName"
    :success-story-session-id="successStorySessionId"
    :success-story-session-link="successStorySessionLink"
    :can-save-success-story="canSaveSuccessStory"
    :is-success-story-saving="isSuccessStorySaving"
    :is-success-story-saved="isSuccessStorySaved"
    @save-success-story="saveSuccessStory"
  >
    <template #child-block="{ block: childBlock }">
      <ChatBlockRenderer
        :block="childBlock"
        :streaming="streaming"
        :execution-active="executionActive"
        :interaction-disabled="interactionDisabled"
        :active-interaction-key="activeInteractionKey"
        :docked-interaction-key="dockedInteractionKey"
        :datasource-name="datasourceName"
        :datasource-options="datasourceOptions"
        :database-name="databaseName"
        :success-story-session-id="successStorySessionId"
        :success-story-session-link="successStorySessionLink"
        :can-save-success-story="canSaveSuccessStory"
        :success-story-version="successStoryVersion"
        :is-success-story-saving="isSuccessStorySaving"
        :is-success-story-saved="isSuccessStorySaved"
        @submit-interaction="submitInteraction"
        @open-artifact="openArtifact"
        @save-success-story="saveSuccessStory"
      />
    </template>
  </ChatToolExecutionBlock>

  <SubagentSummaryBlock
    v-else-if="block.type === 'subagent-complete'"
    :block="block"
  />

  <Artifact
    v-else-if="block.type === 'artifact'"
  >
    <ArtifactHeader>
      <div class="min-w-0">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <ArtifactTitle class="truncate">
            {{ block.name }}
          </ArtifactTitle>
          <Badge variant="secondary">
            <CheckCircle2Icon data-icon="inline-start" />
            已生成
          </Badge>
        </div>
        <ArtifactDescription>
          {{ artifactKindLabel(block.kind) }}{{ block.mode ? ` · ${artifactModeLabel(block.mode)}` : "" }}
        </ArtifactDescription>
      </div>
      <ArtifactActions>
        <ArtifactAction
          :icon="ExternalLinkIcon"
          label="打开"
          tooltip="打开产物"
          @click="openArtifact(block.kind, block.slug)"
        />
      </ArtifactActions>
    </ArtifactHeader>
    <ArtifactContent class="text-sm text-muted-foreground">
      {{ block.description || block.slug }}
    </ArtifactContent>
  </Artifact>

  <div
    v-else-if="isDockedInteraction(block)"
    class="flex min-w-0 items-start gap-3 rounded-md border border-dashed bg-muted/20 p-3"
  >
    <Badge
      variant="secondary"
      class="shrink-0"
    >
      <WrenchIcon data-icon="inline-start" />
      等待确认
    </Badge>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium text-foreground">
        {{ userInteractionSummary(block) }}
      </p>
      <p class="text-xs text-muted-foreground">
        请在输入框上方处理此工具权限请求
      </p>
    </div>
  </div>

  <div
    v-else-if="isReadOnlyInteraction(block)"
    class="flex min-w-0 items-start gap-3 rounded-md border border-dashed bg-muted/20 p-3"
  >
    <Badge
      variant="secondary"
      class="shrink-0"
    >
      <CheckCircle2Icon data-icon="inline-start" />
      已处理
    </Badge>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium text-foreground">
        {{ userInteractionSummary(block) }}
      </p>
      <p class="text-xs text-muted-foreground">
        {{ readOnlyInteractionDescription() }}
      </p>
    </div>
  </div>

  <UserInteractionBlock
    v-else-if="block.type === 'user-interaction'"
    :block="block"
    :disabled="interactionDisabled || block.interactionKey !== activeInteractionKey"
    @submit="submitInteraction"
  />

  <InteractionSummaryBlock
    v-else-if="block.type === 'interaction-summary'"
    :block="block"
  />
</template>
