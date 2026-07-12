<script setup lang="ts">
import { computed, onMounted, onUnmounted, useTemplateRef, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  handleArtifactPreviewMessage,
  type ArtifactPreviewQueryHandler,
} from "@/lib/artifact-preview-bridge"

const props = withDefaults(defineProps<{
  title: string
  url: string | null
  loading: boolean
  error: string | null
  showChrome?: boolean
  dashboardSlug?: string | null
  query?: ArtifactPreviewQueryHandler
}>(), {
  showChrome: true,
  dashboardSlug: null,
  query: undefined,
})

const emit = defineEmits<{
  reload: []
}>()

const frameTitle = computed(() => `${props.title}预览`)
const frameRef = useTemplateRef<HTMLIFrameElement>("previewFrame")
let previewController = new AbortController()

function handleWindowMessage(event: MessageEvent<unknown>) {
  const dashboardSlug = props.dashboardSlug?.trim()
  const query = props.query
  if (!dashboardSlug || !query) return

  void handleArtifactPreviewMessage(
    event,
    frameRef.value?.contentWindow ?? null,
    dashboardSlug,
    query,
    previewController.signal,
  )
}

watch(
  () => [props.url, props.dashboardSlug, props.query] as const,
  () => {
    previewController.abort()
    previewController = new AbortController()
  },
  { flush: "sync" },
)

onMounted(() => window.addEventListener("message", handleWindowMessage))
onUnmounted(() => {
  previewController.abort()
  window.removeEventListener("message", handleWindowMessage)
})
</script>

<template>
  <section class="flex min-h-[440px] min-w-0 flex-1 flex-col overflow-hidden rounded-md border bg-muted/20">
    <div
      v-if="props.showChrome"
      class="flex h-11 shrink-0 items-center justify-between gap-3 border-b bg-background px-3"
    >
      <div class="min-w-0 truncate text-sm font-medium">{{ frameTitle }}</div>
      <Button
        variant="ghost"
        size="icon-sm"
        :disabled="props.loading"
        :aria-label="`刷新${frameTitle}`"
        @click="emit('reload')"
      >
        <RefreshCwIcon data-icon="inline-start" />
      </Button>
    </div>

    <div
      v-if="props.loading"
      class="flex min-h-[440px] flex-1 flex-col gap-3 p-4"
    >
      <div class="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span>正在加载预览...</span>
      </div>
      <Skeleton class="h-10 w-full" />
      <Skeleton class="h-64 w-full" />
      <Skeleton class="h-20 w-2/3" />
    </div>

    <div
      v-else-if="props.error"
      class="flex min-h-[440px] flex-1 items-center justify-center p-4"
    >
      <Alert variant="destructive">
        <AlertTitle>预览不可用</AlertTitle>
        <AlertDescription>{{ props.error }}</AlertDescription>
      </Alert>
    </div>

    <div
      v-else-if="!props.url"
      class="flex min-h-[440px] flex-1 items-center justify-center p-6 text-center"
    >
      <div class="max-w-sm text-sm text-muted-foreground">
        正在等待产物 HTML。
      </div>
    </div>

    <iframe
      v-else
      ref="previewFrame"
      :src="props.url"
      :title="frameTitle"
      sandbox="allow-scripts allow-downloads"
      referrerpolicy="no-referrer"
      class="min-h-[440px] flex-1 bg-background"
    />
  </section>
</template>
