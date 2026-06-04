<script setup lang="ts">
import { CollapsibleRoot } from "reka-ui";
import { computed, ref } from "vue";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = withDefaults(defineProps<{
  defaultOpen?: boolean;
  open?: boolean;
  class?: HTMLAttributes["class"];
}>(), {
  defaultOpen: false
});

const emit = defineEmits<{
  "update:open": [value: boolean];
}>();

const isOpen = ref(props.open ?? props.defaultOpen);

const dataState = computed(() => isOpen.value ? "open" : "closed");

const handleUpdate = (value: boolean) => {
  isOpen.value = value;
  emit("update:open", value);
};
</script>

<template>
  <CollapsibleRoot
    :open="props.open ?? isOpen"
    :default-open="props.defaultOpen"
    :data-state="dataState"
    :class="cn(props.class)"
    @update:open="handleUpdate"
  >
    <slot />
  </CollapsibleRoot>
</template>
