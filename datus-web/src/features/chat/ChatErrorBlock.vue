<script setup lang="ts">
import { computed } from "vue"
import { InfoIcon, ShieldAlertIcon, TriangleAlertIcon, XIcon } from "@lucide/vue"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import type { ChatErrorBlock } from "@/types"

const props = defineProps<{
  block: ChatErrorBlock
  dismissible?: boolean
}>()

const emit = defineEmits<{
  dismiss: []
}>()

const icon = computed(() => {
  if (props.block.tone === "info") return InfoIcon
  if (props.block.tone === "warning") return ShieldAlertIcon
  return TriangleAlertIcon
})
</script>

<template>
  <Alert
    :variant="block.tone === 'error' || !block.tone ? 'destructive' : 'default'"
    class="rounded-lg"
  >
    <component :is="icon" />
    <AlertTitle>{{ block.title }}</AlertTitle>
    <AlertDescription class="flex flex-col gap-2 text-sm leading-6">
      <span>{{ block.message }}</span>
      <span
        v-if="block.code"
        class="font-mono text-xs"
      >
        错误码：{{ block.code }}
      </span>
    </AlertDescription>
    <AlertAction v-if="dismissible">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="关闭错误提示"
        @click="emit('dismiss')"
      >
        <XIcon />
      </Button>
    </AlertAction>
  </Alert>
</template>
