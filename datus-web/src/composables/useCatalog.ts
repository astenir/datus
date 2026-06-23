import { ref, computed, readonly, shallowRef } from "vue";
import { catalogApi } from "@/lib/api";
import { databaseNameFromCatalog, schemaOptionsForDatabase, uniqueOptions } from "@/lib/chat";
import { handleError } from "@/lib/utils";
import { useConnection } from "./useConnection";
import type { CatalogRecord, SelectOption } from "@/types";

const { effectiveBase } = useConnection();

const catalogEntries = ref<CatalogRecord[]>([]);
const databaseOptions = ref<SelectOption[]>([]);
const database = shallowRef("");
const schema = shallowRef("");
const isLoadingCatalog = shallowRef(false);

async function loadCatalog(databaseName?: string) {
  const base = effectiveBase();
  isLoadingCatalog.value = true;
  try {
    const result = await catalogApi.list(base, databaseName ? { database_name: databaseName } : undefined);
    if (result) {
      catalogEntries.value = result.databases ?? [];
      if (!databaseName) {
        databaseOptions.value = uniqueOptions(
          catalogEntries.value.map((entry) => {
            const name = databaseNameFromCatalog(entry);
            return { value: name, label: name };
          }).filter((o) => o.value)
        );
      }
    }
  } catch (error) {
    handleError("加载数据源目录失败", error);
  } finally {
    isLoadingCatalog.value = false;
  }
}

const schemaOptions = computed(() => schemaOptionsForDatabase(catalogEntries.value, database.value));

function setDatabase(value: string) {
  database.value = value;
}

function setSchema(value: string) {
  schema.value = value;
}

export function useCatalog() {
  return {
    catalogEntries: readonly(catalogEntries),
    databaseOptions: readonly(databaseOptions),
    database: readonly(database),
    schema: readonly(schema),
    schemaOptions,
    isLoadingCatalog: readonly(isLoadingCatalog),
    loadCatalog,
    setDatabase,
    setSchema,
  };
}
