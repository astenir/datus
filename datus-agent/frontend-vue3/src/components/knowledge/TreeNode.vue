<script setup lang="ts">
import { Folder, FolderOpen, BookOpen, BarChart3, Code, ChevronRight, ChevronDown, FolderPlus, Trash2 } from "@lucide/vue";
import type { SubjectNode, SubjectNodeType } from "@/types";

defineProps<{
  node: SubjectNode;
  selectedPath: string;
  depth: number;
}>();

const emit = defineEmits<{
  select: [node: SubjectNode];
  create: [parentPath: string[], type: SubjectNodeType];
  delete: [node: SubjectNode];
}>();

const expanded = defineModel<boolean>("expanded", { default: true });

const typeIconMap: Record<string, typeof Folder> = {
  directory: Folder,
  metric: BarChart3,
  reference_sql: Code,
  knowledge: BookOpen,
};
</script>

<template>
  <div class="treeNodeGroup">
    <div
      :class="`treeNode ${selectedPath === node.subject_path.join('/') ? 'selected' : ''}`"
      :style="{ paddingLeft: `${depth * 16 + 4}px` }"
      @click="emit('select', node)"
    >
      <!-- Expand toggle for directories with children -->
      <button
        v-if="node.type === 'directory' && node.children?.length"
        type="button"
        class="treeToggle"
        @click.stop="expanded = !expanded"
      >
        <ChevronDown v-if="expanded" :size="12" />
        <ChevronRight v-else :size="12" />
      </button>
      <span v-else class="treeTogglePlaceholder" />

      <component :is="typeIconMap[node.type || 'directory'] || Folder" :size="14" />
      <span class="treeNodeName">{{ node.name }}</span>

      <div class="treeNodeActions">
        <button v-if="node.type === 'directory'" type="button" title="新建" @click.stop="emit('create', node.subject_path, 'metric')">
          <FolderPlus :size="12" />
        </button>
        <button type="button" title="删除" @click.stop="emit('delete', node)">
          <Trash2 :size="12" />
        </button>
      </div>
    </div>

    <!-- Recursive children -->
    <div v-if="expanded && node.children?.length" class="treeChildren">
      <TreeNode
        v-for="child in node.children"
        :key="child.subject_path.join('/')"
        :node="child"
        :selected-path="selectedPath"
        :depth="depth + 1"
        @select="emit('select', $event)"
        @create="emit('create', ...($event as [string[], SubjectNodeType]))"
        @delete="emit('delete', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
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

.treeNodeActions {
  display: none;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}

.treeNode:hover .treeNodeActions {
  display: flex;
}

.treeNodeActions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--muted-foreground);
  border-radius: 3px;
  padding: 0;
}

.treeNodeActions button:hover {
  background: var(--accent);
  color: var(--foreground);
}

.treeChildren {
  display: flex;
  flex-direction: column;
}
</style>
