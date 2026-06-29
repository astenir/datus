<script setup lang="ts">
import type { BundledLanguage } from "shiki"
import { ExternalLinkIcon } from "@lucide/vue"
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
  CodeBlockCopyButton,
  CodeBlockHeader,
  CodeBlockTitle,
} from "@/components/ai-elements/code-block"
import {
  Node,
  NodeContent,
  NodeDescription,
  NodeHeader,
  NodeTitle,
} from "@/components/ai-elements/node"
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning"
import {
  Tool,
  ToolContent,
  ToolHeader,
} from "@/components/ai-elements/tool"
import { MessageResponse } from "@/components/ai-elements/message"
import ToolPayloadView from "@/features/chat/ToolPayloadView.vue"
import UserInteractionBlock from "@/features/chat/UserInteractionBlock.vue"
import type { MessageDisplayBlock, ToolChildMessage } from "@/types"

defineProps<{
  block: MessageDisplayBlock
  streaming?: boolean
  thinkingDisplay?: "answer" | "reasoning"
  interactionDisabled?: boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
  openArtifact: [kind: string, slug: string]
}>()

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function openArtifact(kind: string, slug: string) {
  if (!slug) return
  emit("openArtifact", kind, slug)
}

function toolOutputState(errorText?: string) {
  return errorText ? "output-error" : "output-available"
}

function codeLanguage(language: string) {
  return (language.trim().toLowerCase() || "text") as BundledLanguage
}

function artifactKindLabel(kind: string) {
  return kind === "report" ? "报表" : "仪表盘"
}

function subagentSummary(block: Extract<MessageDisplayBlock, { type: "subagent-complete" }>) {
  const parts = []
  if (block.toolCount != null) parts.push(`${block.toolCount} tools`)
  if (block.duration != null) parts.push(`${block.duration.toFixed(2)}s`)
  return parts.join(" · ") || "已完成"
}

function childMessageLabel(message: ToolChildMessage) {
  if (message.role === "system") return "系统事件"
  if (message.role === "user") return "用户输入"
  return message.depth && message.depth > 0 ? "子 Agent" : "关联消息"
}
</script>

<template>
  <MessageResponse
    v-if="block.type === 'markdown'"
    :content="block.content"
  />

  <MessageResponse
    v-else-if="block.type === 'thinking' && thinkingDisplay === 'answer'"
    :content="block.content"
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
        <CodeBlockCopyButton />
      </CodeBlockActions>
    </CodeBlockHeader>
  </CodeBlock>

  <Tool v-else-if="block.type === 'tool-call'">
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      state="input-available"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolPayloadView
        mode="input"
        :tool-name="block.toolName"
        :value="block.params"
      />
      <div
        v-if="block.childMessages?.length"
        class="flex flex-col gap-3 border-t border-border/70 p-4"
      >
        <div
          v-for="child in block.childMessages"
          :key="child.id"
          class="flex flex-col gap-2 rounded-md bg-muted/40 p-3"
        >
          <div class="text-xs font-medium text-muted-foreground">
            {{ childMessageLabel(child) }}
          </div>
          <div class="flex flex-col gap-2 text-sm leading-6">
            <template v-if="child.blocks?.length">
              <ChatBlockRenderer
                v-for="(childBlock, index) in child.blocks"
                :key="`${child.id}-${index}`"
                :block="childBlock"
                :streaming="streaming"
                :thinking-display="thinkingDisplay"
                :interaction-disabled="interactionDisabled"
                @submit-interaction="submitInteraction"
                @open-artifact="openArtifact"
              />
            </template>
            <MessageResponse
              v-else
              :content="child.content"
            />
          </div>
        </div>
      </div>
    </ToolContent>
  </Tool>

  <Tool v-else-if="block.type === 'tool-result'">
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      :state="toolOutputState(block.errorText)"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolPayloadView
        mode="output"
        :tool-name="block.toolName"
        :value="block.result"
        :error-text="block.errorText"
      />
    </ToolContent>
  </Tool>

  <Tool v-else-if="block.type === 'tool-execution'">
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      :state="toolOutputState(block.errorText)"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolPayloadView
        mode="input"
        :tool-name="block.toolName"
        :value="block.params"
      />
      <div
        v-if="block.childMessages?.length"
        class="flex flex-col gap-3 border-t border-border/70 p-4"
      >
        <div
          v-for="child in block.childMessages"
          :key="child.id"
          class="flex flex-col gap-2 rounded-md bg-muted/40 p-3"
        >
          <div class="text-xs font-medium text-muted-foreground">
            {{ childMessageLabel(child) }}
          </div>
          <div class="flex flex-col gap-2 text-sm leading-6">
            <template v-if="child.blocks?.length">
              <ChatBlockRenderer
                v-for="(childBlock, index) in child.blocks"
                :key="`${child.id}-${index}`"
                :block="childBlock"
                :streaming="streaming"
                :thinking-display="thinkingDisplay"
                :interaction-disabled="interactionDisabled"
                @submit-interaction="submitInteraction"
                @open-artifact="openArtifact"
              />
            </template>
            <MessageResponse
              v-else
              :content="child.content"
            />
          </div>
        </div>
      </div>
      <ToolPayloadView
        mode="output"
        :tool-name="block.toolName"
        :value="block.result"
        :error-text="block.errorText"
      />
    </ToolContent>
  </Tool>

  <Node
    v-else-if="block.type === 'subagent-complete'"
    class="w-full"
  >
    <NodeHeader>
      <NodeTitle>{{ block.subagent }}</NodeTitle>
      <NodeDescription>
        {{ block.errorText ? "子 Agent 执行失败" : "子 Agent 已完成" }}
      </NodeDescription>
    </NodeHeader>
    <NodeContent class="flex flex-col gap-2 text-sm">
      <p class="text-muted-foreground">
        {{ subagentSummary(block) }}
      </p>
      <p
        v-if="block.errorText"
        class="text-destructive"
      >
        {{ block.errorText }}
      </p>
    </NodeContent>
  </Node>

  <Artifact
    v-else-if="block.type === 'artifact'"
  >
    <ArtifactHeader>
      <div class="min-w-0">
        <ArtifactTitle class="truncate">
          {{ block.name }}
        </ArtifactTitle>
        <ArtifactDescription>
          {{ artifactKindLabel(block.kind) }}{{ block.mode ? ` · ${block.mode}` : "" }}
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

  <UserInteractionBlock
    v-else-if="block.type === 'user-interaction'"
    :block="block"
    :disabled="interactionDisabled"
    @submit="submitInteraction"
  />
</template>
