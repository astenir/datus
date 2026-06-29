<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from "@/components/ui/dialog"
import { artifactPreviewKey, useArtifacts } from "@/composables/useArtifacts"
import ArtifactCollectionGrid from "@/features/artifacts/ArtifactCollectionGrid.vue"
import ArtifactDetailPanel from "@/features/artifacts/ArtifactDetailPanel.vue"
import type { ArtifactViewTab } from "@/features/workspace/types"

const props = withDefaults(defineProps<{
  tab?: ArtifactViewTab
  selectedSlug?: string | null
}>(), {
  tab: "dashboard",
  selectedSlug: null,
})
const emit = defineEmits<{
  "open-artifact": [tab: ArtifactViewTab, slug: string]
  "close-detail": []
}>()

const artifacts = useArtifacts()

const selectedDetailSlug = computed(() => props.selectedSlug?.trim() || null)
const detailDialogOpen = computed(() => Boolean(selectedDetailSlug.value))
const detailKindLabel = computed(() => props.tab === "report" ? "报表" : "仪表盘")
const selectedPreviewKey = computed(() => {
  const slug = selectedDetailSlug.value
  return slug ? artifactPreviewKey(props.tab, slug) : null
})

const selectedPreviewOpening = computed(() => {
  return Boolean(selectedPreviewKey.value && artifacts.previewLoadingKey.value === selectedPreviewKey.value)
})

const dashboardOpeningSlug = computed(() => loadingSlugFor("dashboard"))
const reportOpeningSlug = computed(() => loadingSlugFor("report"))

function loadingSlugFor(tab: ArtifactViewTab): string | null {
  const key = artifacts.previewLoadingKey.value
  const prefix = `${tab}:`
  return key?.startsWith(prefix) ? key.slice(prefix.length) : null
}

function openArtifact(tab: ArtifactViewTab, slug: string) {
  emit("open-artifact", tab, slug)
}

function runDashboardQuery(querySlug: string, params: Record<string, unknown>) {
  if (props.tab !== "dashboard" || !selectedDetailSlug.value) return
  void artifacts.runDashboardQuery(selectedDetailSlug.value, querySlug, params)
}

function openPreview(tab: ArtifactViewTab, slug: string | null | undefined) {
  void artifacts.openHtmlPreview(tab, slug)
}

function handleDetailDialogOpen(open: boolean) {
  if (!open) {
    emit("close-detail")
  }
}

onMounted(artifacts.loadArtifacts)

watch(
  () => [props.tab, selectedDetailSlug.value] as const,
  ([tab, slug]) => {
    void artifacts.loadDetail(tab, slug)
  },
  { immediate: true },
)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex items-center justify-end">
        <Button
          variant="outline"
          size="sm"
          :disabled="artifacts.listLoading.value"
          @click="artifacts.loadArtifacts"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <template v-if="props.tab === 'dashboard'">
        <ArtifactCollectionGrid
          :items="artifacts.dashboards.value"
          :loading="artifacts.listLoading.value"
          :opening-slug="dashboardOpeningSlug"
          empty-title="暂无仪表盘"
          @select="openArtifact('dashboard', $event)"
          @open-preview="openPreview('dashboard', $event)"
        />
      </template>

      <template v-else>
        <ArtifactCollectionGrid
          :items="artifacts.reports.value"
          :loading="artifacts.listLoading.value"
          :opening-slug="reportOpeningSlug"
          empty-title="暂无报表"
          @select="openArtifact('report', $event)"
          @open-preview="openPreview('report', $event)"
        />
      </template>
    </div>

    <Dialog
      :open="detailDialogOpen"
      @update:open="handleDetailDialogOpen"
    >
      <DialogScrollContent class="max-h-[88vh] w-[calc(100vw-2rem)] min-w-0 overflow-y-auto sm:max-w-2xl lg:max-w-4xl">
        <DialogHeader class="min-w-0 pr-8">
          <DialogTitle>{{ detailKindLabel }}详情</DialogTitle>
          <DialogDescription class="truncate">
            {{ selectedDetailSlug ?? "未选择产物" }}
          </DialogDescription>
        </DialogHeader>

        <div class="pr-1">
          <ArtifactDetailPanel
            v-if="selectedDetailSlug"
            :tab="props.tab"
            :detail="artifacts.activeDetail.value"
            :loading="artifacts.detailLoading.value"
            :error="artifacts.detailError.value"
            :preview-opening="selectedPreviewOpening"
            :query-result="artifacts.queryResult.value"
            :query-loading="artifacts.queryLoading.value"
            :query-error="artifacts.queryError.value"
            :active-query-slug="artifacts.activeQuerySlug.value"
            @open-preview="openPreview(props.tab, selectedDetailSlug)"
            @run-dashboard-query="runDashboardQuery"
          />
        </div>
      </DialogScrollContent>
    </Dialog>
  </section>
</template>
