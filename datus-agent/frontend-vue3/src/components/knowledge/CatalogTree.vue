<script setup lang="ts">
import { computed } from "vue";
import { Database, Table2, ChevronRight, ChevronDown, Layers } from "@lucide/vue";
import { ref } from "vue";
import type { DatabaseInfo } from "@/types";

const props = defineProps<{
  entries: DatabaseInfo[];
  selectedTable: string;
}>();

const emit = defineEmits<{
  select: [tableName: string];
}>();

// ─── Build tree structure from flat DatabaseInfo[] ────────────────────────────

interface SchemaNode {
  name: string;
  tables: string[];
}

interface DatabaseNode {
  name: string;
  schemas: SchemaNode[];
}

const treeData = computed<DatabaseNode[]>(() => {
  const dbMap = new Map<string, Map<string, string[]>>();

  for (const entry of props.entries) {
    const dbName = entry.name;
    const schemaName = entry.schema_name || "default";
    const tables = entry.tables ?? [];

    if (!dbMap.has(dbName)) dbMap.set(dbName, new Map());
    const schemaMap = dbMap.get(dbName)!;
    if (!schemaMap.has(schemaName)) schemaMap.set(schemaName, []);
    schemaMap.get(schemaName)!.push(...tables);
  }

  return Array.from(dbMap.entries()).map(([dbName, schemaMap]) => ({
    name: dbName,
    schemas: Array.from(schemaMap.entries()).map(([schemaName, tables]) => ({
      name: schemaName,
      tables: [...new Set(tables)].sort(),
    })),
  }));
});

// ─── Expand state ────────────────────────────────────────────────────────────

const expandedDbs = ref<Set<string>>(new Set());
const expandedSchemas = ref<Set<string>>(new Set());

function toggleDb(db: string) {
  if (expandedDbs.value.has(db)) {
    expandedDbs.value.delete(db);
  } else {
    expandedDbs.value.add(db);
  }
}

function toggleSchema(key: string) {
  if (expandedSchemas.value.has(key)) {
    expandedSchemas.value.delete(key);
  } else {
    expandedSchemas.value.add(key);
  }
}

function selectTable(db: string, schema: string, table: string) {
  const fullName = schema === "default" ? `${db}.${table}` : `${db}.${schema}.${table}`;
  emit("select", fullName);
}

function isSelected(db: string, schema: string, table: string): boolean {
  const fullName = schema === "default" ? `${db}.${table}` : `${db}.${schema}.${table}`;
  return props.selectedTable === fullName;
}
</script>

<template>
  <div class="catalogTree">
    <div v-if="entries.length === 0" class="catalogTreeEmpty">
      <Database :size="24" />
      <p>暂无 Catalog 数据</p>
    </div>
    <template v-else>
      <div v-for="db in treeData" :key="db.name" class="treeNodeGroup">
        <!-- Database node -->
        <div class="treeNode" style="padding-left: 4px" @click="toggleDb(db.name)">
          <button type="button" class="treeToggle" @click.stop="toggleDb(db.name)">
            <ChevronDown v-if="expandedDbs.has(db.name)" :size="12" />
            <ChevronRight v-else :size="12" />
          </button>
          <Database :size="14" />
          <span class="treeNodeName">{{ db.name }}</span>
        </div>

        <!-- Schema nodes -->
        <template v-if="expandedDbs.has(db.name)">
          <div v-for="schema in db.schemas" :key="`${db.name}.${schema.name}`" class="treeNodeGroup">
            <div
              class="treeNode"
              :style="{ paddingLeft: '20px' }"
              @click="toggleSchema(`${db.name}.${schema.name}`)"
            >
              <button
                type="button"
                class="treeToggle"
                @click.stop="toggleSchema(`${db.name}.${schema.name}`)"
              >
                <ChevronDown v-if="expandedSchemas.has(`${db.name}.${schema.name}`)" :size="12" />
                <ChevronRight v-else :size="12" />
              </button>
              <Layers :size="14" />
              <span class="treeNodeName">{{ schema.name }}</span>
            </div>

            <!-- Table nodes -->
            <template v-if="expandedSchemas.has(`${db.name}.${schema.name}`)">
              <div
                v-for="table in schema.tables"
                :key="`${db.name}.${schema.name}.${table}`"
                :class="['treeNode', { selected: isSelected(db.name, schema.name, table) }]"
                :style="{ paddingLeft: '36px' }"
                @click="selectTable(db.name, schema.name, table)"
              >
                <span class="treeTogglePlaceholder" />
                <Table2 :size="14" />
                <span class="treeNodeName">{{ table }}</span>
              </div>
            </template>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.catalogTreeEmpty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 30px 0;
  color: var(--text-muted);
}

.treeNodeGroup {
  display: contents;
}

.treeNode {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  min-height: 28px;
  user-select: none;
}

.treeNode:hover {
  background: var(--accent);
}

.treeNode.selected {
  background: var(--accent);
  font-weight: 500;
}

.treeToggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--muted-foreground);
  padding: 0;
}

.treeToggle:hover {
  color: var(--foreground);
}

.treeTogglePlaceholder {
  width: 16px;
  flex-shrink: 0;
}

.treeNodeName {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
