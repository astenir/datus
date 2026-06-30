import { ref, computed, readonly, shallowRef } from "vue";
import { catalogApi } from "@/lib/api";
import { databaseNameFromCatalog, schemaOptionsForDatabase, uniqueOptions } from "@/lib/chat";
import { handleError } from "@/lib/utils";
import { useConnection } from "./useConnection";
import type { CatalogRecord, DatasourceStatusItem, SelectOption } from "@/types";

const { effectiveBase } = useConnection();

type CatalogSnapshot = {
  entries: CatalogRecord[];
  databaseOptions: SelectOption[];
  database: string;
  schema: string;
};

const catalogEntries = ref<CatalogRecord[]>([]);
const databaseOptions = ref<SelectOption[]>([]);
const database = shallowRef("");
const schema = shallowRef("");
const isLoadingCatalog = shallowRef(false);
const activeDatasource = shallowRef("");
const catalogSnapshots = shallowRef<Record<string, CatalogSnapshot>>({});
const datasourceStatuses = ref<Record<string, DatasourceStatusItem>>({});
const prewarmingDatasources = shallowRef<Set<string>>(new Set());

function datasourceKey(datasourceId?: string) {
  return datasourceId?.trim() ?? "";
}

function snapshotKey(datasourceId?: string) {
  return datasourceKey(datasourceId) || "__default__";
}

function databaseOptionsFromEntries(entries: readonly CatalogRecord[]) {
  return uniqueOptions(
    entries.map((entry) => {
      const name = databaseNameFromCatalog(entry);
      return { value: name, label: name };
    }).filter((option) => option.value)
  );
}

function saveActiveSnapshot() {
  const key = snapshotKey(activeDatasource.value);
  catalogSnapshots.value = {
    ...catalogSnapshots.value,
    [key]: {
      entries: [...catalogEntries.value],
      databaseOptions: [...databaseOptions.value],
      database: database.value,
      schema: schema.value,
    },
  };
}

function restoreSnapshot(datasourceId?: string) {
  const snapshot = catalogSnapshots.value[snapshotKey(datasourceId)];
  if (!snapshot) return;
  catalogEntries.value = [...snapshot.entries];
  databaseOptions.value = [...snapshot.databaseOptions];
  database.value = snapshot.database;
  schema.value = snapshot.schema;
}

function selectCatalogDatasource(datasourceId?: string) {
  const datasource = datasourceKey(datasourceId);
  if (activeDatasource.value === datasource) return;
  saveActiveSnapshot();
  activeDatasource.value = datasource;
  restoreSnapshot(datasource);
}

function hasCatalogSnapshot(datasourceId?: string) {
  const snapshot = catalogSnapshots.value[snapshotKey(datasourceId)];
  return Boolean(snapshot && snapshot.entries.length > 0);
}

async function loadCatalog(databaseName?: string, datasourceId?: string): Promise<boolean> {
  const datasource = datasourceKey(datasourceId) || activeDatasource.value;
  if (datasource !== activeDatasource.value) {
    selectCatalogDatasource(datasource);
  }

  const base = effectiveBase();
  isLoadingCatalog.value = true;
  try {
    const result = await catalogApi.list(base, {
      ...(datasource ? { datasource_id: datasource } : {}),
      ...(databaseName ? { database_name: databaseName } : {}),
    });
    if (result) {
      catalogEntries.value = result.databases ?? [];
      if (!databaseName) {
        databaseOptions.value = databaseOptionsFromEntries(catalogEntries.value);
        if (database.value && !databaseOptions.value.some((option) => option.value === database.value)) {
          database.value = "";
          schema.value = "";
        }
      }
      saveActiveSnapshot();
    }
    return true;
  } catch (error) {
    handleError("加载数据源目录失败", error);
    return false;
  } finally {
    isLoadingCatalog.value = false;
  }
}

async function loadDatasourceStatuses(datasourceId?: string): Promise<boolean> {
  try {
    const result = await catalogApi.status(effectiveBase(), datasourceId);
    const next = { ...datasourceStatuses.value };
    for (const status of result?.statuses ?? []) {
      next[status.datasource_id] = status;
    }
    datasourceStatuses.value = next;
    return true;
  } catch (error) {
    handleError("加载数据源状态失败", error);
    return false;
  }
}

async function prewarmDatasource(datasourceId?: string): Promise<boolean> {
  const datasource = datasourceKey(datasourceId);
  if (!datasource) return false;

  const running = new Set(prewarmingDatasources.value);
  running.add(datasource);
  prewarmingDatasources.value = running;

  try {
    const result = await catalogApi.prewarm(effectiveBase(), datasource);
    if (result?.datasource_id) {
      datasourceStatuses.value = {
        ...datasourceStatuses.value,
        [result.datasource_id]: {
          datasource_id: result.datasource_id,
          status: "connecting",
          cached: false,
        },
      };
    }
    return Boolean(result);
  } catch (error) {
    handleError("启动数据源预热失败", error);
    return false;
  } finally {
    const next = new Set(prewarmingDatasources.value);
    next.delete(datasource);
    prewarmingDatasources.value = next;
  }
}

const schemaOptions = computed(() => schemaOptionsForDatabase(catalogEntries.value, database.value));

function setDatabase(value: string) {
  if (database.value !== value) {
    schema.value = "";
  }
  database.value = value;
  saveActiveSnapshot();
}

function setSchema(value: string) {
  schema.value = value;
  saveActiveSnapshot();
}

export function useCatalog() {
  return {
    catalogEntries: readonly(catalogEntries),
    databaseOptions: readonly(databaseOptions),
    database: readonly(database),
    schema: readonly(schema),
    schemaOptions,
    isLoadingCatalog: readonly(isLoadingCatalog),
    datasourceStatuses: readonly(datasourceStatuses),
    prewarmingDatasources: readonly(prewarmingDatasources),
    selectCatalogDatasource,
    hasCatalogSnapshot,
    loadCatalog,
    loadDatasourceStatuses,
    prewarmDatasource,
    setDatabase,
    setSchema,
  };
}
