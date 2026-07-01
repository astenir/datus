<script setup lang="ts">
import { computed, shallowRef, useTemplateRef, watchEffect } from "vue"
import { ChevronDownIcon, ChevronRightIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import type { RoleDatasourceTreeNode } from "@/lib/role-permissions"

const props = withDefaults(defineProps<{
  node: RoleDatasourceTreeNode
  selectedNodeIds: readonly string[]
  level?: number
  disabled?: boolean
  inheritedSelected?: boolean
}>(), {
  level: 0,
  disabled: false,
  inheritedSelected: false,
})

const emit = defineEmits<{
  toggleNode: [nodeId: string]
}>()

const expanded = shallowRef(false)
const checkboxRef = useTemplateRef<HTMLInputElement>("checkbox")
const explicitlyChecked = computed(() => props.selectedNodeIds.includes(props.node.id))
const selectedDescendantCount = computed(() => countSelectedDescendants(props.node, props.selectedNodeIds))
const checked = computed(() => explicitlyChecked.value || props.inheritedSelected)
const indeterminate = computed(() => !checked.value && selectedDescendantCount.value > 0)
const checkboxId = computed(() => `grant-scope-${props.node.id.replace(/[^a-zA-Z0-9_-]/g, "-")}`)
const childLevel = computed(() => props.level + 1)
const hasChildren = computed(() => (props.node.children?.length ?? 0) > 0)

watchEffect(() => {
  if (checkboxRef.value) {
    checkboxRef.value.indeterminate = indeterminate.value
  }
})

function countSelectedDescendants(node: RoleDatasourceTreeNode, selectedNodeIds: readonly string[]): number {
  return (node.children ?? []).reduce((count, child) => {
    const selfCount = selectedNodeIds.includes(child.id) ? 1 : 0
    return count + selfCount + countSelectedDescendants(child, selectedNodeIds)
  }, 0)
}
</script>

<template>
  <li class="flex flex-col gap-1">
    <div class="flex min-h-8 items-start gap-2 rounded-md px-2 py-1.5 hover:bg-muted/60">
      <Button
        v-if="hasChildren"
        type="button"
        variant="ghost"
        size="icon-xs"
        :aria-label="expanded ? `折叠 ${node.label}` : `展开 ${node.label}`"
        @click="expanded = !expanded"
      >
        <ChevronDownIcon
          v-if="expanded"
          data-icon="icon"
        />
        <ChevronRightIcon
          v-else
          data-icon="icon"
        />
      </Button>
      <span
        v-else
        class="size-6 shrink-0"
      />
      <input
        :id="checkboxId"
        ref="checkbox"
        type="checkbox"
        class="mt-0.5 size-4 shrink-0 rounded border border-input accent-primary"
        :checked="checked"
        :disabled="disabled"
        :aria-checked="indeterminate ? 'mixed' : checked ? 'true' : 'false'"
        :aria-label="`切换 ${node.label}`"
        @change="emit('toggleNode', node.id)"
      >
      <label
        :for="checkboxId"
        class="min-w-0 flex-1 cursor-pointer text-sm"
      >
        <span class="block truncate font-medium">{{ node.label }}</span>
        <span
          v-if="hasChildren"
          class="block text-xs text-muted-foreground"
        >
          {{ node.children?.length }} 个下级对象<span v-if="selectedDescendantCount">，已选 {{ selectedDescendantCount }} 个下级</span>
          <span v-else-if="checked && hasChildren">，已覆盖全部下级</span>
        </span>
      </label>
    </div>
    <ul
      v-if="hasChildren && expanded"
      class="ml-4 flex flex-col gap-1 border-l pl-3"
    >
      <DatasourceGrantScopeTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-node-ids="selectedNodeIds"
        :level="childLevel"
        :disabled="disabled"
        :inherited-selected="checked"
        @toggle-node="emit('toggleNode', $event)"
      />
    </ul>
  </li>
</template>
