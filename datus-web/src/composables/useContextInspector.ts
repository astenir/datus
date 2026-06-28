import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { sqlApi } from "@/lib/api";
import type { ContextCommandResult, InternalCommandResult } from "@/types";

export type ContextInspectorCommandKind = "context" | "internal";

export type ContextInspectorCommandId =
  | "context"
  | "catalogs"
  | "tables"
  | "internal-databases"
  | "internal-tables";

export type ContextInspectorCommandOption = {
  id: ContextInspectorCommandId;
  kind: ContextInspectorCommandKind;
  command: string;
  label: string;
  description: string;
};

export type ContextInspectorTableRow = {
  name: string;
  type: string;
};

export type ContextInspectorResult = {
  option: ContextInspectorCommandOption;
  context?: ContextCommandResult;
  internal?: InternalCommandResult;
};

export const contextInspectorCommands: readonly ContextInspectorCommandOption[] = [
  {
    id: "context",
    kind: "context",
    command: "context",
    label: "当前上下文",
    description: "读取当前数据源、数据库、catalog 与 schema 状态。",
  },
  {
    id: "catalogs",
    kind: "context",
    command: "catalogs",
    label: "Catalog 列表",
    description: "通过 context route 读取可见 catalog 元数据。",
  },
  {
    id: "tables",
    kind: "context",
    command: "tables",
    label: "上下文表",
    description: "通过 context route 读取当前数据源可见表。",
  },
  {
    id: "internal-databases",
    kind: "internal",
    command: "databases",
    label: "数据库",
    description: "通过 internal metadata command 读取数据库列表。",
  },
  {
    id: "internal-tables",
    kind: "internal",
    command: "tables",
    label: "内部表清单",
    description: "通过 internal metadata command 读取表清单。",
  },
];

function commandById(id: ContextInspectorCommandId): ContextInspectorCommandOption {
  return contextInspectorCommands.find((option) => option.id === id) ?? contextInspectorCommands[0];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function tableRowsFromUnknown(value: unknown): ContextInspectorTableRow[] {
  if (!Array.isArray(value)) return [];

  return value.map((item) => {
    if (typeof item === "string") {
      return { name: item, type: "table" };
    }

    if (!isRecord(item)) {
      return { name: "", type: "" };
    }

    const name = stringField(item.name) || stringField(item.table_name);
    const type = stringField(item.type) || stringField(item.table_type) || "table";
    return { name, type };
  }).filter((row) => row.name);
}

function internalData(result: InternalCommandResult | undefined): Record<string, unknown> {
  const data = result?.result.data;
  return isRecord(data) ? data : {};
}

export function useContextInspector() {
  const { effectiveBase } = useConnection();

  const selectedCommandId = shallowRef<ContextInspectorCommandId>("context");
  const isLoading = shallowRef(false);
  const error = shallowRef("");
  const result = ref<ContextInspectorResult | null>(null);

  const selectedCommand = computed(() => commandById(selectedCommandId.value));
  const tableRows = computed<ContextInspectorTableRow[]>(() => {
    const current = result.value;
    if (!current) return [];

    const contextTables = tableRowsFromUnknown(current.context?.result.tables);
    if (contextTables.length > 0) return contextTables;

    const data = internalData(current.internal);
    return tableRowsFromUnknown(data.tables ?? data.databases);
  });
  const outputText = computed(() => {
    const current = result.value;
    if (!current) return "尚未读取上下文";

    if (current.internal) {
      return current.internal.result.command_output || current.option.description;
    }

    const info = current.context?.result.context_info;
    if (isRecord(info) && typeof info.message === "string") {
      return info.message;
    }

    return current.option.description;
  });
  const resultJson = computed(() => {
    const payload = result.value?.context ?? result.value?.internal ?? null;
    return JSON.stringify(payload, null, 2);
  });

  async function runCommand(
    id: ContextInspectorCommandId = selectedCommandId.value,
    options: { databaseName?: string; schemaName?: string } = {},
  ) {
    const option = commandById(id);
    selectedCommandId.value = option.id;
    isLoading.value = true;
    error.value = "";

    try {
      if (option.kind === "context") {
        const data = await sqlApi.contextCommand(
          effectiveBase(),
          option.command,
          "",
          options.databaseName,
          options.schemaName,
        );
        result.value = { option, context: data ?? undefined };
      } else {
        const data = await sqlApi.internalCommand(effectiveBase(), option.command, "");
        result.value = { option, internal: data ?? undefined };
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      error.value = message;
      toast.error("读取上下文失败");
    } finally {
      isLoading.value = false;
    }
  }

  return {
    commands: contextInspectorCommands,
    selectedCommandId,
    selectedCommand,
    isLoading: readonly(isLoading),
    error: readonly(error),
    result: readonly(result),
    tableRows,
    outputText,
    resultJson,
    runCommand,
  };
}

export const contextInspectorInternals = {
  tableRowsFromUnknown,
};
