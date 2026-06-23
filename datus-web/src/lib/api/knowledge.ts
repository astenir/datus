import { apiResult, jsonBody } from "./helpers";
import type { MetricInfo, ReferenceSQLInfo, SemanticModelValidation, SubjectNode, TableDetail } from "@/types";

export const subjectApi = {
  list(baseUrl: string): Promise<{ subjects: SubjectNode[] } | null> {
    return apiResult(baseUrl, "/api/v1/subject/list");
  },

  create(baseUrl: string, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/create", jsonBody({ subject_path: subjectPath }));
  },

  rename(baseUrl: string, type: string, subjectPath: string[], newSubjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/rename", jsonBody({ type, subject_path: subjectPath, new_subject_path: newSubjectPath }));
  },

  delete(baseUrl: string, type: string, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/delete", { method: "DELETE", body: JSON.stringify({ type, subject_path: subjectPath }) });
  },

  getMetric(baseUrl: string, subjectPath: string[]): Promise<MetricInfo | null> {
    return apiResult(baseUrl, "/api/v1/subject/metric", jsonBody({ subject_path: subjectPath }));
  },

  createMetric(baseUrl: string, subjectPath: string[], name: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/metric/create", jsonBody({ subject_path: subjectPath, name }));
  },

  editMetric(baseUrl: string, subjectPath: string[], yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/metric/edit", jsonBody({ subject_path: subjectPath, yaml }));
  },

  getReferenceSql(baseUrl: string, subjectPath: string[]): Promise<ReferenceSQLInfo | null> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql", jsonBody({ subject_path: subjectPath }));
  },

  createReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql/create", jsonBody(data));
  },

  editReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/reference_sql/edit", jsonBody(data));
  },

  editSemanticModel(baseUrl: string, entryId: string, updateValues: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject/semantic_model/edit", jsonBody({ entry_id: entryId, update_values: updateValues }));
  },
};

export const tableApi = {
  detail(baseUrl: string, table: string): Promise<{ table: TableDetail } | null> {
    return apiResult(baseUrl, `/api/v1/table/detail?table=${encodeURIComponent(table)}`);
  },

  getSemanticModel(baseUrl: string, table: string): Promise<{ yaml: string } | null> {
    return apiResult(baseUrl, `/api/v1/semantic_model?table=${encodeURIComponent(table)}`);
  },

  saveSemanticModel(baseUrl: string, table: string, yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/semantic_model", jsonBody({ table, yaml }));
  },

  validateSemanticModel(baseUrl: string, table: string, yaml: string): Promise<SemanticModelValidation | null> {
    return apiResult(baseUrl, "/api/v1/semantic_model/validate", jsonBody({ table, yaml }));
  },
};
