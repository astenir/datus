<script setup lang="ts">
import { computed, ref } from "vue";
import { CheckCircle2, Database, Loader2, RefreshCw, Server, Settings2, XCircle, Zap } from "@lucide/vue";

import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import Checkbox from "@/components/ui/Checkbox.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import { configApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { ConfigSummary, ConnectionState, ProbeResult } from "@/types";

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

// ─── Connectivity testing ────────────────────────────────────────────────────

const testingModel = ref(false);
const testingDatasource = ref(false);
const modelTestResult = ref<ProbeResult | null>(null);
const datasourceTestResult = ref<ProbeResult | null>(null);

async function testModel() {
  if (!props.config?.target) return;
  testingModel.value = true;
  modelTestResult.value = null;
  try {
    const { effectiveBase } = useConnection();
    const result = await configApi.testModel(effectiveBase(), {
      type: "openai",
      model: props.config.target,
    });
    modelTestResult.value = result;
  } catch (e) {
    modelTestResult.value = { ok: false, message: (e as Error).message };
  } finally {
    testingModel.value = false;
  }
}

async function testDatasource() {
  if (!props.config?.current_datasource) return;
  testingDatasource.value = true;
  datasourceTestResult.value = null;
  try {
    const { effectiveBase } = useConnection();
    const result = await configApi.testDatasource(effectiveBase(), {
      type: props.config.current_datasource,
    });
    datasourceTestResult.value = result;
  } catch (e) {
    datasourceTestResult.value = { ok: false, message: (e as Error).message };
  } finally {
    testingDatasource.value = false;
  }
}
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

      <!-- Connection -->
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

      <!-- Advanced params -->
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

      <!-- Current config with connectivity test -->
      <section class="settingsSection summaryPanel">
        <div class="panelTitle">
          <Database :size="16" />
          <span>当前配置</span>
        </div>
        <dl>
          <dt>模型</dt>
          <dd class="configTestRow">
            {{ config?.target || '-' }}
            <Button
              v-if="config?.target"
              class="iconButton testBtn"
              variant="ghost"
              size="icon"
              :disabled="testingModel"
              aria-label="测试模型连接"
              @click="testModel"
            >
              <Loader2 v-if="testingModel" class="spin" :size="14" />
              <Zap v-else :size="14" />
            </Button>
          </dd>
          <dt>数据源</dt>
          <dd class="configTestRow">
            {{ config?.current_datasource || '-' }}
            <Button
              v-if="config?.current_datasource"
              class="iconButton testBtn"
              variant="ghost"
              size="icon"
              :disabled="testingDatasource"
              aria-label="测试数据源连接"
              @click="testDatasource"
            >
              <Loader2 v-if="testingDatasource" class="spin" :size="14" />
              <Zap v-else :size="14" />
            </Button>
          </dd>
          <dt>Home</dt>
          <dd :title="config?.home">{{ config?.home || '-' }}</dd>
        </dl>

        <!-- Test results -->
        <div v-if="modelTestResult" class="testResult">
          <Badge :variant="modelTestResult.ok ? 'success' : 'destructive'">
            <CheckCircle2 v-if="modelTestResult.ok" :size="12" />
            <XCircle v-else :size="12" />
            模型: {{ modelTestResult.ok ? '连接正常' : modelTestResult.message || '连接失败' }}
          </Badge>
        </div>
        <div v-if="datasourceTestResult" class="testResult">
          <Badge :variant="datasourceTestResult.ok ? 'success' : 'destructive'">
            <CheckCircle2 v-if="datasourceTestResult.ok" :size="12" />
            <XCircle v-else :size="12" />
            数据源: {{ datasourceTestResult.ok ? '连接正常' : datasourceTestResult.message || '连接失败' }}
          </Badge>
        </div>
      </section>

      <!-- Datasources detail -->
      <section v-if="config?.datasources && Object.keys(config.datasources).length > 0" class="settingsSection">
        <div class="panelTitle">
          <Database :size="16" />
          <span>数据源列表</span>
        </div>
        <div class="configList">
          <div v-for="(ds, name) in config.datasources" :key="name" class="configItem">
            <span class="configItemName">{{ name }}</span>
            <span class="configItemType">{{ (ds as Record<string, unknown>).type || '-' }}</span>
          </div>
        </div>
      </section>

      <!-- Models detail -->
      <section v-if="config?.models && Object.keys(config.models).length > 0" class="settingsSection">
        <div class="panelTitle">
          <Server :size="16" />
          <span>模型列表</span>
        </div>
        <div class="configList">
          <div v-for="(model, name) in config.models" :key="name" class="configItem">
            <span class="configItemName">{{ name }}</span>
            <span class="configItemType">{{ (model as Record<string, unknown>).type || '-' }}</span>
          </div>
        </div>
      </section>
    </SheetContent>
  </Sheet>
</template>
