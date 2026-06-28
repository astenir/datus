import type { components } from "@/types/openapi";

export interface ApiResponse<T> {
  success: boolean;
  data?: T | null;
  errorCode?: string;
  errorMessage?: string;
}

export type AdminUser = components["schemas"]["AdminUserSummary"];
export type Role = components["schemas"]["AdminRoleSummary"];
export type AdminSession = components["schemas"]["AdminSessionSummary"];
export type AdminSessionDetail = components["schemas"]["AdminSessionDetail"];
export type AuditLog = components["schemas"]["AuditLogEntry"];
export type AdminDatasource = components["schemas"]["AdminDatasourceSummary"];
export type AdminDatasourceGrant = components["schemas"]["AdminDatasourceGrantSummary"];
export type AdminQuota = components["schemas"]["AdminQuotaSummary"];
export type AdminUsage = components["schemas"]["AdminUsageSummary"];
export type AdminSecret = components["schemas"]["AdminSecretSummary"];
export type AdminArtifact = components["schemas"]["AdminArtifactSummary"];
export type ArtifactAcl = components["schemas"]["ArtifactAcl"];

export interface RoleListData {
  roles: Role[];
  total: number;
}

export interface RoleFormData {
  name: string;
  description: string;
  permissions: string[];
}

export interface AdminUserListData {
  users: AdminUser[];
  total: number;
}

export interface AdminUserFormData {
  user_id: string;
  display_name: string;
  email: string;
  enabled: boolean;
}

export interface AdminUserRolesData {
  user_id: string;
  role_ids: string[];
}

export interface AssignableRole {
  role_id: string;
  name: string;
}

export interface AuditLogListData {
  logs: AuditLog[];
  total: number;
}

export interface AuditLogSearchForm {
  user_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  decision: string;
}

export interface AuditLogExportFile {
  filename: string;
  contentType: string;
  content: string;
}

export interface RoleSearchForm {
  keyword: string;
}

export interface AdminUserSearchForm {
  status: "all" | "enabled" | "disabled";
}

export interface CatalogDatabase {
  datasourceName: string;
  name: string;
  type: string;
  catalogName?: string;
  schemaName?: string;
  tables: string[];
}

export interface RolePermissionRecord {
  permission_type: string;
  resource_code: string;
  permission_value: string;
}

export interface AuditActionType {
  value: string;
  label: string;
}

export interface AdminOverviewData {
  datasources: AdminDatasource[];
  datasourceGrants: AdminDatasourceGrant[];
  quotas: AdminQuota[];
  usage: AdminUsage[];
  secrets: AdminSecret[];
  sessions: AdminSession[];
  artifacts: AdminArtifact[];
}

export interface DatasourceGrantFormData {
  subject_type: string;
  subject_id: string;
  datasource_key: string;
  effect: "allow" | "deny";
  scope_text: string;
}

export interface QuotaFormData {
  subject_type: string;
  subject_id: string;
  resource: string;
  limit: number;
  window_seconds: number;
  enabled: boolean;
}

export interface SecretFormData {
  name: string;
  provider: string;
  reference: string;
  description: string;
  enabled: boolean;
}

export interface ArtifactAclFormData {
  owner_user_id: string;
  visibility: "private" | "role" | "enterprise";
  allowed_roles_text: string;
  datasources_text: string;
}

export interface AuditLogListParams {
  limit: number;
  userId?: string;
  action?: string;
  resourceType?: string;
  resourceId?: string;
  decision?: string;
}

export interface AdminUserListParams {
  enabled?: boolean;
}

export interface DatasourceGrantListParams {
  subjectType?: string;
  subjectId?: string;
  datasourceKey?: string;
}

export interface QuotaListParams {
  subjectType?: string;
  subjectId?: string;
  resource?: string;
}

export interface UsageListParams {
  subjectType?: string;
  subjectId?: string;
  resource?: string;
}

export interface SecretListParams {
  prefix?: string;
}

export interface UpsertUserInput {
  display_name?: string | null;
  email?: string | null;
  enabled: boolean;
}

export interface UpsertRoleInput {
  name: string;
  description?: string | null;
  permissions?: string[];
}

export interface UpsertDatasourceGrantInput {
  effect: "allow" | "deny";
  scope?: Record<string, unknown>;
}

export interface UpsertQuotaInput {
  subject_type: string;
  subject_id?: string | null;
  resource: string;
  limit: number;
  window_seconds: number;
  enabled: boolean;
}

export interface UpsertSecretInput {
  provider: string;
  reference: string;
  description?: string | null;
  enabled: boolean;
}
