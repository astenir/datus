<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { CheckIcon, CopyIcon } from "@lucide/vue";
import { computed, onBeforeUnmount, shallowRef } from "vue";
import { toast } from "vue-sonner";
import { Button } from "@/components/ui/button";
import { copyTextToClipboard } from "@/lib/clipboard";
import { cn } from "@/lib/utils";

const props = withDefaults(defineProps<{
  code: string
  timeout?: number
  class?: HTMLAttributes["class"]
}>(), {
  timeout: 2000,
});

const isCopied = shallowRef(false);
let resetTimer: ReturnType<typeof setTimeout> | undefined;

const icon = computed(() => (isCopied.value ? CheckIcon : CopyIcon));

async function copyCode() {
  try {
    await copyTextToClipboard(props.code);
    isCopied.value = true;

    if (resetTimer) {
      clearTimeout(resetTimer);
    }

    resetTimer = setTimeout(() => {
      isCopied.value = false;
    }, props.timeout);
  } catch (error) {
    console.error("Copy code block failed", error);
    toast.error("复制失败：当前浏览器不支持自动复制");
  }
}

onBeforeUnmount(() => {
  if (resetTimer) {
    clearTimeout(resetTimer);
  }
});
</script>

<template>
  <Button
    type="button"
    :class="cn('shrink-0', props.class)"
    size="icon"
    variant="ghost"
    aria-label="复制代码"
    title="复制代码"
    @click="copyCode"
  >
    <component
      :is="icon"
      :size="14"
    />
  </Button>
</template>
