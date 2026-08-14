<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import {
  FileTree,
  FileTreeFile,
  FileTreeFolder,
} from "@/components/ai-elements/file-tree"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
import TreeLoadingIndicator from "@/features/workspace/TreeLoadingIndicator.vue"
import { buildCatalogTree } from "@/lib/catalog-tree"
import type { CatalogRecord } from "@/types"

const props = withDefaults(defineProps<{
  entries: readonly CatalogRecord[]
  selectedTable?: string | null
  loading?: boolean
  embedded?: boolean
  title?: string
  description?: string
}>(), {
  selectedTable: null,
  loading: false,
  embedded: false,
  title: "目录树",
  description: "按数据库、模式和表组织。",
})

const emit = defineEmits<{
  refresh: []
  selectTable: [table: string]
  loadSchema: [database: string, schema: string]
}>()

const expandedPaths = shallowRef<Set<string>>(new Set())
const databaseKey = shallowRef("")

const treeData = computed(() => buildCatalogTree(props.entries))
const hasCatalogData = computed(() => treeData.value.databases.length > 0)
const selectedPath = computed(() => props.selectedTable?.trim() || undefined)

// Reset expansion only when the database set changes (datasource switch or a
// fresh load); keep the user's manual schema expansion when table lists update.
watch(
  () => treeData.value.databases.map((database) => database.path).join("|"),
  (key) => {
    if (key !== databaseKey.value) {
      databaseKey.value = key
      expandedPaths.value = new Set(treeData.value.expandedPaths)
    }
  },
  { immediate: true },
)

function handleSelectedPath(path: string) {
  if (!path || path.startsWith("database:") || path.includes(":schema:")) return
  emit("selectTable", path)
}

function handleExpandedChange(paths: Set<string>) {
  expandedPaths.value = new Set(paths)
  for (const database of treeData.value.databases) {
    for (const schema of database.schemas) {
      if (schema.tables.length === 0 && paths.has(schema.path)) {
        emit("loadSchema", schema.database, schema.schema)
      }
    }
  }
}
</script>

<template>
  <component
    :is="embedded ? 'div' : Card"
    :class="embedded ? 'flex min-h-0 min-w-0 flex-1 flex-col' : 'min-h-0 min-w-0 gap-4'"
  >
    <PanelCardHeader
      v-if="!embedded"
      :title="title"
      :description="description"
    >
      <template #action>
        <Button
          variant="outline"
          size="sm"
          :disabled="loading"
          @click="emit('refresh')"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </template>
    </PanelCardHeader>
    <CardContent :class="embedded ? 'flex min-h-0 flex-1 flex-col p-0' : 'flex min-h-0 flex-1 flex-col'">
      <ScrollArea
        type="auto"
        class="min-h-0 flex-1 overflow-hidden pr-3"
      >
        <FileTree
          :expanded="expandedPaths"
          :selected-path="selectedPath"
          :aria-busy="loading"
          class="border-0 bg-transparent p-0 font-sans"
          @expanded-change="handleExpandedChange"
          @update:selected-path="handleSelectedPath"
        >
          <TreeLoadingIndicator
            v-if="loading && !hasCatalogData"
            label="正在加载目录..."
          />
          <TreeLoadingIndicator
            v-if="loading && hasCatalogData"
            compact
            label="正在刷新目录..."
          />
          <template v-if="hasCatalogData">
            <FileTreeFolder
              v-for="database in treeData.databases"
              :key="database.key"
              :path="database.path"
              :name="database.name"
            >
              <FileTreeFolder
                v-for="schema in database.schemas"
                :key="schema.key"
                :path="schema.path"
                :name="schema.name"
              >
                <FileTreeFile
                  v-for="table in schema.tables"
                  :key="table.key"
                  :path="table.fullName"
                  :name="table.table"
                  :aria-label="`加载 ${table.fullName}`"
                  class="min-w-0 [&>span:first-child]:shrink-0 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1"
                />
              </FileTreeFolder>
            </FileTreeFolder>
          </template>
          <div
            v-else-if="!loading"
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            暂无可浏览表，刷新目录或切换数据范围后重试。
          </div>
        </FileTree>
      </ScrollArea>
    </CardContent>
  </component>
</template>
