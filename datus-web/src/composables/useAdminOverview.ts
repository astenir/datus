import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import {
  adminArtifactApi,
  adminDatasourceApi,
  adminQuotaApi,
  adminSecretApi,
  adminSessionApi,
} from "@/lib/api";
import { usePermission } from "@/composables/usePermission";
import { useAdminPagination } from "@/composables/useAdminPagination";
import { quotaResourceOptionFor } from "@/lib/quota-options";
import {
  buildDatasourceTreeOptions,
  datasourceNodeIdsFromScope,
  datasourceScopeFromNodeIds,
  isStandardDatasourceGrantScope,
} from "@/lib/role-permissions";
import type {
  AdminArtifact,
  AdminDatasourceGrant,
  AdminOverviewData,
  AdminQuota,
  AdminSecret,
  AdminSession,
  AdminSessionDetail,
  ArtifactAclFormData,
  DatasourceGrantFormData,
  QuotaSubjectType,
  QuotaFormData,
  SecretFormData,
} from "@/types/admin";
import type { CatalogDatabase } from "@/types/admin";
import type { DatabaseInfo } from "@/types";
import type { RoleDatasourceTreeNode } from "@/lib/role-permissions";

type ArtifactAclTarget = {
  artifactType: AdminArtifact["artifact_type"];
  slug: string;
};

function cloneEmptyOverview(): AdminOverviewData {
  return {
    datasources: [],
    datasourceGrants: [],
    quotas: [],
    usage: [],
    secrets: [],
    sessions: [],
    artifacts: [],
  };
}

function scopeText(scope: Record<string, unknown> | undefined): string {
  if (!scope || Object.keys(scope).length === 0) return "{}";
  return JSON.stringify(scope, null, 2);
}

function parseScope(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};

  const parsed: unknown = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Scope 必须是 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

function isWildcardDatasourceKey(datasourceKey: string): boolean {
  return datasourceKey.trim() === "*";
}

function standardGrantScopeMode(datasourceKey: string, scope: Record<string, unknown> | undefined): DatasourceScopeMode {
  if (!scope || Object.keys(scope).length === 0) return "all";
  if (isWildcardDatasourceKey(datasourceKey)) return "json";
  return isStandardDatasourceGrantScope(scope) ? "picker" : "json";
}

function quotaSubjectTypeFromValue(value: string): QuotaSubjectType {
  if (value === "global" || value === "role" || value === "user") return value;
  return "user";
}

function toggleListValue(values: readonly string[], value: string): string[] {
  const normalizedValue = value.trim();
  if (!normalizedValue) return [...values];
  return values.includes(normalizedValue)
    ? values.filter(item => item !== normalizedValue)
    : [...values, normalizedValue];
}

function artifactKey(artifact: AdminArtifact): string {
  return `${artifact.artifact_type}:${artifact.manifest.slug}`;
}

function artifactAclTargetKey(target: ArtifactAclTarget): string {
  return `${target.artifactType}:${target.slug}`;
}

function quotaKey(quota: Pick<AdminQuota, "subject_type" | "subject_id" | "resource">): string {
  return `${quota.subject_type}:${quota.subject_id}:${quota.resource}`;
}

function catalogDatabasesForDatasource(datasourceKey: string, databases: readonly DatabaseInfo[]): CatalogDatabase[] {
  return databases.map((database) => ({
    datasourceName: datasourceKey,
    name: database.name,
    type: database.type ?? "",
    catalogName: database.catalog_name,
    schemaName: database.schema_name,
    tables: Array.isArray(database.tables)
      ? database.tables.filter((table): table is string => typeof table === "string" && table.trim().length > 0)
      : [],
  }));
}

function findAncestorNodeIds(
  nodes: readonly RoleDatasourceTreeNode[],
  nodeId: string,
  ancestors: readonly string[] = []
): string[] {
  for (const node of nodes) {
    if (node.id === nodeId) {
      return [...ancestors];
    }

    const childAncestors = findAncestorNodeIds(node.children ?? [], nodeId, [...ancestors, node.id]);
    if (childAncestors.length > 0) {
      return childAncestors;
    }
  }

  return [];
}

function findTreeNode(nodes: readonly RoleDatasourceTreeNode[], nodeId: string): RoleDatasourceTreeNode | null {
  for (const node of nodes) {
    if (node.id === nodeId) return node;
    const childNode = findTreeNode(node.children ?? [], nodeId);
    if (childNode) return childNode;
  }
  return null;
}

function collectDescendantNodeIds(node: RoleDatasourceTreeNode): string[] {
  return (node.children ?? []).flatMap((child) => [
    child.id,
    ...collectDescendantNodeIds(child),
  ]);
}

export type DatasourceScopeMode = "all" | "picker" | "json";

