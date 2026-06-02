<script setup lang="ts">
import { computed } from "vue";
import { Database, Loader2, RefreshCw, Server, Settings2 } from "@lucide/vue";

import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import Button from "@/components/ui/Button.vue";
import Checkbox from "@/components/ui/Checkbox.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import type { ConfigSummary, ConnectionState } from "@/types";

const props = defineProps<{
  open: boolean;
  apiBase: string;
  connection: ConnectionState;
  config: ConfigSummary | null;
  language: string;
  permissionMode: string;
  planMode: boolean;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:api-base": [value: string];
  "update:language": [value: string];
  "update:permission-mode": [value: string];
  "update:plan-mode": [value: boolean];
  "refresh-connection": [];
}>();

const connectionLabel = computed(() => {
  const map: Record<ConnectionState, string> = {
    idle: "未检测",
    checking: "检测中…",
    online: "已连接",
    offline: "未连接",
  };
  return map[props.connection];
});
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="settingsDrawer" side="right" :show-close-button="false" aria-label="设置">
      <SheetHeader class="settingsHeader">
        <div>
          <p class="eyebrow">
            <Settings2 :size="14" />
            控制台
          </p>
          <SheetTitle>设置</SheetTitle>
        </div>
      </SheetHeader>

      <section class="settingsSection">
        <div class="panelTitle">
          <Server :size="16" />
          <span>服务连接</span>
        </div>
        <label>
          API 地址
          <Input :value="apiBase" placeholder="同源代理或 http://localhost:8000" @update:value="emit('update:api-base', $event)" />
        </label>
        <Button class="secondaryButton" variant="outline" type="button" @click="emit('refresh-connection')">
          <Loader2 v-if="connection === 'checking'" class="spin" :size="16" />
          <RefreshCw v-else :size="16" />
          {{ connectionLabel }}
        </Button>
      </section>

      <section class="settingsSection">
        <div class="panelTitle">
          <Settings2 :size="16" />
          <span>高级参数</span>
        </div>
        <div class="twoCols">
          <label>
            语言
            <AppPopoverSelect
              :value="language"
              :options="[{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }]"
              @update:value="emit('update:language', $event)"
            />
          </label>
          <label>
            权限
            <AppPopoverSelect
              :value="permissionMode"
              :options="[{ value: 'normal', label: 'normal' }, { value: 'auto', label: 'auto' }, { value: 'dangerous', label: 'dangerous' }]"
              @update:value="emit('update:permission-mode', $event)"
            />
          </label>
        </div>
        <Label class="checkRow">
          <Checkbox :checked="planMode" @update:checked="emit('update:plan-mode', $event)" />
          Plan mode
        </Label>
      </section>

      <section class="settingsSection summaryPanel">
        <div class="panelTitle">
          <Database :size="16" />
          <span>当前配置</span>
        </div>
        <dl>
          <dt>模型</dt>
          <dd>{{ config?.target || '-' }}</dd>
          <dt>数据源</dt>
          <dd>{{ config?.current_datasource || '-' }}</dd>
          <dt>Home</dt>
          <dd :title="config?.home">{{ config?.home || '-' }}</dd>
        </dl>
      </section>
    </SheetContent>
  </Sheet>
</template>
