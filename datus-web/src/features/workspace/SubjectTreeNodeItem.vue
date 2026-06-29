<script setup lang="ts">
import {
  FileTreeFile,
  FileTreeFolder,
} from "@/components/ai-elements/file-tree"
import type { SubjectTreeNode } from "@/lib/subject-tree"

defineProps<{
  node: SubjectTreeNode
}>()
</script>

<template>
  <FileTreeFolder
    v-if="node.children.length > 0"
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
    :aria-label="`加载 ${node.subjectPath.join('/')}`"
  />
</template>
