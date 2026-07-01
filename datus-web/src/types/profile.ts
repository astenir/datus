import type { components } from "@/types/openapi";

export interface ApiResponse<T> {
  success: boolean;
  data?: T | null;
  errorCode?: string | null;
  errorMessage?: string | null;
}

export type MeSummary = components["schemas"]["MeSummary"];
export type MeSessionsData = components["schemas"]["ChatSessionData"];
export type MeSession = components["schemas"]["ChatSessionItemInfo"];

export interface MeUsage {
  subject_type: string;
  subject_id: string;
  resource: string;
  used: number;
  window_start?: string | null;
  window_seconds?: number | null;
  updated_at?: string | null;
}

export interface MeDatasourceGrantView {
  datasource: string;
  enabled: boolean;
  effect: string;
  scopeText: string;
  raw: unknown;
}

export interface MeFeatureView {
  code: string;
  label: string;
  enabled: boolean;
}
