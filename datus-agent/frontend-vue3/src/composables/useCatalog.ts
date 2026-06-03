import { ref, watch } from "vue";
import { catalogApi } from "@/lib/api";
import { databaseNameFromCatalog, schemaOptionsForDatabase, uniqueOptions } from "@/lib/chat";
import { useConnection } from "./useConnection";
import type { CatalogRecord, SelectOption } from "@/types";

const catalogEntries = ref<CatalogRecord[]>([]);
const databaseOptions = ref<SelectOption[]>([]);
const database = ref("");
const schema = ref("");

async function loadCatalog(databaseName?: string) {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
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
  } catch {
    // silently fail
  }
}

const schemaOptions = ref<SelectOption[]>([]);
watch([database, catalogEntries], ([db]) => {
  schemaOptions.value = schemaOptionsForDatabase(catalogEntries.value, db);
});

function resetCatalog() {
  database.value = "";
  schema.value = "";
}

export function useCatalog() {
  return {
    catalogEntries,
    databaseOptions,
    database,
    schema,
    schemaOptions,
    loadCatalog,
  };
}
