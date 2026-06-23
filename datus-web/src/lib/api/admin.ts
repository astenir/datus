import { del, get, post, put } from "@/lib/request";
import type {
  AdminUserFormData,
  AdminUserListData,
  ApiResponse,
  AssignableRole,
  AuditActionType,
  AuditLogListData,
  RoleFormData,
  RoleListData,
  RolePermissionRecord,
} from "@/types/admin";

export type RoleListParams = {
  page: number;
  size: number;
  roleType?: string;
  keyword?: string;
};

export type AdminUserListParams = {
  page: number;
  size: number;
  keyword?: string;
  status?: string;
};

export type AuditLogListParams = {
  page: number;
  size: number;
  startDate?: string;
  endDate?: string;
  action?: string;
};

export const adminRoleApi = {
  listRoles(params: RoleListParams): Promise<ApiResponse<RoleListData>> {
    const searchParams = new URLSearchParams();
    searchParams.set("page", String(params.page));
    searchParams.set("size", String(params.size));
    if (params.roleType) {
      searchParams.set("role_type", params.roleType);
    }
    if (params.keyword) {
      searchParams.set("keyword", params.keyword);
    }
    return get<ApiResponse<RoleListData>>(`/api/v1/admin/roles?${searchParams.toString()}`);
  },

  createRole(input: RoleFormData): Promise<ApiResponse<{ role_id: number }>> {
    return post<ApiResponse<{ role_id: number }>>("/api/v1/admin/roles", input);
  },

  updateRole(roleId: number, input: Pick<RoleFormData, "role_name" | "description">): Promise<unknown> {
    return put(`/api/v1/admin/roles/${roleId}`, input);
  },

  deleteRole(roleId: number): Promise<unknown> {
    return del(`/api/v1/admin/roles/${roleId}`);
  },

  getRolePermissions(roleId: number): Promise<ApiResponse<RolePermissionRecord[]>> {
    return get<ApiResponse<RolePermissionRecord[]>>(`/api/v1/admin/roles/${roleId}/permissions`);
  },

  updateRolePermissions(roleId: number, permissions: RolePermissionRecord[]): Promise<unknown> {
    return put(`/api/v1/admin/roles/${roleId}/permissions`, { permissions });
  },
};

export const adminUserApi = {
  listUsers(params: AdminUserListParams): Promise<ApiResponse<AdminUserListData>> {
    const searchParams = new URLSearchParams();
    searchParams.set("page", String(params.page));
    searchParams.set("size", String(params.size));
    if (params.keyword) {
      searchParams.set("keyword", params.keyword);
    }
    if (params.status) {
      searchParams.set("status", params.status);
    }
    return get<ApiResponse<AdminUserListData>>(`/api/v1/admin/users?${searchParams.toString()}`);
  },

  listAssignableRoles(size = 100): Promise<ApiResponse<{ roles: AssignableRole[] }>> {
    return get<ApiResponse<{ roles: AssignableRole[] }>>(`/api/v1/admin/roles?size=${size}`);
  },

  getUserRoles(userId: string): Promise<ApiResponse<Array<Pick<AssignableRole, "id" | "role_code" | "role_name">>>> {
    return get<ApiResponse<Array<Pick<AssignableRole, "id" | "role_code" | "role_name">>>>(`/api/v1/admin/users/${userId}/roles`);
  },

  updateUserRoles(userId: string, roleIds: readonly number[]): Promise<unknown> {
    return put(`/api/v1/admin/users/${userId}/roles`, { role_ids: roleIds });
  },

  updateUserStatus(userId: string, status: string): Promise<unknown> {
    return put(`/api/v1/admin/users/${userId}/status`, { status });
  },

  createUser(input: AdminUserFormData): Promise<unknown> {
    return post("/api/v1/admin/users", input);
  },
};

export const adminAuditApi = {
  listActionTypes(): Promise<ApiResponse<AuditActionType[]>> {
    return get<ApiResponse<AuditActionType[]>>("/api/v1/admin/audit-logs/actions");
  },

  listLogs(params: AuditLogListParams): Promise<ApiResponse<AuditLogListData>> {
    const searchParams = new URLSearchParams();
    searchParams.set("page", String(params.page));
    searchParams.set("size", String(params.size));
    if (params.startDate) {
      searchParams.set("start_date", params.startDate);
    }
    if (params.endDate) {
      searchParams.set("end_date", params.endDate);
    }
    if (params.action) {
      searchParams.set("action", params.action);
    }
    return get<ApiResponse<AuditLogListData>>(`/api/v1/admin/audit-logs?${searchParams.toString()}`);
  },
};
