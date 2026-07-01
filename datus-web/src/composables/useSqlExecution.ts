import { computed, readonly, shallowRef } from "vue";
import { toast } from "vue-sonner";
import { sqlApi } from "@/lib/api";
import { displaySqlCellValue, parseSqlReturnRows } from "@/lib/sql-results";
import { useConnection } from "@/composables/useConnection";
import type { SqlExecuteResult } from "@/types";

type ExecuteSqlOptions = {
  databaseName?: string;
};

let sqlExecutionSequence = 0;

function nextSqlExecutionTaskId() {
  sqlExecutionSequence += 1;
  return `frontend-sql-${Date.now()}-${sqlExecutionSequence}`;
}

function normalizedOptionalString(value?: string) {
  const normalized = value?.trim() ?? "";
  return normalized || undefined;
}

export function useSqlExecution() {
  const { effectiveBase } = useConnection();
  const running = shallowRef(false);
  const error = shallowRef("");
  const result = shallowRef<SqlExecuteResult | null>(null);
  const activeTaskId = shallowRef<string | null>(null);
  const runToken = shallowRef(0);

  const rows = computed(() => parseSqlReturnRows(result.value?.sql_return ?? ""));

  const columns = computed(() => {
    const resultColumns = result.value?.columns?.filter((column) => column.trim()) ?? [];
    if (resultColumns.length > 0) return resultColumns;

    const keys = new Set<string>();
    for (const row of rows.value.slice(0, 20)) {
      Object.keys(row).forEach((key) => keys.add(key));
    }
    return Array.from(keys);
  });

  const displayRows = computed(() =>
    rows.value.map((row) => columns.value.map((column) => displaySqlCellValue(row[column]))),
  );

  const rawResult = computed(() => result.value?.sql_return?.trim() ?? "");

  async function executeSql(sqlQuery: string, options: ExecuteSqlOptions = {}) {
    const query = sqlQuery.trim();
    if (!query || running.value) return;

    const token = runToken.value + 1;
    const executeTaskId = nextSqlExecutionTaskId();
    runToken.value = token;
    running.value = true;
    error.value = "";
    result.value = null;
    activeTaskId.value = executeTaskId;

    try {
      const data = await sqlApi.execute(effectiveBase(), query, {
        database_name: normalizedOptionalString(options.databaseName),
        result_format: "json",
        execute_task_id: executeTaskId,
      });

      if (runToken.value === token) {
        result.value = data;
      }
    } catch (err) {
      if (runToken.value === token) {
        error.value = err instanceof Error ? err.message : String(err);
        toast.error("SQL 执行失败");
      }
    } finally {
      if (runToken.value === token) {
        running.value = false;
        activeTaskId.value = null;
      }
    }
  }

  async function stopRunning() {
    const executeTaskId = activeTaskId.value;
    if (!executeTaskId) return;

    runToken.value += 1;
    running.value = false;
    activeTaskId.value = null;

    try {
      await sqlApi.stopExecute(effectiveBase(), executeTaskId);
    } catch (err) {
      console.error("Failed to stop SQL execution:", err);
      toast.error("停止 SQL 执行失败");
    }
  }

  function reset() {
    if (running.value) {
      void stopRunning();
      return;
    }

    error.value = "";
    result.value = null;
    activeTaskId.value = null;
  }

  return {
    running: readonly(running),
    error: readonly(error),
    result: readonly(result),
    rows,
    columns,
    displayRows,
    rawResult,
    executeSql,
    stopRunning,
    reset,
  };
}
