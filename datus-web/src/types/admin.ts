export interface ApiResponse<T> {
  success: boolean;
  data: T;
  errorCode?: string;
  errorMessage?: string;
}

export interface Role {
  id: number;
  role_code: string;
  role_name: string;
  role_type: string;
  description: string | null;
  is_system: boolean;
  created_at: string;
  user_count: number;
}

export interface RoleListData {
  roles: Role[];
  total: number;
  page: number;
  size: number;
}

export interface RoleFormData {
  role_code: string;
  role_name: string;
  role_type: string;
  description: string;
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

export interface AdminUser {
  id: number;
  user_id: string;
  username: string | null;
  realname: string | null;
  email: string | null;
  department: string | null;
  status: string;
  is_builtin?: boolean;
  created_at: string;
  last_login_at: string | null;
  login_count: number;
  roles: string[];
}

export interface AdminUserListData {
  users: AdminUser[];
  total: number;
  page: number;
  size: number;
}

export interface AdminUserFormData {
  user_id: string;
  username: string;
  realname: string;
  email: string;
  department: string;
}

export interface AssignableRole {
  id: number;
  role_code: string;
  role_name: string;
  role_type: string;
}

export interface AuditLog {
  id: number;
  operator_id: string;
  operator_name: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  target_name: string | null;
  detail: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogListData {
  logs: AuditLog[];
  total: number;
  page: number;
  size: number;
}

export interface AuditActionType {
  value: string;
  label: string;
}

export interface AuditLogSearchForm {
  start_date: string;
  end_date: string;
  action: string;
}

export interface RoleSearchForm {
  role_type: string;
  keyword: string;
}

export interface AdminUserSearchForm {
  keyword: string;
  status: string;
}
