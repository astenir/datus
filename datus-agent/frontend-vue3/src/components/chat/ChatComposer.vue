<script setup lang="ts">
import { Bot, Cpu, ListChecks, Loader2 } from "@lucide/vue";

import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import DatabasePicker from "@/components/chat/DatabasePicker.vue";
import Button from "@/components/ui/Button.vue";
import Switch from "@/components/ui/Switch.vue";
import Textarea from "@/components/ui/Textarea.vue";
import type { CatalogRecord, SelectOption } from "@/types";

defineProps<{
  agentOptions: SelectOption[];
  catalogEntries: CatalogRecord[];
  database: string;
  databaseOptions: SelectOption[];
  expandedDatabases: Set<string>;
  isDatabasePickerOpen: boolean;
  isLoadingOptions: boolean;
  isStreaming: boolean;
  message: string;
  model: string;
  modelOptions: SelectOption[];
  planMode: boolean;
  schema: string;
  selectedAgent: string;
  selectedDatabaseLabel: string;
}>();

const emit = defineEmits<{
  "database-picker-open-change": [open: boolean];
  "message-change": [value: string];
  "model-change": [value: string];
  "plan-mode-change": [value: boolean];
  "select-agent": [value: string];
  "select-database-schema": [databaseName: string, schemaName: string, closePicker?: boolean];
  submit: [];
  "toggle-database-expansion": [databaseName: string];
}>();

const submit = (event: Event) => {
  event.preventDefault();
  emit("submit");
};
</script>

<template>
  <form class="composer" @submit="submit">
    <Textarea
      :model-value="message"
      placeholder="输入要交给 Datus Agent 处理的问题..."
      :rows="2"
      @update:model-value="emit('message-change', $event)"
      @keydown="(e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); emit('submit') } }"
    />
    <div class="quickControls">
      <div class="quickControlsLeft">
        <label aria-label="子 Agent">
          <span class="controlIcon" title="子 Agent" aria-hidden="true">
            <Bot :size="13" />
          </span>
          <AppPopoverSelect :value="selectedAgent" :options="agentOptions" placeholder="默认 chat" narrow @update:value="emit('select-agent', $event)" />
        </label>
        <DatabasePicker
          :open="isDatabasePickerOpen"
          :disabled="isLoadingOptions"
          :selected-label="selectedDatabaseLabel"
          :database="database"
          :schema="schema"
          :database-options="databaseOptions"
          :catalog-entries="catalogEntries"
          :expanded-databases="expandedDatabases"
          @update:open="emit('database-picker-open-change', $event)"
          @select="(db, s, close) => emit('select-database-schema', db, s, close)"
          @toggle-database="(db) => emit('toggle-database-expansion', db)"
        />
        <label class="planModeSwitch" for="plan-mode-switch">
          <ListChecks :size="13" />
          <span>规划</span>
          <Switch id="plan-mode-switch" :checked="planMode" aria-label="规划模式" @update:checked="emit('plan-mode-change', $event)" />
        </label>
      </div>
      <div class="quickControlsRight">
        <label aria-label="模型">
          <span class="controlIcon" title="模型" aria-hidden="true">
            <Cpu :size="13" />
          </span>
          <AppPopoverSelect :value="model" :options="modelOptions" :disabled="isLoadingOptions" placeholder="默认模型" narrow @update:value="emit('model-change', $event)" />
        </label>
        <Button class="primaryButton" type="submit" aria-label="发送消息" :disabled="!message.trim() || isStreaming">
          <Loader2 v-if="isStreaming" class="spin" :size="17" />
          <svg v-else class="sendSolidIcon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" />
            <path d="m21.854 2.147-10.94 10.939" />
          </svg>
          发送
        </Button>
      </div>
    </div>
  </form>
</template>
