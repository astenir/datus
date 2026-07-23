<script setup lang="ts">
import { computed, h } from "vue"
import {
  BracesIcon,
  ChartNoAxesCombinedIcon,
  SquareTerminalIcon,
} from "@lucide/vue"
import {
  FileTreeFile,
  FileTreeFolder,
} from "@/components/ai-elements/file-tree"
import type { SubjectTreeNode } from "@/lib/subject-tree"

const props = defineProps<{
  node: SubjectTreeNode
}>()

const nodeIcon = computed(() => {
  const nodeType = String(props.node.type)

  if (nodeType === "metric") {
    return h(ChartNoAxesCombinedIcon, { class: "size-4 text-emerald-500" })
  }
  if (nodeType === "reference_sql") {
    return h(SquareTerminalIcon, { class: "size-4 text-sky-500" })
  }
  if (nodeType === "reference_template") {
    return h(BracesIcon, { class: "size-4 text-amber-500" })
  }

  return undefined
})
</script>

<template>
  <FileTreeFolder
    v-if="node.type === 'directory'"
    :path="node.path"
    :name="node.name"
  >
    <SubjectTreeNodeItem
      v-for="child in node.children"
      :key="child.key"
      :node="child"
    />
  </FileTreeFolder>
  <FileTreeFile
    v-else
    :path="node.path"
    :name="node.name"
    :icon="nodeIcon"
    :aria-label="`加载 ${node.subjectPath.join('/')}`"
    class="min-w-0 [&>span:first-child]:shrink-0 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1"
  />
</template>
