<script setup lang="ts">
import { ref, watch } from "vue";
import { CircleStop, Clock, Loader2, Play, Rows3, Terminal } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Textarea from "@/components/ui/Textarea.vue";
import { sqlApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import { useCatalog } from "@/composables/useCatalog";
import type { SqlExecuteResult } from "@/types";

const sqlQuery = ref("");
const executing = ref(false);
const result = ref<SqlExecuteResult | null>(null);
const error = ref("");
const executeTaskId = ref("");

const { effectiveBase } = useConnection();
const { database } = useCatalog();

async function handleExecute() {
  const query = sqlQuery.value.trim();
  if (!query || executing.value) return;

  executing.value = true;
  error.value = "";
  result.value = null;
  executeTaskId.value = crypto.randomUUID();

  try {
    const res = await sqlApi.execute(effectiveBase(), query, {
      database_name: database.value || undefined,
      result_format: "json",
    });
    result.value = res;
  } catch (e) {
    error.value = (e as Error).message || "执行失败";
  } finally {
    executing.value = false;
  }
}

async function handleStop() {
  if (!executeTaskId.value) return;
  try {
    await sqlApi.stopExecute(effectiveBase(), executeTaskId.value);
  } catch (e) {
    console.error("Stop failed:", e);
  }
  executing.value = false;
}

function handleKeyDown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    handleExecute();
  }
}

// Parse sql_return as JSON table if possible
const tableData = ref<Array<Record<string, unknown>>>([]);
const tableColumns = ref<string[]>([]);

function parseResult() {
  if (!result.value?.sql_return) {
    tableData.value = [];
    tableColumns.value = result.value?.columns || [];
    return;
  }
  try {
    const parsed = JSON.parse(result.value.sql_return);
    if (Array.isArray(parsed) && parsed.length > 0) {
      tableData.value = parsed;
      tableColumns.value = Object.keys(parsed[0]);
    } else {
      tableData.value = [];
      tableColumns.value = result.value.columns || [];
    }
  } catch {
    tableData.value = [];
    tableColumns.value = result.value.columns || [];
  }
}

// Watch for result changes
watch(result, parseResult);
</script>

<template>
  <div class="sqlConsole">
    <!-- Editor -->
    <div class="sqlEditor">
      <div class="sqlEditorHeader">
        <Terminal :size="16" />
        <span>SQL 控制台</span>
        <div class="sqlEditorActions">
          <Button v-if="!executing" variant="outline" size="sm" :disabled="!sqlQuery.trim()" @click="handleExecute">
            <Play :size="14" />
            执行
          </Button>
          <Button v-else variant="outline" size="sm" class="stopButton" @click="handleStop">
            <CircleStop :size="14" />
            停止
          </Button>
        </div>
      </div>
      <Textarea
        v-model="sqlQuery"
        class="sqlTextarea"
        placeholder="输入 SQL 查询... (Ctrl+Enter 执行)"
        :rows="6"
        @keydown="handleKeyDown"
      />
    </div>

    <!-- Status bar -->
    <div v-if="result || error || executing" class="sqlStatus">
      <Loader2 v-if="executing" class="spin" :size="14" />
      <template v-if="result">
        <span class="sqlStat">
          <Clock :size="12" />
          {{ result.execution_time?.toFixed(2) }}s
        </span>
        <span class="sqlStat">
          <Rows3 :size="12" />
          {{ result.row_count ?? 0 }} 行
        </span>
      </template>
      <span v-if="error" class="sqlError">{{ error }}</span>
    </div>

    <!-- Results -->
    <div v-if="tableData.length > 0" class="sqlResults">
      <div class="sqlTableWrap">
        <table class="sqlTable">
          <thead>
            <tr>
              <th v-for="col in tableColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in tableData" :key="i">
              <td v-for="col in tableColumns" :key="col">{{ row[col] ?? '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Raw result fallback -->
    <div v-else-if="result?.sql_return && tableData.length === 0" class="sqlResults">
      <pre class="sqlRawOutput">{{ result.sql_return }}</pre>
    </div>
  </div>
</template>
