<script setup lang="ts">
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

defineProps<{
  apiBase: string;
  connection: ConnectionState;
  connectionLabel: string;
  config: ConfigSummary | null;
  language: string;
  permissionMode: string;
  planMode: boolean;
}>();

const emit = defineEmits<{
  "api-base-change": [value: string];
  "check-connection": [];
  "language-change": [value: string];
  "permission-mode-change": [value: string];
  "plan-mode-change": [value: boolean];
  close: [];
}>();
</script>

<template>
  <Sheet :open="true" @update:open="(open) => { if (!open) emit('close') }">
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
          <Input :value="apiBase" placeholder="同源代理或 http://localhost:8000" @update:value="emit('api-base-change', $event)" />
        </label>
        <Button class="secondaryButton" variant="outline" type="button" @click="emit('check-connection')">
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
              @update:value="emit('language-change', $event)"
            />
          </label>
          <label>
            权限
            <AppPopoverSelect
              :value="permissionMode"
              :options="[{ value: 'normal', label: 'normal' }, { value: 'auto', label: 'auto' }, { value: 'dangerous', label: 'dangerous' }]"
              @update:value="emit('permission-mode-change', $event)"
            />
          </label>
        </div>
        <Label class="checkRow">
          <Checkbox :checked="planMode" @update:checked="emit('plan-mode-change', $event)" />
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
