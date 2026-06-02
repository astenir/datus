<script setup lang="ts">
import { CheckCircle2, ChevronDown, TerminalSquare, XCircle } from "@lucide/vue";
import { CollapsibleRoot, CollapsibleTrigger, CollapsibleContent } from "reka-ui";
import { ref } from "vue";

import { stringifyContent } from "@/lib/chat";
import { displayValueForTool, sqlFromToolValue, sqlKeys, summarizeValue, tableFromToolValue, toolResultStatus } from "@/lib/tool-display";

const props = defineProps<{
  mode: "call" | "result";
  toolName: string;
  value: unknown;
  duration?: number;
  shortDesc?: string;
}>();

const isOpen = ref(props.mode === "result");

const payload = stringifyContent(props.value);
const displayValue = displayValueForTool(props.mode, props.value);
const displayPayload = stringifyContent(displayValue);
const hasValue = displayValue !== undefined && displayValue !== null && displayPayload !== "";
const payloadLabel = props.mode === "call" ? "参数" : "返回";
const resultStatus = props.mode === "result" ? toolResultStatus(props.value) : "unknown";
const statusLabel = props.mode === "call" ? "Tool call" : resultStatus === "error" ? "Tool result failed" : "Tool result";
const sqlText = sqlFromToolValue(displayValue);
const table = tableFromToolValue(displayValue, { omitKeys: sqlText ? sqlKeys : undefined });
const valueKind = table?.sourceLabel ?? summarizeValue(displayValue);
</script>

<template>
  <CollapsibleRoot :open="isOpen" :data-state="isOpen ? 'open' : 'closed'" :class="`toolCard ${mode} ${mode === 'result' ? resultStatus : ''}`">
    <CollapsibleTrigger as-child>
      <div class="toolHeader" role="button" tabindex="0" @click="isOpen = !isOpen">
        <span class="toolChevron" aria-hidden="true">
          <ChevronDown :size="16" />
        </span>
        <span class="toolStatusIcon" aria-hidden="true">
          <TerminalSquare v-if="mode === 'call'" :size="15" />
          <XCircle v-else-if="resultStatus === 'error'" :size="15" />
          <CheckCircle2 v-else :size="15" />
        </span>
        <span class="toolHeading">
          <span class="toolBadge">{{ statusLabel }}</span>
          <span class="toolName">{{ toolName }}</span>
        </span>
        <span class="toolMetaGroup">
          <span class="toolMeta">{{ valueKind }}</span>
          <span v-if="duration !== undefined" class="toolMeta">{{ duration.toFixed(2) }}s</span>
        </span>
      </div>
    </CollapsibleTrigger>
    <CollapsibleContent force-mount>
      <div class="toolBody">
        <div v-if="shortDesc" class="toolSummary">{{ shortDesc }}</div>
        <template v-if="hasValue">
          <section v-if="sqlText" class="toolSqlBlock" aria-label="SQL 语句">
            <div class="toolSqlHeader">
              <span>SQL 语句</span>
            </div>
            <pre class="toolSqlCode">{{ sqlText }}</pre>
          </section>
          <div v-if="table" class="toolTableWrap">
            <table class="toolTable">
              <thead>
                <tr>
                  <th v-for="column in table.columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in table.rows" :key="rowIndex">
                  <td v-for="(cell, cellIndex) in row" :key="`${rowIndex}-${cellIndex}`" :title="cell">
                    {{ cell }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <details class="toolRawBlock" :open="!table">
            <summary>
              <span>{{ table ? `查看原始${payloadLabel}` : payloadLabel }}</span>
              <span>{{ valueKind }}</span>
            </summary>
            <pre class="toolPayload">{{ table ? payload : displayPayload }}</pre>
          </details>
        </template>
        <div v-else class="toolEmpty">没有可展示的{{ payloadLabel }}</div>
      </div>
    </CollapsibleContent>
  </CollapsibleRoot>
</template>
