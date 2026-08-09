import { computed, onBeforeUnmount, shallowRef, type ComputedRef, type Ref } from "vue";

import type { UserPermissions } from "@/composables/usePermission";
import type { WorkspaceAccessFlags } from "@/features/workspace/access";
import type {
  CatalogRecord,
  DatasourceStatusItem,
  NormalizedProbeResult,
  SelectOption,
} from "@/types";
import {
  datasourceGrantAllowsCatalog,
  mergeSelectOptions,
  WILDCARD_DATASOURCE_GRANT,
} from "@/composables/workspace-datasource-policy";

const STATUS_REFRESH_DELAYS = [1500, 5000] as const;

type ReadonlyValue<T> = Readonly<Ref<T>>;

type WorkspaceConfigSource = {
  readonly current_datasource?: string;
};

interface WorkspaceDatasourceConnectionSource {
  config: ReadonlyValue<WorkspaceConfigSource | null>;
  datasourceOptions: ReadonlyValue<readonly SelectOption[]>;
  isTestingDatasource: ReadonlyValue<boolean>;
}

interface WorkspaceDatasourcePermissionSource {
  permissions?: ReadonlyValue<UserPermissions | null>;
  hasDatasourcePermission: (datasourceName: string) => boolean;
  hasFeaturePermission: (featureCode: string) => boolean;
  hasPermission: (permissionCode: string) => boolean;
}

interface WorkspaceDatasourceCatalogSource {
  catalogEntries: ReadonlyValue<readonly CatalogRecord[]>;
  databaseOptions: ReadonlyValue<readonly SelectOption[]>;
  database: ReadonlyValue<string>;
  schema: ReadonlyValue<string>;
  schemaOptions: ReadonlyValue<readonly SelectOption[]>;
  isLoadingCatalog: ReadonlyValue<boolean>;
  isLoadingDatabases: ReadonlyValue<boolean>;
  isLoadingSchemas: ReadonlyValue<boolean>;
  datasourceStatuses: ReadonlyValue<Record<string, DatasourceStatusItem>>;
  prewarmingDatasources: ReadonlyValue<ReadonlySet<string>>;
  selectCatalogDatasource: (datasourceId?: string) => void;
  hasCatalogSnapshot: (datasourceId?: string) => boolean;
  loadCatalog: (databaseName?: string, datasourceId?: string) => Promise<boolean>;
  loadDatasourceStatuses: (datasourceId?: string) => Promise<boolean>;
  prewarmDatasource: (datasourceId?: string) => Promise<boolean>;
  setDatabase: (value: string) => void;
  setSchema: (value: string) => void;
}

export interface UseWorkspaceDatasourceContextOptions {
  connection: WorkspaceDatasourceConnectionSource;
  permission: WorkspaceDatasourcePermissionSource;
  catalog: WorkspaceDatasourceCatalogSource;
  viewAccess: ComputedRef<WorkspaceAccessFlags>;
}

