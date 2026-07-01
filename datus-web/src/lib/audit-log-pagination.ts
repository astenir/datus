export const auditLogLimitOptions = [10, 20, 50, 100, 200] as const;

export type AuditLogLimitOption = (typeof auditLogLimitOptions)[number];

export const defaultAuditLogLimit: AuditLogLimitOption = 20;

export function isAuditLogLimitOption(value: number): value is AuditLogLimitOption {
  return (auditLogLimitOptions as readonly number[]).includes(value);
}
