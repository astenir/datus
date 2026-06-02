<script setup lang="ts">
import MarkdownIt from "markdown-it";

import type { ChatMessage } from "@/types";

import ToolCard from "./ToolCard.vue";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
});

// Enable tables and strikethrough (GFM-like)
md.enable("table");
md.enable("strikethrough");

// Open links in new tab
const defaultRender = md.renderer.rules.link_open || function(tokens, idx, options, _env, self) {
  return self.renderToken(tokens, idx, options);
};
md.renderer.rules.link_open = function(tokens, idx, options, env, self) {
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noreferrer");
  return defaultRender(tokens, idx, options, env, self);
};

const props = defineProps<{
  message: ChatMessage;
}>();

const blocks = props.message.blocks?.length
  ? props.message.blocks
  : [{ type: "markdown" as const, content: props.message.content }];

function renderMarkdown(content: string): string {
  return md.render(content);
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
      <div
        v-else
        class="markdownBody"
        v-html="renderMarkdown(block.content)"
      />
    </template>
  </div>
</template>
