<script setup lang="ts">
import { ref, computed } from "vue";
import { Bot, Cpu, ListChecks, Loader2 } from "@lucide/vue";

import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import DatabasePicker from "@/components/chat/DatabasePicker.vue";
import Button from "@/components/ui/Button.vue";
import Switch from "@/components/ui/Switch.vue";
import Textarea from "@/components/ui/Textarea.vue";
import type { CatalogRecord, ConnectionState, SelectOption } from "@/types";

const props = defineProps<{
  connection: ConnectionState;
  isStreaming: boolean;
  agentOptions: SelectOption[];
  modelOptions: SelectOption[];
  databaseOptions: SelectOption[];
  catalogEntries: CatalogRecord[];
  selectedAgent: string;
  model: string;
  database: string;
  schema: string;
  planMode: boolean;
}>();

const emit = defineEmits<{
  "update:selected-agent": [value: string];
  "update:model": [value: string];
  "update:database": [value: string];
  "update:schema": [value: string];
  "update:plan-mode": [value: boolean];
  send: [message: string];
  stop: [];
}>();

const message = ref("");
const expandedDatabases = ref(new Set<string>());
const isDatabasePickerOpen = ref(false);

const selectedDatabaseLabel = computed(() => {
  if (!props.database) return "";
  return props.schema ? `${props.database}.${props.schema}` : props.database;
});

function handleSubmit() {
  const trimmed = message.value.trim();
  if (!trimmed || props.isStreaming) return;
  emit("send", trimmed);
  message.value = "";
}

function handleKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    handleSubmit();
  }
}

function handleSelectDatabaseSchema(databaseName: string, schemaName: string, closePicker?: boolean) {
  emit("update:database", databaseName);
  emit("update:schema", schemaName);
  if (closePicker) {
    isDatabasePickerOpen.value = false;
  }
}

function toggleDatabaseExpansion(databaseName: string) {
  const next = new Set(expandedDatabases.value);
  if (next.has(databaseName)) {
    next.delete(databaseName);
  } else {
    next.add(databaseName);
  }
  expandedDatabases.value = next;
}
</script>

<template>
  <form class="composer" @submit.prevent="handleSubmit">
    <Textarea
      v-model="message"
      placeholder="输入要交给 Datus Agent 处理的问题..."
      :rows="2"
      @keydown="handleKeyDown"
    />
    <div class="quickControls">
      <div class="quickControlsLeft">
        <label aria-label="子 Agent">
          <span class="controlIcon" title="子 Agent" aria-hidden="true">
            <Bot :size="13" />
          </span>
          <AppPopoverSelect
            :value="selectedAgent"
            :options="agentOptions"
            placeholder="默认 chat"
            narrow
            @update:value="emit('update:selected-agent', $event)"
          />
        </label>
        <DatabasePicker
          :open="isDatabasePickerOpen"
          :disabled="connection !== 'online'"
          :selected-label="selectedDatabaseLabel"
          :database="database"
          :schema="schema"
          :database-options="databaseOptions"
          :catalog-entries="catalogEntries"
          :expanded-databases="expandedDatabases"
          @update:open="isDatabasePickerOpen = $event"
          @select="handleSelectDatabaseSchema"
          @toggle-database="toggleDatabaseExpansion"
        />
        <label class="planModeSwitch" for="plan-mode-switch">
          <ListChecks :size="13" />
          <span>规划</span>
          <Switch
            id="plan-mode-switch"
            :checked="planMode"
            aria-label="规划模式"
            @update:checked="emit('update:plan-mode', $event)"
          />
        </label>
      </div>
      <div class="quickControlsRight">
        <label aria-label="模型">
          <span class="controlIcon" title="模型" aria-hidden="true">
            <Cpu :size="13" />
          </span>
          <AppPopoverSelect
            :value="props.model"
            :options="modelOptions"
            :disabled="connection !== 'online'"
            placeholder="默认模型"
            narrow
            @update:value="emit('update:model', $event)"
          />
        </label>
        <Button
          class="primaryButton"
          type="submit"
          aria-label="发送消息"
          :disabled="!message.trim() || isStreaming"
        >
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
