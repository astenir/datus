import { del, get, post, put, request } from "@/lib/request";
import type {
  AdminArtifact,
  AdminDatasource,
  AdminDatasourceGrant,
  AdminSession,
  AdminSessionDetail,
  AdminUsage,
  AdminUser,
  AdminUserListParams,
  AdminUserRolesData,
  ApiResponse,
  ArtifactAcl,
  AuditLogExportFile,
  AuditLog,
  AuditLogListParams,
  DatasourceGrantListParams,
  QuotaListParams,
  Role,
  SecretListParams,
  UpsertDatasourceGrantInput,
  UpsertQuotaInput,
  UpsertRoleInput,
  UpsertSecretInput,
  UpsertUserInput,
  UsageListParams,
  AdminQuota,
  AdminSecret,
} from "@/types/admin";

function queryString(entries: Array<[string, string | number | boolean | undefined]>): string {
  const params = new URLSearchParams();
  for (const [key, value] of entries) {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

function auditLogQuery(params: AuditLogListParams): string {
  return queryString([
    ["limit", params.limit],
    ["user_id", params.userId],
    ["action", params.action],
    ["resource_type", params.resourceType],
    ["resource_id", params.resourceId],
    ["decision", params.decision],
  ]);
}

function filenameFromContentDisposition(value: string | null): string {
  const fallback = "audit-logs.csv";
  if (!value) return fallback;

  const filenameStar = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStar?.[1]) return decodeURIComponent(filenameStar[1].trim().replace(/^"|"$/g, ""));

  const filename = value.match(/filename="?([^";]+)"?/i);
  return filename?.[1]?.trim() || fallback;
}

export const adminRoleApi = {
  listRoles(): Promise<ApiResponse<Role[]>> {
    return get<ApiResponse<Role[]>>("/api/v1/admin/roles");
  },

  getRole(roleId: string): Promise<ApiResponse<Role>> {
    return get<ApiResponse<Role>>(`/api/v1/admin/roles/${encodeURIComponent(roleId)}`);
  },

  upsertRole(roleId: string, input: UpsertRoleInput): Promise<ApiResponse<Role>> {
    return put<ApiResponse<Role>>(`/api/v1/admin/roles/${encodeURIComponent(roleId)}`, input);
  },

  deleteRole(roleId: string): Promise<ApiResponse<Record<string, unknown>>> {
    return del<ApiResponse<Record<string, unknown>>>(`/api/v1/admin/roles/${encodeURIComponent(roleId)}`);
  },

  setRolePermissions(roleId: string, permissions: readonly string[]): Promise<ApiResponse<Role>> {
    return put<ApiResponse<Role>>(`/api/v1/admin/roles/${encodeURIComponent(roleId)}/permissions`, { permissions });
  },
};

export const adminUserApi = {
  listUsers(params?: AdminUserListParams): Promise<ApiResponse<AdminUser[]>> {
    const query = queryString([["enabled", params?.enabled]]);
    return get<ApiResponse<AdminUser[]>>(`/api/v1/admin/users${query}`);
  },

  getUser(userId: string): Promise<ApiResponse<AdminUser>> {
    return get<ApiResponse<AdminUser>>(`/api/v1/admin/users/${encodeURIComponent(userId)}`);
  },

  upsertUser(userId: string, input: UpsertUserInput): Promise<ApiResponse<AdminUser>> {
    return put<ApiResponse<AdminUser>>(`/api/v1/admin/users/${encodeURIComponent(userId)}`, input);
  },

  enableUser(userId: string): Promise<ApiResponse<AdminUser>> {
    return post<ApiResponse<AdminUser>>(`/api/v1/admin/users/${encodeURIComponent(userId)}/enable`);
  },

  disableUser(userId: string): Promise<ApiResponse<AdminUser>> {
    return post<ApiResponse<AdminUser>>(`/api/v1/admin/users/${encodeURIComponent(userId)}/disable`);
  },

  getUserRoles(userId: string): Promise<ApiResponse<AdminUserRolesData>> {
    return get<ApiResponse<AdminUserRolesData>>(`/api/v1/admin/users/${encodeURIComponent(userId)}/roles`);
  },

  updateUserRoles(userId: string, roleIds: readonly string[]): Promise<ApiResponse<AdminUserRolesData>> {
    return put<ApiResponse<AdminUserRolesData>>(`/api/v1/admin/users/${encodeURIComponent(userId)}/roles`, {
      role_ids: roleIds,
    });
  },
};

export const adminAuditApi = {
  listLogs(params: AuditLogListParams): Promise<ApiResponse<AuditLog[]>> {
    return get<ApiResponse<AuditLog[]>>(`/api/v1/admin/audit-logs${auditLogQuery(params)}`);
  },

  async exportLogs(params: AuditLogListParams): Promise<AuditLogExportFile> {
    const response = await request(`/api/v1/admin/audit-logs/export${auditLogQuery(params)}`, {
      method: "GET",
      headers: {
        Accept: "text/csv",
      },
    });

    return {
      filename: filenameFromContentDisposition(response.headers.get("Content-Disposition")),
      contentType: response.headers.get("Content-Type") || "text/csv;charset=utf-8",
      content: await response.text(),
    };
  },
};

