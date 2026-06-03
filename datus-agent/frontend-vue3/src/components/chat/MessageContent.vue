<script setup lang="ts">
import { computed } from "vue";
import MarkdownIt from "markdown-it";
import { chatApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";

import type { ChatMessage } from "@/types";
import ToolCard from "./ToolCard.vue";
import UserInteractionCard from "./UserInteractionCard.vue";
import FeedbackButtons from "./FeedbackButtons.vue";
import SuccessStoryButton from "./SuccessStoryButton.vue";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
});

// Block dangerous URI schemes (XSS prevention)
const SAFE_SCHEMES = /^(https?|mailto|tel):/i;
md.validateLink = (url: string) => SAFE_SCHEMES.test(url) || /^(?:[a-z][a-z0-9+\-.]*:)?\/\//i.test(url);

md.enable("table");
md.enable("strikethrough");

const defaultRender =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options);
  };
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noreferrer");
  return defaultRender(tokens, idx, options, env, self);
};

const props = defineProps<{
  message: ChatMessage;
  sessionId?: string;
}>();

const blocks = computed(() =>
  props.message.blocks?.length
    ? props.message.blocks
    : [{ type: "markdown" as const, content: props.message.content }]
);

function renderMarkdown(content: string): string {
  return md.render(content);
}

async function handleFeedback(emoji: string) {
  if (!props.sessionId) return;
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    await chatApi.feedback(base, {
      source_session_id: props.sessionId,
      reaction_emoji: emoji,
      reference_msg: props.message.content.slice(0, 2000),
    });
  } catch (error) {
    console.error("Feedback failed:", error);
  }
}
</script>

<template>
  <div class="messageBlocks">
    <template v-for="(block, index) in blocks" :key="index">
      <ToolCard
        v-if="block.type === 'tool-call'"
        mode="call"
        :tool-name="block.toolName"
        :value="block.params"
      />
      <ToolCard
        v-else-if="block.type === 'tool-result'"
        mode="result"
        :tool-name="block.toolName"
        :value="block.result"
        :duration="block.duration"
        :short-desc="block.shortDesc"
      />
      <UserInteractionCard
        v-else-if="block.type === 'user-interaction'"
        :session-id="sessionId ?? ''"
        :action-type="block.actionType"
        :requests="block.requests"
      />
      <div v-else class="markdownBody" v-html="renderMarkdown(block.content)" />
    </template>
    <div v-if="message.role === 'assistant' && sessionId" class="messageActions">
      <FeedbackButtons
        @feedback="handleFeedback"
      />
      <SuccessStoryButton
        :session-id="sessionId"
        :message-content="message.content"
      />
    </div>
  </div>
</template>
