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
    class="gap-x-2 rounded-lg px-3 py-2.5 text-sm"
    data-testid="chat-error"
  >
    <component
      :is="icon"
      class="size-4 translate-y-0!"
      :class="block.tone === 'info' ? 'text-muted-foreground' : ''"
      data-testid="chat-error-leading-icon"
      aria-hidden="true"
    />
    <AlertTitle
      class="text-sm leading-5"
      data-testid="chat-error-title"
    >
      {{ block.title }}
    </AlertTitle>
    <AlertDescription
      class="flex flex-col gap-2 text-xs leading-5"
      data-testid="chat-error-description"
    >
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
