<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import {
  FileTree,
  FileTreeFile,
  FileTreeFolder,
} from "@/components/ai-elements/file-tree"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
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
}>()

const expandedPaths = shallowRef<Set<string>>(new Set())

const treeData = computed(() => buildCatalogTree(props.entries))
const selectedPath = computed(() => props.selectedTable?.trim() || undefined)

watch(
  () => treeData.value.expandedPaths,
  (paths) => {
    expandedPaths.value = new Set(paths)
  },
  { immediate: true },
)

function handleSelectedPath(path: string) {
  if (!path || path.startsWith("database:") || path.includes(":schema:")) return
  emit("selectTable", path)
}

function handleExpandedChange(paths: Set<string>) {
  expandedPaths.value = new Set(paths)
}
</script>

<template>
  <component
    :is="embedded ? 'div' : Card"
    :class="embedded ? 'flex min-h-0 min-w-0 flex-1 flex-col' : 'min-h-0 min-w-0'"
  >
    <CardHeader
      v-if="!embedded"
      class="flex flex-row items-start justify-between gap-3"
    >
      <div class="min-w-0">
        <CardTitle class="text-lg">{{ title }}</CardTitle>
        <CardDescription class="text-sm">
          {{ description }}
        </CardDescription>
      </div>
      <Button
        variant="outline"
        size="sm"
        :disabled="loading"
        @click="emit('refresh')"
      >
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
    </CardHeader>
    <CardContent :class="embedded ? 'flex min-h-0 flex-1 flex-col p-0' : 'flex min-h-0 flex-1 flex-col'">
      <ScrollArea
        type="auto"
        class="min-h-0 flex-1 overflow-hidden pr-3"
      >
        <FileTree
          :expanded="expandedPaths"
          :selected-path="selectedPath"
          class="border-0 bg-transparent p-0 font-sans"
          @expanded-change="handleExpandedChange"
          @update:selected-path="handleSelectedPath"
        >
          <template v-if="treeData.databases.length > 0">
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
                />
              </FileTreeFolder>
            </FileTreeFolder>
          </template>
          <div
            v-else
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            暂无可浏览表，刷新目录或切换数据范围后重试。
          </div>
        </FileTree>
      </ScrollArea>
    </CardContent>
  </component>
</template>