export function useAdminOverview() {
  const permission = usePermission();
  const loading = shallowRef(false);
  const savingGrant = shallowRef(false);
  const savingQuota = shallowRef(false);
  const savingSecret = shallowRef(false);
  const savingArtifactAcl = shallowRef(false);
  const actingSessionId = shallowRef<string | null>(null);
  const deletingGrantKey = shallowRef<string | null>(null);
  const deletingQuotaKey = shallowRef<string | null>(null);
  const deletingSecretName = shallowRef<string | null>(null);
  const loadingGrantDetail = shallowRef(false);
  const loadingGrantCatalog = shallowRef(false);
  const selectedGrantRouteKey = shallowRef<string | null>(null);
  const grantDetailError = shallowRef<string | null>(null);
  const grantCatalogError = shallowRef<string | null>(null);
  const loadingSecretDetail = shallowRef(false);
  const selectedSecretName = shallowRef<string | null>(null);
  const secretDetailError = shallowRef<string | null>(null);
  const loadingArtifactAcl = shallowRef(false);
  const selectedArtifactAclKey = shallowRef<string | null>(null);
  const artifactAclError = shallowRef<string | null>(null);
  const loadingSessionDetail = shallowRef(false);
  const showSessionDetailDialog = shallowRef(false);
  const selectedSessionDetailId = shallowRef<string | null>(null);
  const selectedSessionDetail = shallowRef<AdminSessionDetail | null>(null);
  const sessionDetailError = shallowRef<string | null>(null);
  let grantDetailRequestId = 0;
  let grantCatalogRequestId = 0;
  let secretDetailRequestId = 0;
  let artifactAclRequestId = 0;
  let sessionDetailRequestId = 0;
  let grantListRequestId = 0;
  let quotaListRequestId = 0;
  let sessionListRequestId = 0;
  let secretListRequestId = 0;
  let artifactListRequestId = 0;

  const grantPagination = useAdminPagination();
  const quotaPagination = useAdminPagination();
  const sessionPagination = useAdminPagination();
  const secretPagination = useAdminPagination();
  const artifactPagination = useAdminPagination();
  let grantListFilters: { effect?: "allow" | "deny"; search?: string } = {};
  let quotaListFilters: { enabled?: boolean; search?: string } = {};
  let sessionListFilters: { state?: "running" | "stopped"; search?: string } = {};
  let secretListFilters: { enabled?: boolean; search?: string } = {};
  let artifactListFilters: { artifactType?: AdminArtifact["artifact_type"]; search?: string } = {};

  const data = ref<AdminOverviewData>(cloneEmptyOverview());

  const showGrantDialog = shallowRef(false);
  const editingGrant = shallowRef<AdminDatasourceGrant | null>(null);
  const grantForm = ref<DatasourceGrantFormData>({
    subject_type: "user",
    subject_id: "",
    datasource_key: "",
    effect: "allow",
    scope_text: "{}",
  });
  const grantScopeMode = shallowRef<DatasourceScopeMode>("all");
  const selectedGrantNodes = ref<string[]>([]);
  const grantCatalogDatabases = ref<CatalogDatabase[]>([]);

  const showQuotaDialog = shallowRef(false);
  const editingQuota = shallowRef<AdminQuota | null>(null);
  const quotaForm = ref<QuotaFormData>({
    subject_type: "user",
    subject_id: "",
    resource: "chat.stream",
    limit: 100000,
    window_seconds: 86400,
    enabled: true,
  });

  const showSecretDialog = shallowRef(false);
  const editingSecret = shallowRef<AdminSecret | null>(null);
  const secretForm = ref<SecretFormData>({
    name: "",
    provider: "env",
    reference: "",
    description: "",
    enabled: true,
  });

  const showArtifactAclDialog = shallowRef(false);
  const editingArtifact = shallowRef<AdminArtifact | null>(null);
  const editingArtifactAclTarget = shallowRef<ArtifactAclTarget | null>(null);
  const artifactAclForm = ref<ArtifactAclFormData>({
    owner_user_id: "",
    visibility: "private",
    allowed_roles: [],
    allowed_user_ids: [],
    datasources: [],
  });

  const defaultDatasourceName = computed(() => data.value.datasources.find(item => item.is_default)?.name ?? "");
  const runningSessionCount = computed(() => data.value.sessions.filter(session => session.is_running).length);
  const grantCount = computed(() => data.value.datasourceGrants.length);
  const quotaCount = computed(() => data.value.quotas.length);
  const secretCount = computed(() => data.value.secrets.length);
  const grantCatalogTree = computed(() => buildDatasourceTreeOptions(grantCatalogDatabases.value));
  const grantSelectedScopePreview = computed(() => {
    if (grantScopeMode.value === "all") return "{}";
    if (grantScopeMode.value === "json") return grantForm.value.scope_text.trim() || "{}";
    return JSON.stringify(datasourceScopeFromNodeIds(grantForm.value.datasource_key, selectedGrantNodes.value), null, 2);
  });
  const canManageDatasources = computed(() => permission.hasPermission("module.admin.datasources"));
  const canManageQuotas = computed(() => permission.hasPermission("module.admin.quotas"));
  const canManageSessions = computed(() => permission.hasPermission("module.admin.sessions"));
  const canManageSecrets = computed(() => permission.hasPermission("module.admin.secrets"));
  const canManageArtifacts = computed(() => permission.hasPermission("module.admin.artifacts"));

  async function fetchPermissionsIfNeeded(): Promise<void> {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
  }

  function grantRouteKey(subjectType: string, subjectId: string, datasourceKey: string): string {
    return `${subjectType}:${subjectId}:${datasourceKey}`;
  }

  function setGrantFormFromGrant(grant: AdminDatasourceGrant) {
    const scope = grant.scope ?? {};
    editingGrant.value = grant;
    grantForm.value = {
      subject_type: grant.subject_type,
      subject_id: grant.subject_id,
      datasource_key: grant.datasource_key,
      effect: grant.effect === "deny" ? "deny" : "allow",
      scope_text: scopeText(scope),
    };
    grantScopeMode.value = standardGrantScopeMode(grant.datasource_key, scope);
    selectedGrantNodes.value = grantScopeMode.value === "picker"
      ? datasourceNodeIdsFromScope(grant.datasource_key, scope, grantCatalogDatabases.value)
      : [];
  }

  function setSecretFormFromSecret(secret: AdminSecret) {
    editingSecret.value = secret;
    secretForm.value = {
      name: secret.name,
      provider: secret.provider,
      reference: "",
      description: secret.description ?? "",
      enabled: secret.enabled,
    };
  }

  async function loadOverview() {
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      const [
        datasourceResult,
        grantResult,
        quotaResult,
        usageResult,
        secretResult,
        sessionResult,
        artifactResult,
      ] = await Promise.all([
        canManageDatasources.value ? adminDatasourceApi.listDatasources() : Promise.resolve(null),
        canManageDatasources.value ? adminDatasourceApi.listGrants({ limit: grantPagination.pageSize.value, offset: 0 }) : Promise.resolve(null),
        canManageQuotas.value ? adminQuotaApi.listQuotas({ limit: quotaPagination.pageSize.value, offset: 0 }) : Promise.resolve(null),
        canManageQuotas.value ? adminQuotaApi.listUsage({ limit: 100, offset: 0 }) : Promise.resolve(null),
        canManageSecrets.value ? adminSecretApi.listSecrets({ limit: secretPagination.pageSize.value, offset: 0 }) : Promise.resolve(null),
        canManageSessions.value ? adminSessionApi.listSessions({ limit: sessionPagination.pageSize.value, offset: 0 }) : Promise.resolve(null),
        canManageArtifacts.value ? adminArtifactApi.listArtifacts({ limit: artifactPagination.pageSize.value, offset: 0 }) : Promise.resolve(null),
      ]);

      data.value = {
        datasources: datasourceResult?.data ?? [],
        datasourceGrants: grantPagination.applyResponse(grantResult),
        quotas: quotaPagination.applyResponse(quotaResult),
        usage: usageResult?.data ?? [],
        secrets: secretPagination.applyResponse(secretResult),
        sessions: sessionPagination.applyResponse(sessionResult),
        artifacts: artifactPagination.applyResponse(artifactResult),
      };
    } catch (err) {
      console.error("加载管理概览失败:", err);
      data.value = cloneEmptyOverview();
      toast.error("加载管理概览失败");
    } finally {
      loading.value = false;
    }
  }

  async function loadDatasourceGrants() {
    const requestId = grantListRequestId + 1;
    grantListRequestId = requestId;
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      if (!canManageDatasources.value) {
        data.value = {
          ...data.value,
          datasources: [],
          datasourceGrants: [],
        };
        return;
      }
      const [datasourceResult, grantResult] = await Promise.all([
        adminDatasourceApi.listDatasources(),
        adminDatasourceApi.listGrants({
          ...grantListFilters,
          limit: grantPagination.pageSize.value,
          offset: grantPagination.offset.value,
        }),
      ]);
      if (requestId !== grantListRequestId) return;
      data.value = {
        ...data.value,
        datasources: datasourceResult.data ?? [],
        datasourceGrants: grantPagination.applyResponse(grantResult),
      };
    } catch (err) {
      if (requestId !== grantListRequestId) return;
      console.error("加载数据授权失败:", err);
      toast.error("加载数据授权失败");
    } finally {
      if (requestId === grantListRequestId) loading.value = false;
    }
  }

  async function loadQuotasAndUsage() {
    const requestId = quotaListRequestId + 1;
    quotaListRequestId = requestId;
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      if (!canManageQuotas.value) {
        data.value = {
          ...data.value,
          quotas: [],
          usage: [],
        };
        return;
      }
      const [quotaResult, usageResult] = await Promise.all([
        adminQuotaApi.listQuotas({
          ...quotaListFilters,
          limit: quotaPagination.pageSize.value,
          offset: quotaPagination.offset.value,
        }),
        adminQuotaApi.listUsage({ search: quotaListFilters.search, limit: 100, offset: 0 }),
      ]);
      if (requestId !== quotaListRequestId) return;
      data.value = {
        ...data.value,
        quotas: quotaPagination.applyResponse(quotaResult),
        usage: usageResult.data ?? [],
      };
    } catch (err) {
      if (requestId !== quotaListRequestId) return;
      console.error("加载额度与用量失败:", err);
      toast.error("加载额度与用量失败");
    } finally {
      if (requestId === quotaListRequestId) loading.value = false;
    }
  }

  async function loadSessions() {
    const requestId = sessionListRequestId + 1;
    sessionListRequestId = requestId;
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      if (!canManageSessions.value) {
        data.value = {
          ...data.value,
          sessions: [],
        };
        return;
      }
      const result = await adminSessionApi.listSessions({
        ...sessionListFilters,
        limit: sessionPagination.pageSize.value,
        offset: sessionPagination.offset.value,
      });
      if (requestId !== sessionListRequestId) return;
      data.value = {
        ...data.value,
        sessions: sessionPagination.applyResponse(result),
      };
    } catch (err) {
      if (requestId !== sessionListRequestId) return;
      console.error("加载会话失败:", err);
      toast.error("加载会话失败");
    } finally {
      if (requestId === sessionListRequestId) loading.value = false;
    }
  }

  async function loadSecrets() {
    const requestId = secretListRequestId + 1;
    secretListRequestId = requestId;
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      if (!canManageSecrets.value) {
        data.value = {
          ...data.value,
          secrets: [],
        };
        return;
      }
      const result = await adminSecretApi.listSecrets({
        ...secretListFilters,
        limit: secretPagination.pageSize.value,
        offset: secretPagination.offset.value,
      });
      if (requestId !== secretListRequestId) return;
      data.value = {
        ...data.value,
        secrets: secretPagination.applyResponse(result),
      };
    } catch (err) {
      if (requestId !== secretListRequestId) return;
      console.error("加载密钥引用失败:", err);
      toast.error("加载密钥引用失败");
    } finally {
      if (requestId === secretListRequestId) loading.value = false;
    }
  }

  async function loadArtifacts() {
    const requestId = artifactListRequestId + 1;
    artifactListRequestId = requestId;
    loading.value = true;
    try {
      await fetchPermissionsIfNeeded();
      if (!canManageArtifacts.value) {
        data.value = {
          ...data.value,
          artifacts: [],
        };
        return;
      }
      const result = await adminArtifactApi.listArtifacts({
        ...artifactListFilters,
        limit: artifactPagination.pageSize.value,
        offset: artifactPagination.offset.value,
      });
      if (requestId !== artifactListRequestId) return;
      data.value = {
        ...data.value,
        artifacts: artifactPagination.applyResponse(result),
      };
    } catch (err) {
      if (requestId !== artifactListRequestId) return;
      console.error("加载产物 ACL 失败:", err);
      toast.error("加载产物 ACL 失败");
    } finally {
      if (requestId === artifactListRequestId) loading.value = false;
    }
  }

  function pageActions(pagination: ReturnType<typeof useAdminPagination>, load: () => Promise<void>) {
    return {
      next: () => {
        if (pagination.prepareNext()) void load();
      },
      previous: () => {
        if (pagination.preparePrevious()) void load();
      },
      setPageSize: (value: number) => {
        if (pagination.setPageSize(value)) void load();
      },
    };
  }

  const grantPageActions = pageActions(grantPagination, loadDatasourceGrants);
  const quotaPageActions = pageActions(quotaPagination, loadQuotasAndUsage);
  const sessionPageActions = pageActions(sessionPagination, loadSessions);
  const secretPageActions = pageActions(secretPagination, loadSecrets);
  const artifactPageActions = pageActions(artifactPagination, loadArtifacts);

  function applyGrantListFilters(filters: { effect?: "allow" | "deny"; search?: string }) {
    grantListFilters = filters;
    grantPagination.reset();
    void loadDatasourceGrants();
  }

  function applyQuotaListFilters(filters: { enabled?: boolean; search?: string }) {
    quotaListFilters = filters;
    quotaPagination.reset();
    void loadQuotasAndUsage();
  }

  function applySessionListFilters(filters: { state?: "running" | "stopped"; search?: string }) {
    sessionListFilters = filters;
    sessionPagination.reset();
    void loadSessions();
  }

  function applySecretListFilters(filters: { enabled?: boolean; search?: string }) {
    secretListFilters = filters;
    secretPagination.reset();
    void loadSecrets();
  }

  function applyArtifactListFilters(filters: { artifactType?: AdminArtifact["artifact_type"]; search?: string }) {
    artifactListFilters = filters;
    artifactPagination.reset();
    void loadArtifacts();
  }

  async function loadGrantCatalog(datasourceKey = grantForm.value.datasource_key) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    const normalizedDatasourceKey = datasourceKey.trim();
    grantCatalogError.value = null;
    grantCatalogDatabases.value = [];
    if (!canManageDatasources.value) return;
    if (!normalizedDatasourceKey) return;
    if (isWildcardDatasourceKey(normalizedDatasourceKey)) return;

    const requestId = grantCatalogRequestId + 1;
    grantCatalogRequestId = requestId;
    loadingGrantCatalog.value = true;
    try {
      const result = await adminDatasourceApi.listCatalog(normalizedDatasourceKey);
      if (requestId !== grantCatalogRequestId) return;

      if (!result.success) {
        const message = result.errorCode === "REQUEST_TIMEOUT"
          ? "数据源目录加载超时，请稍后重试"
          : "加载数据源目录失败";
        grantCatalogError.value = message;
        grantCatalogDatabases.value = [];
        toast.error(message);
        return;
      }

      grantCatalogDatabases.value = catalogDatabasesForDatasource(
        normalizedDatasourceKey,
        result.data?.databases ?? [],
      );
      if (editingGrant.value?.datasource_key === normalizedDatasourceKey && grantScopeMode.value === "picker") {
        selectedGrantNodes.value = datasourceNodeIdsFromScope(
          normalizedDatasourceKey,
          editingGrant.value.scope ?? {},
          grantCatalogDatabases.value,
        );
      }
    } catch (err) {
      if (requestId !== grantCatalogRequestId) return;
      console.error("加载数据源目录失败:", err);
      const message = err instanceof Error && /timeout|timed out|超时/i.test(err.message)
        ? "数据源目录加载超时，请稍后重试"
        : "加载数据源目录失败，请稍后重试";
      grantCatalogError.value = message;
      grantCatalogDatabases.value = [];
      toast.error(message);
    } finally {
      if (requestId === grantCatalogRequestId) {
        loadingGrantCatalog.value = false;
      }
    }
  }

  function openCreateGrantDialog() {
    if (!canManageDatasources.value) return;
    grantDetailRequestId += 1;
    selectedGrantRouteKey.value = null;
    grantDetailError.value = null;
    loadingGrantDetail.value = false;
    editingGrant.value = null;
    grantForm.value = {
      subject_type: "user",
      subject_id: "",
      datasource_key: defaultDatasourceName.value || data.value.datasources[0]?.name || "",
      effect: "allow",
      scope_text: "{}",
    };
    grantScopeMode.value = "all";
    selectedGrantNodes.value = [];
    showGrantDialog.value = true;
    void loadGrantCatalog();
  }

  function openEditGrantDialog(grant: AdminDatasourceGrant) {
    if (!canManageDatasources.value) return;
    grantDetailRequestId += 1;
    selectedGrantRouteKey.value = grantRouteKey(grant.subject_type, grant.subject_id, grant.datasource_key);
    grantDetailError.value = null;
    loadingGrantDetail.value = false;
    setGrantFormFromGrant(grant);
    showGrantDialog.value = true;
    void loadGrantCatalog(grant.datasource_key);
  }

  async function openGrantDetail(subjectType: string, subjectId: string, datasourceKey: string) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageDatasources.value) return;
    const normalizedSubjectType = subjectType.trim();
    const normalizedSubjectId = subjectId.trim();
    const normalizedDatasourceKey = datasourceKey.trim();
    if (!normalizedSubjectType || !normalizedSubjectId || !normalizedDatasourceKey) return;

    const requestId = grantDetailRequestId + 1;
    grantDetailRequestId = requestId;
    selectedGrantRouteKey.value = grantRouteKey(normalizedSubjectType, normalizedSubjectId, normalizedDatasourceKey);
    editingGrant.value = null;
    grantDetailError.value = null;
    loadingGrantDetail.value = true;
    grantForm.value = {
      subject_type: normalizedSubjectType,
      subject_id: normalizedSubjectId,
      datasource_key: normalizedDatasourceKey,
      effect: "allow",
      scope_text: "{}",
    };
    grantScopeMode.value = "all";
    selectedGrantNodes.value = [];
    showGrantDialog.value = true;
    void loadGrantCatalog(normalizedDatasourceKey);

    try {
      const result = await adminDatasourceApi.getGrant(
        normalizedSubjectType,
        normalizedSubjectId,
        normalizedDatasourceKey,
      );
      if (requestId !== grantDetailRequestId) return;

      if (result.data) {
        setGrantFormFromGrant(result.data);
      } else {
        grantDetailError.value = "未找到数据授权详情";
      }
    } catch (err) {
      if (requestId !== grantDetailRequestId) return;
      console.error("加载数据授权详情失败:", err);
      grantDetailError.value = "加载数据授权详情失败";
      toast.error("加载数据授权详情失败");
    } finally {
      if (requestId === grantDetailRequestId) {
        loadingGrantDetail.value = false;
      }
    }
  }

  function closeGrantDialog() {
    grantDetailRequestId += 1;
    grantCatalogRequestId += 1;
    showGrantDialog.value = false;
    selectedGrantRouteKey.value = null;
    editingGrant.value = null;
    grantDetailError.value = null;
    grantCatalogError.value = null;
    loadingGrantDetail.value = false;
    loadingGrantCatalog.value = false;
    selectedGrantNodes.value = [];
    grantCatalogDatabases.value = [];
  }

  function setGrantSubjectType(value: unknown) {
    if (value !== "user" && value !== "role") return;
    if (grantForm.value.subject_type !== value) {
      grantForm.value.subject_id = "";
    }
    grantForm.value.subject_type = value;
  }

  function setGrantDatasource(value: unknown) {
    if (typeof value !== "string") return;
    const normalizedDatasourceKey = value.trim();
    if (!normalizedDatasourceKey) return;
    grantForm.value.datasource_key = normalizedDatasourceKey;
    selectedGrantNodes.value = [];
    grantCatalogDatabases.value = [];
    void loadGrantCatalog(normalizedDatasourceKey);
  }

  function setGrantScopeMode(value: unknown) {
    if (value !== "all" && value !== "picker" && value !== "json") return;
    if (value === "picker" && isWildcardDatasourceKey(grantForm.value.datasource_key)) {
      toast.error("通配数据源 * 不支持目录选择器，请使用整个数据源或 JSON 范围");
      return;
    }
    grantScopeMode.value = value;
    if (value === "all") {
      selectedGrantNodes.value = [];
      grantForm.value.scope_text = "{}";
      return;
    }
    if (value === "picker") {
      if (!grantCatalogDatabases.value.length) {
        void loadGrantCatalog();
      }
      return;
    }
    if (!grantForm.value.scope_text.trim()) {
      grantForm.value.scope_text = "{}";
    }
  }

  function toggleGrantNode(nodeId: string) {
    const selected = new Set(selectedGrantNodes.value);
    const treeNode = findTreeNode(grantCatalogTree.value, nodeId);
    const descendantIds = treeNode ? collectDescendantNodeIds(treeNode) : [];

    if (selected.has(nodeId)) {
      selected.delete(nodeId);
      for (const descendantId of descendantIds) {
        selected.delete(descendantId);
      }
    } else {
      for (const ancestorId of findAncestorNodeIds(grantCatalogTree.value, nodeId)) {
        selected.delete(ancestorId);
      }
      for (const descendantId of descendantIds) {
        selected.delete(descendantId);
      }
      selected.add(nodeId);
    }

    selectedGrantNodes.value = Array.from(selected);
  }

  function grantScopeFromForm(): Record<string, unknown> | null {
    if (grantScopeMode.value === "all") return {};
    if (grantScopeMode.value === "json") return parseScope(grantForm.value.scope_text);

    if (selectedGrantNodes.value.length === 0) {
      toast.error("请选择库、Schema 或表，或切换为全量授权");
      return null;
    }
    return datasourceScopeFromNodeIds(grantForm.value.datasource_key, selectedGrantNodes.value);
  }

  async function saveGrant() {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageDatasources.value) return;
    const subjectType = grantForm.value.subject_type.trim();
    const subjectId = grantForm.value.subject_id.trim();
    const datasourceKey = grantForm.value.datasource_key.trim();
    if (!subjectType || !subjectId || !datasourceKey) {
      toast.error("请填写授权主体和数据源");
      return;
    }

    let scope: Record<string, unknown> | null;
    try {
      scope = grantScopeFromForm();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Scope JSON 无效");
      return;
    }
    if (!scope) return;

    savingGrant.value = true;
    try {
      await adminDatasourceApi.upsertGrant(subjectType, subjectId, datasourceKey, {
        effect: grantForm.value.effect,
        scope,
      });
      closeGrantDialog();
      await loadDatasourceGrants();
    } catch (err) {
      console.error("保存数据授权失败:", err);
      toast.error("保存数据授权失败");
    } finally {
      savingGrant.value = false;
    }
  }

  async function deleteGrant(grant: AdminDatasourceGrant) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageDatasources.value) return;
    const key = `${grant.subject_type}:${grant.subject_id}:${grant.datasource_key}`;
    deletingGrantKey.value = key;
    try {
      await adminDatasourceApi.deleteGrant(grant.subject_type, grant.subject_id, grant.datasource_key);
      await loadDatasourceGrants();
    } catch (err) {
      console.error("删除数据授权失败:", err);
      toast.error("删除数据授权失败");
    } finally {
      deletingGrantKey.value = null;
    }
  }

  function openCreateQuotaDialog() {
    if (!canManageQuotas.value) return;
    editingQuota.value = null;
    quotaForm.value = {
      subject_type: "user",
      subject_id: "",
      resource: "chat.stream",
      limit: 100000,
      window_seconds: 86400,
      enabled: true,
    };
    showQuotaDialog.value = true;
  }

  function openEditQuotaDialog(quota: AdminQuota) {
    if (!canManageQuotas.value) return;
    editingQuota.value = quota;
    const subjectType = quotaSubjectTypeFromValue(quota.subject_type);
    quotaForm.value = {
      subject_type: subjectType,
      subject_id: subjectType === "global" ? "*" : quota.subject_id,
      resource: quota.resource,
      limit: quota.limit,
      window_seconds: quota.window_seconds,
      enabled: quota.enabled,
    };
    showQuotaDialog.value = true;
  }

  function setQuotaSubjectType(value: unknown) {
    if (value !== "global" && value !== "role" && value !== "user") return;
    const subjectType: QuotaSubjectType = value;
    if (quotaForm.value.subject_type !== subjectType) {
      quotaForm.value.subject_id = subjectType === "global" ? "*" : "";
    }
    quotaForm.value.subject_type = subjectType;
  }

  function setQuotaSubjectId(value: unknown) {
    if (typeof value !== "string") return;
    quotaForm.value.subject_id = value.trim();
  }

  function setQuotaResource(value: unknown) {
    if (typeof value !== "string") return;
    const resource = value.trim();
    if (!resource) return;
    quotaForm.value.resource = resource;
  }

  function setQuotaEnabled(value: unknown) {
    if (typeof value !== "boolean") return;
    quotaForm.value.enabled = value;
  }

  async function saveQuota() {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageQuotas.value) return;
    const subjectType = quotaSubjectTypeFromValue(quotaForm.value.subject_type);
    const subjectId = subjectType === "global" ? "*" : quotaForm.value.subject_id.trim();
    const resource = quotaForm.value.resource.trim();
    if (
      (subjectType !== "global" && !subjectId)
      || !quotaResourceOptionFor(resource)
      || quotaForm.value.limit <= 0
      || quotaForm.value.window_seconds <= 0
    ) {
      toast.error("请填写有效的额度主体、资源、限制和窗口");
      return;
    }

    savingQuota.value = true;
    try {
      await adminQuotaApi.upsertQuota({
        subject_type: subjectType,
        subject_id: subjectId,
        resource,
        limit: Number(quotaForm.value.limit),
        window_seconds: Number(quotaForm.value.window_seconds),
        enabled: quotaForm.value.enabled,
      });
      showQuotaDialog.value = false;
      await loadQuotasAndUsage();
    } catch (err) {
      console.error("保存额度失败:", err);
      toast.error("保存额度失败");
    } finally {
      savingQuota.value = false;
    }
  }

  async function deleteQuota(quota: AdminQuota) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageQuotas.value) return;
    const key = quotaKey(quota);
    deletingQuotaKey.value = key;
    try {
      await adminQuotaApi.deleteQuota({
        subject_type: quotaSubjectTypeFromValue(quota.subject_type),
        subject_id: quota.subject_type === "global" ? "*" : quota.subject_id,
        resource: quota.resource,
      });
      await loadQuotasAndUsage();
    } catch (err) {
      console.error("删除额度失败:", err);
      toast.error("删除额度失败");
    } finally {
      deletingQuotaKey.value = null;
    }
  }

  function openCreateSecretDialog() {
    if (!canManageSecrets.value) return;
    secretDetailRequestId += 1;
    selectedSecretName.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
    editingSecret.value = null;
    secretForm.value = {
      name: "",
      provider: "env",
      reference: "",
      description: "",
      enabled: true,
    };
    showSecretDialog.value = true;
  }

  function openEditSecretDialog(secret: AdminSecret) {
    if (!canManageSecrets.value) return;
    secretDetailRequestId += 1;
    selectedSecretName.value = secret.name;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
    setSecretFormFromSecret(secret);
    showSecretDialog.value = true;
  }

  async function openSecretDetail(name: string) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSecrets.value) return;
    const normalizedName = name.trim();
    if (!normalizedName) return;

    const requestId = secretDetailRequestId + 1;
    secretDetailRequestId = requestId;
    selectedSecretName.value = normalizedName;
    editingSecret.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = true;
    secretForm.value = {
      name: normalizedName,
      provider: "",
      reference: "",
      description: "",
      enabled: true,
    };
    showSecretDialog.value = true;

    try {
      const result = await adminSecretApi.getSecret(normalizedName);
      if (requestId !== secretDetailRequestId) return;

      if (result.data) {
        setSecretFormFromSecret(result.data);
      } else {
        secretDetailError.value = "未找到密钥引用详情";
      }
    } catch (err) {
      if (requestId !== secretDetailRequestId) return;
      console.error("加载密钥引用详情失败:", err);
      secretDetailError.value = "加载密钥引用详情失败";
      toast.error("加载密钥引用详情失败");
    } finally {
      if (requestId === secretDetailRequestId) {
        loadingSecretDetail.value = false;
      }
    }
  }

  function closeSecretDialog() {
    secretDetailRequestId += 1;
    showSecretDialog.value = false;
    selectedSecretName.value = null;
    editingSecret.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
  }

  async function saveSecret() {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSecrets.value) return;
    const name = secretForm.value.name.trim();
    const provider = secretForm.value.provider.trim();
    const reference = secretForm.value.reference.trim();
    if (!name || !provider || !reference) {
      toast.error("请填写密钥名称、Provider 和引用");
      return;
    }

    savingSecret.value = true;
    try {
      await adminSecretApi.upsertSecret(name, {
        provider,
        reference,
        description: secretForm.value.description.trim() || null,
        enabled: secretForm.value.enabled,
      });
      closeSecretDialog();
      await loadSecrets();
    } catch (err) {
      console.error("保存密钥引用失败:", err);
      toast.error("保存密钥引用失败");
    } finally {
      savingSecret.value = false;
    }
  }

  async function deleteSecret(secret: AdminSecret) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSecrets.value) return;
    deletingSecretName.value = secret.name;
    try {
      await adminSecretApi.deleteSecret(secret.name);
      await loadSecrets();
    } catch (err) {
      console.error("删除密钥引用失败:", err);
      toast.error("删除密钥引用失败");
    } finally {
      deletingSecretName.value = null;
    }
  }

  function setArtifactAclTarget(target: ArtifactAclTarget) {
    editingArtifactAclTarget.value = target;
    selectedArtifactAclKey.value = artifactAclTargetKey(target);
    editingArtifact.value = data.value.artifacts.find(item =>
      item.artifact_type === target.artifactType && item.manifest.slug === target.slug
    ) ?? null;
  }

  async function openArtifactAclTarget(target: ArtifactAclTarget) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageArtifacts.value) return;
    const requestId = artifactAclRequestId + 1;
    artifactAclRequestId = requestId;
    setArtifactAclTarget(target);
    artifactAclError.value = null;
    loadingArtifactAcl.value = true;
    artifactAclForm.value = {
      owner_user_id: "",
      visibility: "private",
      allowed_roles: [],
      allowed_user_ids: [],
      datasources: [...(editingArtifact.value?.manifest.datasources ?? [])],
    };
    showArtifactAclDialog.value = true;

    try {
      const result = await adminArtifactApi.getAcl(target.artifactType, target.slug);
      if (requestId !== artifactAclRequestId) return;

      const acl = result.data;
      if (acl) {
        artifactAclForm.value = {
          owner_user_id: acl.owner_user_id,
          visibility: acl.visibility,
          allowed_roles: acl.allowed_roles ?? [],
          allowed_user_ids: acl.allowed_user_ids ?? [],
          datasources: acl.datasources ?? [],
        };
      } else {
        artifactAclError.value = "未找到产物 ACL";
      }
    } catch (err) {
      if (requestId !== artifactAclRequestId) return;
      console.error("加载产物 ACL 失败:", err);
      artifactAclError.value = "加载产物 ACL 失败";
      toast.error("加载产物 ACL 失败");
    } finally {
      if (requestId === artifactAclRequestId) {
        loadingArtifactAcl.value = false;
      }
    }
  }

  async function openArtifactAclDialog(artifact: AdminArtifact) {
    await openArtifactAclTarget({
      artifactType: artifact.artifact_type,
      slug: artifact.manifest.slug,
    });
  }

  async function openArtifactAclDetail(artifactType: AdminArtifact["artifact_type"], slug: string) {
    const normalizedSlug = slug.trim();
    if (!normalizedSlug) return;

    await openArtifactAclTarget({
      artifactType,
      slug: normalizedSlug,
    });
  }

  function closeArtifactAclDialog() {
    artifactAclRequestId += 1;
    showArtifactAclDialog.value = false;
    selectedArtifactAclKey.value = null;
    editingArtifact.value = null;
    editingArtifactAclTarget.value = null;
    artifactAclError.value = null;
    loadingArtifactAcl.value = false;
  }

  function toggleArtifactAclRole(roleId: string) {
    artifactAclForm.value.allowed_roles = toggleListValue(artifactAclForm.value.allowed_roles, roleId);
  }

  function toggleArtifactAclUser(userId: string) {
    artifactAclForm.value.allowed_user_ids = toggleListValue(artifactAclForm.value.allowed_user_ids, userId);
  }

  async function saveArtifactAcl() {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageArtifacts.value) return;
    if (!editingArtifactAclTarget.value) return;

    const ownerUserId = artifactAclForm.value.owner_user_id.trim();
    if (!ownerUserId) {
      toast.error("请填写产物所有者");
      return;
    }

    savingArtifactAcl.value = true;
    try {
      await adminArtifactApi.putAcl(editingArtifactAclTarget.value.artifactType, editingArtifactAclTarget.value.slug, {
        owner_user_id: ownerUserId,
        visibility: artifactAclForm.value.visibility,
        allowed_roles: artifactAclForm.value.allowed_roles,
        allowed_user_ids: artifactAclForm.value.allowed_user_ids,
        datasources: artifactAclForm.value.datasources,
      });
      closeArtifactAclDialog();
      await loadArtifacts();
    } catch (err) {
      console.error("保存产物 ACL 失败:", err);
      toast.error("保存产物 ACL 失败");
    } finally {
      savingArtifactAcl.value = false;
    }
  }

  async function openSessionDetail(sessionId: string) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSessions.value) return;
    const normalizedSessionId = sessionId.trim();
    if (!normalizedSessionId) return;

    const requestId = sessionDetailRequestId + 1;
    sessionDetailRequestId = requestId;
    showSessionDetailDialog.value = true;
    selectedSessionDetailId.value = normalizedSessionId;
    selectedSessionDetail.value = null;
    sessionDetailError.value = null;
    loadingSessionDetail.value = true;

    try {
      const result = await adminSessionApi.getSession(normalizedSessionId);
      if (requestId !== sessionDetailRequestId) return;
      selectedSessionDetail.value = result.data ?? null;
      if (!selectedSessionDetail.value) {
        sessionDetailError.value = "未找到会话详情";
      }
    } catch (err) {
      if (requestId !== sessionDetailRequestId) return;
      console.error("加载会话详情失败:", err);
      sessionDetailError.value = "加载会话详情失败";
      toast.error("加载会话详情失败");
    } finally {
      if (requestId === sessionDetailRequestId) {
        loadingSessionDetail.value = false;
      }
    }
  }

  function closeSessionDetail() {
    sessionDetailRequestId += 1;
    showSessionDetailDialog.value = false;
    selectedSessionDetailId.value = null;
    selectedSessionDetail.value = null;
    sessionDetailError.value = null;
    loadingSessionDetail.value = false;
  }

  async function stopSession(session: AdminSession) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSessions.value) return;
    actingSessionId.value = session.session_id;
    try {
      await adminSessionApi.stopSession(session.session_id);
      await loadSessions();
    } catch (err) {
      console.error("停止会话失败:", err);
      toast.error("停止会话失败");
    } finally {
      actingSessionId.value = null;
    }
  }

  async function deleteSession(session: AdminSession) {
    if (!permission.isLoaded.value) {
      await permission.fetchPermissions();
    }
    if (!canManageSessions.value) return;
    actingSessionId.value = session.session_id;
    try {
      await adminSessionApi.deleteSession(session.session_id);
      await loadSessions();
    } catch (err) {
      console.error("删除会话失败:", err);
      toast.error("删除会话失败");
    } finally {
      actingSessionId.value = null;
    }
  }

  return {
    loading,
    savingGrant,
    savingQuota,
    savingSecret,
    savingArtifactAcl,
    actingSessionId,
    deletingGrantKey,
    deletingQuotaKey,
    deletingSecretName,
    loadingGrantDetail,
    loadingGrantCatalog,
    selectedGrantRouteKey,
    grantDetailError,
    grantCatalogError,
    loadingSecretDetail,
    selectedSecretName,
    secretDetailError,
    loadingArtifactAcl,
    selectedArtifactAclKey,
    artifactAclError,
    loadingSessionDetail,
    data,
    showGrantDialog,
    editingGrant,
    grantForm,
    grantScopeMode,
    selectedGrantNodes,
    grantCatalogDatabases,
    grantCatalogTree,
    grantSelectedScopePreview,
    showQuotaDialog,
    editingQuota,
    quotaForm,
    showSecretDialog,
    editingSecret,
    secretForm,
    showArtifactAclDialog,
    editingArtifact,
    editingArtifactAclTarget,
    artifactAclForm,
    showSessionDetailDialog,
    selectedSessionDetailId,
    selectedSessionDetail,
    sessionDetailError,
    defaultDatasourceName,
    runningSessionCount,
    grantCount,
    quotaCount,
    secretCount,
    grantPagination,
    quotaPagination,
    sessionPagination,
    secretPagination,
    artifactPagination,
    grantPageActions,
    quotaPageActions,
    sessionPageActions,
    secretPageActions,
    artifactPageActions,
    loadOverview,
    loadDatasourceGrants,
    loadQuotasAndUsage,
    loadSessions,
    loadSecrets,
    loadArtifacts,
    applyGrantListFilters,
    applyQuotaListFilters,
    applySessionListFilters,
    applySecretListFilters,
    applyArtifactListFilters,
    loadGrantCatalog,
    openCreateGrantDialog,
    openEditGrantDialog,
    openGrantDetail,
    closeGrantDialog,
    setGrantSubjectType,
    setGrantDatasource,
    setGrantScopeMode,
    toggleGrantNode,
    saveGrant,
    deleteGrant,
    openCreateQuotaDialog,
    openEditQuotaDialog,
    setQuotaSubjectType,
    setQuotaSubjectId,
    setQuotaResource,
    setQuotaEnabled,
    saveQuota,
    deleteQuota,
    openCreateSecretDialog,
    openEditSecretDialog,
    openSecretDetail,
    closeSecretDialog,
    saveSecret,
    deleteSecret,
    openArtifactAclDialog,
    openArtifactAclDetail,
    closeArtifactAclDialog,
    toggleArtifactAclRole,
    toggleArtifactAclUser,
    saveArtifactAcl,
    openSessionDetail,
    closeSessionDetail,
    stopSession,
    deleteSession,
    artifactKey,
    artifactAclTargetKey,
  };
}
