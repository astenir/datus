<script setup lang="ts">
import { ref } from "vue";
import { CircleStop, Loader2, Play } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Checkbox from "@/components/ui/Checkbox.vue";
import Label from "@/components/ui/Label.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import { kbApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import { useCatalog } from "@/composables/useCatalog";
import { parseSseBuffer } from "@/lib/chat";
import type { BootstrapComponent } from "@/types";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
}>();

const { effectiveBase } = useConnection();
const { database } = useCatalog();

// Form state
const selectedComponents = ref<Set<BootstrapComponent>>(new Set(["metadata"]));
const strategy = ref<"overwrite" | "check" | "incremental">("incremental");

// Execution state
const running = ref(false);
const streamId = ref("");
const progressLog = ref<Array<{ component: string; stage: string; message?: string; error?: string; progress?: number }>>([]);

const componentOptions: Array<{ value: BootstrapComponent; label: string }> = [
  { value: "metadata", label: "元数据" },
  { value: "semantic_model", label: "语义模型" },
  { value: "metrics", label: "指标" },
  { value: "ext_knowledge", label: "外部知识" },
  { value: "reference_sql", label: "参考 SQL" },
];

const strategyOptions = [
  { value: "incremental", label: "增量" },
  { value: "check", label: "检查" },
  { value: "overwrite", label: "覆盖" },
];

function toggleComponent(comp: BootstrapComponent) {
  const next = new Set(selectedComponents.value);
  if (next.has(comp)) {
    next.delete(comp);
  } else {
    next.add(comp);
  }
  selectedComponents.value = next;
}

async function handleStart() {
  if (selectedComponents.value.size === 0) return;
  running.value = true;
  progressLog.value = [];
  streamId.value = "";

  try {
    const stream = await kbApi.bootstrap(effectiveBase(), {
      components: Array.from(selectedComponents.value),
      strategy: strategy.value,
      database_name: database.value || undefined,
    });
    if (!stream) return;

    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSseBuffer(buffer);
      buffer = rest;
      for (const event of events) {
        const data = event.data as Record<string, unknown> | undefined;
        if (!data) continue;
        if (data.stream_id && !streamId.value) streamId.value = data.stream_id as string;
        progressLog.value.push({
          component: (data.component as string) ?? "",
          stage: (data.stage as string) ?? "",
          message: data.message as string | undefined,
          error: data.error as string | undefined,
          progress: data.progress as number | undefined,
        });
      }
    }
  } catch (e) {
    progressLog.value.push({ component: "", stage: "error", error: (e as Error).message });
  } finally {
    running.value = false;
  }
}

async function handleCancel() {
  if (!streamId.value) return;
  try {
    await kbApi.cancelBootstrap(effectiveBase(), streamId.value);
  } catch (e) {
    console.error("Cancel failed:", e);
  }
  running.value = false;
}
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="settingsDrawer" side="right" aria-label="知识库构建">
      <SheetHeader class="settingsHeader">
        <SheetTitle>知识库 Bootstrap</SheetTitle>
      </SheetHeader>

      <div class="bootstrapForm">
        <div>
          <p class="panelTitle">组件</p>
          <div class="bootstrapComponents">
            <Label v-for="comp in componentOptions" :key="comp.value" class="checkRow">
              <Checkbox :checked="selectedComponents.has(comp.value)" @update:checked="toggleComponent(comp.value)" />
              {{ comp.label }}
            </Label>
          </div>
        </div>

        <Label>
          策略
          <AppPopoverSelect :value="strategy" :options="strategyOptions" @update:value="strategy = $event as typeof strategy" />
        </Label>

        <div class="bootstrapActions">
          <Button v-if="!running" disabled title="功能开发中，暂不可用" @click="handleStart">
            <Play :size="14" />
            开始构建
          </Button>
          <Button v-else variant="outline" class="stopButton" @click="handleCancel">
            <CircleStop :size="14" />
            取消
          </Button>
        </div>

        <!-- Progress log -->
        <div v-if="progressLog.length > 0" class="bootstrapLog">
          <div v-for="(entry, i) in progressLog" :key="i" :class="`bootstrapLogEntry ${entry.error ? 'error' : ''}`">
            <span class="bootstrapLogComponent">{{ entry.component }}</span>
            <span class="bootstrapLogStage">{{ entry.stage }}</span>
            <span v-if="entry.message" class="bootstrapLogMessage">{{ entry.message }}</span>
            <span v-if="entry.error" class="bootstrapLogError">{{ entry.error }}</span>
            <span v-if="entry.progress != null" class="bootstrapLogProgress">{{ entry.progress }}%</span>
          </div>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
