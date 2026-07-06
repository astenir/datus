export type KnowledgePermissionAdapter = {
  hasFeaturePermission: (featureCode: string) => boolean;
  hasPermission: (permissionCode: string) => boolean;
};

export function canViewSubjectTree(permission: KnowledgePermissionAdapter): boolean {
  return permission.hasPermission("module.datasource_catalog")
    || permission.hasFeaturePermission("datasource_catalog");
}
