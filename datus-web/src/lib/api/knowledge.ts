import { apiResult, deleteJsonBody, jsonBody } from "./helpers";
import type {
  MetricDimensionsData,
  MetricInfo,
  MetricPreviewData,
  MetricPreviewInput,
  ReferenceSQLInfo,
  SemanticModelValidation,
  SubjectNode,
  SubjectNodeType,
  TableDetail,
} from "@/types";

function subjectTreePath(path: string, datasourceId?: string | null): string {
  const selectedDatasource = datasourceId?.trim();
  if (!selectedDatasource) return path;

  const params = new URLSearchParams({ datasource_id: selectedDatasource });
  return `${path}?${params.toString()}`;
}

export const subjectApi = {
  list(baseUrl: string, datasourceId?: string | null): Promise<{ subjects: SubjectNode[] } | null> {
    return apiResult(baseUrl, subjectTreePath("/api/v1/subject-tree", datasourceId));
  },

  create(baseUrl: string, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/create", jsonBody({ subject_path: subjectPath }));
  },

  rename(baseUrl: string, type: SubjectNodeType, subjectPath: string[], newSubjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/rename", jsonBody({ type, subject_path: subjectPath, new_subject_path: newSubjectPath }));
  },

  delete(baseUrl: string, type: SubjectNodeType, subjectPath: string[]): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/delete", deleteJsonBody({ type, subject_path: subjectPath }));
  },

  getMetric(baseUrl: string, subjectPath: string[], datasourceId?: string | null): Promise<MetricInfo | null> {
    return apiResult(
      baseUrl,
      subjectTreePath("/api/v1/subject-tree/metric", datasourceId),
      jsonBody({ subject_path: subjectPath }),
    );
  },

  getMetricDimensions(
    baseUrl: string,
    subjectPath: string[],
    datasourceId?: string | null,
  ): Promise<MetricDimensionsData | null> {
    return apiResult(
      baseUrl,
      subjectTreePath("/api/v1/subject-tree/metric/dimensions", datasourceId),
      jsonBody({ subject_path: subjectPath }),
    );
  },

  previewMetric(baseUrl: string, input: MetricPreviewInput): Promise<MetricPreviewData | null> {
    return apiResult(baseUrl, "/api/v1/subject-tree/metric/preview", jsonBody(input));
  },

  createMetric(baseUrl: string, subjectPath: string[], yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/metric/create", jsonBody({ subject_path: subjectPath, yaml }));
  },

  editMetric(baseUrl: string, subjectPath: string[], yaml: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/metric/edit", jsonBody({ subject_path: subjectPath, yaml }));
  },

  getReferenceSql(
    baseUrl: string,
    subjectPath: string[],
    datasourceId?: string | null,
  ): Promise<ReferenceSQLInfo | null> {
    return apiResult(
      baseUrl,
      subjectTreePath("/api/v1/subject-tree/reference_sql", datasourceId),
      jsonBody({ subject_path: subjectPath }),
    );
  },

  createReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/reference_sql/create", jsonBody(data));
  },

  editReferenceSql(baseUrl: string, data: ReferenceSQLInfo & { subject_path: string[] }): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/reference_sql/edit", jsonBody(data));
  },

  editSemanticModel(baseUrl: string, entryId: string, updateValues: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/subject-tree/semantic_model/edit", jsonBody({ entry_id: entryId, update_values: updateValues }));
  },
};

export const tableApi = {
  detail(baseUrl: string, table: string, datasourceId?: string | null): Promise<{ table: TableDetail } | null> {
    return apiResult(baseUrl, `/api/v1/table/detail?${tableRequestQuery(table, datasourceId)}`);
  },

  getSemanticModel(baseUrl: string, table: string, datasourceId?: string | null): Promise<{ yaml: string } | null> {
    return apiResult(baseUrl, `/api/v1/semantic_model?${tableRequestQuery(table, datasourceId)}`);
  },

  saveSemanticModel(baseUrl: string, table: string, yaml: string, datasourceId?: string | null): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/semantic_model", jsonBody(semanticModelPayload(table, yaml, datasourceId)));
  },

  validateSemanticModel(baseUrl: string, table: string, yaml: string, datasourceId?: string | null): Promise<SemanticModelValidation | null> {
    return apiResult(baseUrl, "/api/v1/semantic_model/validate", jsonBody(semanticModelPayload(table, yaml, datasourceId)));
  },
};

function tableRequestQuery(table: string, datasourceId?: string | null): string {
  const params = new URLSearchParams();
  const selectedDatasource = datasourceId?.trim();
  if (selectedDatasource) params.set("datasource_id", selectedDatasource);
  params.set("table", table);
  return params.toString();
}

function semanticModelPayload(table: string, yaml: string, datasourceId?: string | null) {
  const selectedDatasource = datasourceId?.trim();
  return selectedDatasource ? { table, yaml, datasource_id: selectedDatasource } : { table, yaml };
}