export const adminSessionApi = {
  listSessions(userId?: string): Promise<ApiResponse<AdminSession[]>> {
    const query = queryString([["user_id", userId]]);
    return get<ApiResponse<AdminSession[]>>(`/api/v1/admin/sessions${query}`);
  },

  getSession(sessionId: string): Promise<ApiResponse<AdminSessionDetail>> {
    return get<ApiResponse<AdminSessionDetail>>(`/api/v1/admin/sessions/${encodeURIComponent(sessionId)}`);
  },

  stopSession(sessionId: string): Promise<ApiResponse<Record<string, unknown>>> {
    return post<ApiResponse<Record<string, unknown>>>(`/api/v1/admin/sessions/${encodeURIComponent(sessionId)}/stop`);
  },

  deleteSession(sessionId: string): Promise<ApiResponse<Record<string, unknown>>> {
    return del<ApiResponse<Record<string, unknown>>>(`/api/v1/admin/sessions/${encodeURIComponent(sessionId)}`);
  },
};

export const adminDatasourceApi = {
  listDatasources(): Promise<ApiResponse<AdminDatasource[]>> {
    return get<ApiResponse<AdminDatasource[]>>("/api/v1/admin/datasources");
  },

  listGrants(params?: DatasourceGrantListParams): Promise<ApiResponse<AdminDatasourceGrant[]>> {
    const query = queryString([
      ["subject_type", params?.subjectType],
      ["subject_id", params?.subjectId],
      ["datasource_key", params?.datasourceKey],
    ]);
    return get<ApiResponse<AdminDatasourceGrant[]>>(`/api/v1/admin/datasource-grants${query}`);
  },

  getGrant(
    subjectType: string,
    subjectId: string,
    datasourceKey: string,
  ): Promise<ApiResponse<AdminDatasourceGrant>> {
    return get<ApiResponse<AdminDatasourceGrant>>(
      `/api/v1/admin/datasource-grants/${encodeURIComponent(subjectType)}/${encodeURIComponent(subjectId)}/${encodeURIComponent(datasourceKey)}`,
    );
  },

  upsertGrant(
    subjectType: string,
    subjectId: string,
    datasourceKey: string,
    input: UpsertDatasourceGrantInput,
  ): Promise<ApiResponse<AdminDatasourceGrant>> {
    return put<ApiResponse<AdminDatasourceGrant>>(
      `/api/v1/admin/datasource-grants/${encodeURIComponent(subjectType)}/${encodeURIComponent(subjectId)}/${encodeURIComponent(datasourceKey)}`,
      input,
    );
  },

  deleteGrant(subjectType: string, subjectId: string, datasourceKey: string): Promise<ApiResponse<Record<string, unknown>>> {
    return del<ApiResponse<Record<string, unknown>>>(
      `/api/v1/admin/datasource-grants/${encodeURIComponent(subjectType)}/${encodeURIComponent(subjectId)}/${encodeURIComponent(datasourceKey)}`,
    );
  },
};

export const adminQuotaApi = {
  listQuotas(params?: QuotaListParams): Promise<ApiResponse<AdminQuota[]>> {
    const query = queryString([
      ["subject_type", params?.subjectType],
      ["subject_id", params?.subjectId],
      ["resource", params?.resource],
    ]);
    return get<ApiResponse<AdminQuota[]>>(`/api/v1/admin/quotas${query}`);
  },

  upsertQuota(input: UpsertQuotaInput): Promise<ApiResponse<AdminQuota>> {
    return put<ApiResponse<AdminQuota>>("/api/v1/admin/quotas", input);
  },

  listUsage(params?: UsageListParams): Promise<ApiResponse<AdminUsage[]>> {
    const query = queryString([
      ["subject_type", params?.subjectType],
      ["subject_id", params?.subjectId],
      ["resource", params?.resource],
    ]);
    return get<ApiResponse<AdminUsage[]>>(`/api/v1/admin/usage${query}`);
  },
};

export const adminSecretApi = {
  listSecrets(params?: SecretListParams): Promise<ApiResponse<AdminSecret[]>> {
    const query = queryString([["prefix", params?.prefix]]);
    return get<ApiResponse<AdminSecret[]>>(`/api/v1/admin/secrets${query}`);
  },

  getSecret(name: string): Promise<ApiResponse<AdminSecret>> {
    return get<ApiResponse<AdminSecret>>(`/api/v1/admin/secrets/${encodeURIComponent(name)}`);
  },

  upsertSecret(name: string, input: UpsertSecretInput): Promise<ApiResponse<AdminSecret>> {
    return put<ApiResponse<AdminSecret>>(`/api/v1/admin/secrets/${encodeURIComponent(name)}`, input);
  },

  deleteSecret(name: string): Promise<ApiResponse<Record<string, unknown>>> {
    return del<ApiResponse<Record<string, unknown>>>(`/api/v1/admin/secrets/${encodeURIComponent(name)}`);
  },
};

export const adminArtifactApi = {
  listArtifacts(): Promise<ApiResponse<AdminArtifact[]>> {
    return get<ApiResponse<AdminArtifact[]>>("/api/v1/admin/artifacts");
  },

  getAcl(artifactType: "report" | "dashboard", slug: string): Promise<ApiResponse<ArtifactAcl>> {
    return get<ApiResponse<ArtifactAcl>>(
      `/api/v1/admin/artifacts/${artifactType}/${encodeURIComponent(slug)}/acl`,
    );
  },

  putAcl(artifactType: "report" | "dashboard", slug: string, acl: ArtifactAcl): Promise<ApiResponse<ArtifactAcl>> {
    return put<ApiResponse<ArtifactAcl>>(`/api/v1/admin/artifacts/${artifactType}/${encodeURIComponent(slug)}/acl`, acl);
  },
};
