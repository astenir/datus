<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import {
  FileTree,
} from "@/components/ai-elements/file-tree"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import SubjectTreeNodeItem from "@/features/workspace/SubjectTreeNodeItem.vue"
import { buildSubjectTree, type SubjectTreeNode } from "@/lib/subject-tree"
import type { SubjectNode } from "@/types"

const props = withDefaults(defineProps<{
  subjects: readonly SubjectNode[]
  selectedPath?: string | null
  loading?: boolean
  embedded?: boolean
}>(), {
  selectedPath: null,
  loading: false,
  embedded: false,
})

const emit = defineEmits<{
  refresh: []
  selectSubject: [node: SubjectTreeNode]
}>()

const expandedPaths = shallowRef<Set<string>>(new Set())

const treeData = computed(() => buildSubjectTree(props.subjects))
const selectedTreePath = computed(() => props.selectedPath?.trim() || undefined)

watch(
  () => treeData.value.expandedPaths,
  (paths) => {
    expandedPaths.value = new Set(paths)
  },
  { immediate: true },
)

function handleSelectedPath(path: string) {
  const node = treeData.value.nodeByPath.get(path)
  if (node) {
    emit("selectSubject", node)
  }
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
        <CardTitle class="text-lg">Subject Tree</CardTitle>
        <CardDescription class="text-sm">
          点击主题、指标或参考 SQL 查看详情。
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
          :selected-path="selectedTreePath"
          class="border-0 bg-transparent p-0 font-sans"
          @expanded-change="handleExpandedChange"
          @update:selected-path="handleSelectedPath"
        >
          <template v-if="treeData.nodes.length > 0">
            <SubjectTreeNodeItem
              v-for="node in treeData.nodes"
              :key="node.key"
              :node="node"
            />
          </template>
          <div
            v-else
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            暂无 Subject 数据，刷新或先运行知识构建。
          </div>
        </FileTree>
      </ScrollArea>
    </CardContent>
  </component>
</template>
