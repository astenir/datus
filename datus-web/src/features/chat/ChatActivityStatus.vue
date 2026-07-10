<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from "vue"
import { AlertTriangleIcon, LoaderCircleIcon, SquareIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { chatActivityPresentation } from "@/lib/chat-activity"
import type { ChatStreamActivity } from "@/types"

const props = defineProps<{
  activity: ChatStreamActivity
}>()

const emit = defineEmits<{
  stop: []
}>()

const now = shallowRef(Date.now())
const presentation = computed(() => chatActivityPresentation(props.activity, now.value))
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1_000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div
    v-if="presentation.visible"
    class="mx-auto flex w-full max-w-3xl items-center gap-2 text-xs text-muted-foreground"
  >
    <span
      role="status"
      aria-live="polite"
      class="sr-only"
    >
      {{ presentation.label }}
    </span>
    <AlertTriangleIcon
      v-if="presentation.tone === 'warning'"
      class="size-4 shrink-0 text-amber-600"
    />
    <LoaderCircleIcon
      v-else
      class="size-4 shrink-0 animate-spin"
    />
    <span class="min-w-0 truncate">{{ presentation.label }}</span>
    <span
      v-if="presentation.detail"
      class="shrink-0"
    >
      · {{ presentation.detail }}
    </span>
    <Button
      v-if="presentation.tone === 'warning'"
      type="button"
      variant="ghost"
      size="sm"
      class="ml-auto h-7 shrink-0 px-2 text-xs"
      @click="emit('stop')"
    >
      <SquareIcon />
      停止
    </Button>
  </div>
</template>