export function useWorkspaceDatasourceContext(options: UseWorkspaceDatasourceContextOptions) {
  const isTestingCatalogDatasource = shallowRef(false);
  const selectedDatasource = shallowRef("");
  const statusRefreshTimers = new Set<ReturnType<typeof setTimeout>>();

  const grantedDatasourceOptions = computed<SelectOption[]>(() =>
    (options.permission.permissions?.value?.datasources ?? [])
      .filter((name) => name !== WILDCARD_DATASOURCE_GRANT)
      .map((name) => ({ value: name, label: name }))
  );
  const statusDatasourceOptions = computed<SelectOption[]>(() =>
    Object.keys(options.catalog.datasourceStatuses.value).map((name) => ({ value: name, label: name }))
  );
  const availableDatasourceOptions = computed<SelectOption[]>(() =>
    options.connection.datasourceOptions.value.length > 0
      ? [...options.connection.datasourceOptions.value]
      : mergeSelectOptions(grantedDatasourceOptions.value, statusDatasourceOptions.value)
  );
  const visibleDatasourceOptions = computed<SelectOption[]>(() =>
    availableDatasourceOptions.value.filter((option) => options.permission.hasDatasourcePermission(option.value))
  );
  const defaultDatasource = computed(() => {
    const configuredDatasource = options.connection.config.value?.current_datasource?.trim() ?? "";
    if (visibleDatasourceOptions.value.some((option) => option.value === configuredDatasource)) {
      return configuredDatasource;
    }
    return visibleDatasourceOptions.value[0]?.value ?? "";
  });
  const currentDatasource = computed(() => {
    const selected = selectedDatasource.value.trim();
    if (visibleDatasourceOptions.value.some((option) => option.value === selected)) {
      return selected;
    }
    return defaultDatasource.value;
  });
  const catalogDatasourceOptions = computed(() =>
    visibleDatasourceOptions.value.filter((option) => canBrowseDatasourceCatalog(option.value))
  );
  const hasCatalogBrowseGrant = computed(() =>
    catalogDatasourceOptions.value.length > 0 || hasWildcardCatalogGrant()
  );
  const canUseDatasourceCatalogSupport = computed(() =>
    options.permission.hasPermission("module.datasource_catalog")
    || options.permission.hasFeaturePermission("datasource_catalog")
  );
  const canAccessDatasourceCatalog = computed(() =>
    options.viewAccess.value.canViewKnowledge
    || canUseDatasourceCatalogSupport.value
    || (options.viewAccess.value.canViewChat && hasCatalogBrowseGrant.value)
  );
  const canReadAgentConfig = computed(() =>
    options.viewAccess.value.canViewConfiguration
  );
  const canReadModelOptions = computed(() =>
    options.viewAccess.value.canViewChat || canReadAgentConfig.value
  );
  const isTestingDatasource = computed(() =>
    options.connection.isTestingDatasource.value || isTestingCatalogDatasource.value
  );
  const currentDatasourceStatus = computed(() => {
    const datasource = currentDatasource.value.trim();
    return datasource ? (options.catalog.datasourceStatuses.value[datasource] ?? null) : null;
  });
  const isPrewarmingCurrentDatasource = computed(() => {
    const datasource = currentDatasource.value.trim();
    return Boolean(datasource && options.catalog.prewarmingDatasources.value.has(datasource));
  });

  function clearStatusRefreshTimers() {
    for (const timer of statusRefreshTimers) {
      clearTimeout(timer);
    }
    statusRefreshTimers.clear();
  }

  function scheduleDatasourceStatusRefresh(datasource: string) {
    for (const delay of STATUS_REFRESH_DELAYS) {
      const timer = setTimeout(() => {
        statusRefreshTimers.delete(timer);
        void loadAuthorizedDatasourceStatuses(datasource);
      }, delay);
      statusRefreshTimers.add(timer);
    }
  }

  function canQueryDatasourceCatalog(datasource?: string) {
    if (!canAccessDatasourceCatalog.value) return false;
    const datasourceName = datasource?.trim();
    if (!datasourceName) {
      return hasCatalogBrowseGrant.value;
    }
    return canUseDatasource(datasourceName) && (
      canBrowseDatasourceCatalog(datasourceName)
      || hasWildcardCatalogGrant()
    );
  }

  function loadAuthorizedDatasourceStatuses(datasource?: string) {
    if (!canQueryDatasourceCatalog(datasource)) {
      return false;
    }
    void options.catalog.loadDatasourceStatuses(datasource);
    return true;
  }

  function warmDatasource(datasource: string) {
    const datasourceName = datasource.trim();
    if (!datasourceName || !canQueryDatasourceCatalog(datasourceName)) return;
    void options.catalog.loadDatasourceStatuses(datasourceName);
    void options.catalog.prewarmDatasource(datasourceName).then((started) => {
      if (started) {
        scheduleDatasourceStatusRefresh(datasourceName);
      }
    });
  }

  function handleDatasourceSwitched() {
    selectedDatasource.value = defaultDatasource.value;
    options.catalog.selectCatalogDatasource(currentDatasource.value);
    warmDatasource(currentDatasource.value);
  }

  function initializeDatasource() {
    selectedDatasource.value = defaultDatasource.value;
    options.catalog.selectCatalogDatasource(currentDatasource.value);
  }

  function warmCurrentDatasource() {
    loadAuthorizedDatasourceStatuses();
    warmDatasource(currentDatasource.value);
  }

  async function handleDatasourceTest(name?: string): Promise<NormalizedProbeResult> {
    const datasourceName = (name?.trim() || currentDatasource.value.trim());
    if (!datasourceName) {
      return { ok: false, message: "当前数据源未选择" };
    }
    if (!canAccessDatasourceCatalog.value) {
      return { ok: false, message: "当前用户无权访问数据源目录" };
    }
    if (!canUseDatasource(datasourceName)) {
      return { ok: false, message: "当前用户无权访问该数据源" };
    }

    isTestingCatalogDatasource.value = true;
    try {
      const ok = await options.catalog.loadCatalog(undefined, datasourceName);
      await options.catalog.loadDatasourceStatuses(datasourceName);
      if (ok) {
        return { ok: true, message: "连接正常" };
      }
      const status = options.catalog.datasourceStatuses.value[datasourceName];
      return {
        ok: false,
        message: status?.error_message || "连接失败，请确认权限或数据源配置",
      };
    } finally {
      isTestingCatalogDatasource.value = false;
    }
  }

  function refreshCatalog(databaseName?: string) {
    if (!canQueryDatasourceCatalog(currentDatasource.value)) {
      return Promise.resolve(false);
    }
    return options.catalog.loadCatalog(databaseName, currentDatasource.value);
  }

  function ensureCatalogLoaded() {
    if (options.catalog.isLoadingCatalog.value || options.catalog.hasCatalogSnapshot(currentDatasource.value)) {
      return Promise.resolve(true);
    }
    return refreshCatalog();
  }

  function canUseDatasource(name: string) {
    const datasourceName = name.trim();
    return visibleDatasourceOptions.value.some((option) => option.value === datasourceName);
  }

  function hasWildcardCatalogGrant() {
    const grants = options.permission.permissions?.value?.datasource_grants ?? {};
    return datasourceGrantAllowsCatalog(grants[WILDCARD_DATASOURCE_GRANT]);
  }

  function canBrowseDatasourceCatalog(name: string) {
    const datasourceName = name.trim();
    if (!datasourceName) return false;
    const grants = options.permission.permissions?.value?.datasource_grants ?? {};
    return datasourceGrantAllowsCatalog(grants[datasourceName]);
  }

  async function handleDatasourceSwitch(name: string): Promise<boolean> {
    const datasourceName = name.trim();
    if (!datasourceName || !canUseDatasource(datasourceName)) return false;
    if (datasourceName === currentDatasource.value) return true;

    selectedDatasource.value = datasourceName;
    options.catalog.selectCatalogDatasource(datasourceName);
    if (canQueryDatasourceCatalog(datasourceName)) {
      warmDatasource(datasourceName);
      void options.catalog.loadCatalog(undefined, datasourceName);
    }
    return true;
  }

  onBeforeUnmount(() => {
    clearStatusRefreshTimers();
  });

  return {
    visibleDatasourceOptions,
    currentDatasource,
    isTestingDatasource,
    databaseOptions: options.catalog.databaseOptions,
    catalogEntries: options.catalog.catalogEntries,
    schemaOptions: options.catalog.schemaOptions,
    isLoadingCatalog: options.catalog.isLoadingCatalog,
    isLoadingDatabases: options.catalog.isLoadingDatabases,
    isLoadingSchemas: options.catalog.isLoadingSchemas,
    datasourceStatuses: options.catalog.datasourceStatuses,
    currentDatasourceStatus,
    isPrewarmingCurrentDatasource,
    loadCatalog: refreshCatalog,
    ensureCatalogLoaded,
    loadDatasourceStatuses: options.catalog.loadDatasourceStatuses,
    prewarmDatasource: options.catalog.prewarmDatasource,
    database: options.catalog.database,
    schema: options.catalog.schema,
    setDatabase: options.catalog.setDatabase,
    setSchema: options.catalog.setSchema,
    handleDatasourceSwitched,
    initializeDatasource,
    warmCurrentDatasource,
    handleDatasourceTest,
    handleDatasourceSwitch,
    canUseDatasource,
    canReadAgentConfig,
    canReadModelOptions,
  };
}
