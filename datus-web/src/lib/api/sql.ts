import { apiResult, jsonBody } from "./helpers";
import type { ContextCommandResult, InternalCommandResult, SqlExecuteResult } from "@/types";

export const sqlApi = {
  execute(
    baseUrl: string,
    sqlQuery: string,
    options?: { database_name?: string; result_format?: string; execute_task_id?: string }
  ): Promise<SqlExecuteResult | null> {
    return apiResult(baseUrl, "/api/v1/sql/execute", jsonBody({ sql_query: sqlQuery, ...options }));
  },

  stopExecute(baseUrl: string, executeTaskId: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/sql/stop_execute", jsonBody({ execute_task_id: executeTaskId }));
  },

  contextCommand(baseUrl: string, contextType: string, args?: string, databaseName?: string, schemaName?: string): Promise<ContextCommandResult | null> {
    return apiResult(baseUrl, `/api/v1/context/${encodeURIComponent(contextType)}`, jsonBody({ context_type: contextType, args: args || "", database_name: databaseName, schema_name: schemaName }));
  },

  internalCommand(baseUrl: string, command: string, args?: string): Promise<InternalCommandResult | null> {
    return apiResult(baseUrl, `/api/v1/internal/${encodeURIComponent(command)}`, jsonBody({ command, args: args || "" }));
  },
};
