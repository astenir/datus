<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { artifactPreviewKey, useArtifacts } from "@/composables/useArtifacts"
import ArtifactCollectionGrid from "@/features/artifacts/ArtifactCollectionGrid.vue"
import ArtifactDetailPanel from "@/features/artifacts/ArtifactDetailPanel.vue"
import type { ArtifactViewTab } from "@/features/workspace/types"
import { isArtifactViewTab } from "@/features/workspace/types"

const props = withDefaults(defineProps<{
  tab?: ArtifactViewTab
  selectedSlug?: string | null
}>(), {
  tab: "dashboard",
  selectedSlug: null,
})
const emit = defineEmits<{
  "update:tab": [value: ArtifactViewTab]
  "open-artifact": [tab: ArtifactViewTab, slug: string]
  "close-detail": []
}>()

const artifacts = useArtifacts()

const selectedPreviewKey = computed(() => {
  const slug = props.selectedSlug?.trim()
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

function setTab(value: unknown) {
  if (typeof value === "string" && isArtifactViewTab(value)) {
    emit("update:tab", value)
  }
}

function openArtifact(tab: ArtifactViewTab, slug: string) {
  emit("open-artifact", tab, slug)
}

function runDashboardQuery(querySlug: string, params: Record<string, unknown>) {
  if (props.tab !== "dashboard" || !props.selectedSlug) return
  void artifacts.runDashboardQuery(props.selectedSlug, querySlug, params)
}

function openPreview(tab: ArtifactViewTab, slug: string | null | undefined) {
  void artifacts.openHtmlPreview(tab, slug)
}

onMounted(artifacts.loadArtifacts)

watch(
  () => [props.tab, props.selectedSlug] as const,
  ([tab, slug]) => {
    void artifacts.loadDetail(tab, slug)
  },
  { immediate: true },
)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <Tabs
      :model-value="props.tab"
      class="flex flex-col gap-4"
      @update:model-value="setTab"
    >
      <div class="flex items-center gap-3">
        <TabsList>
          <TabsTrigger value="dashboard">仪表盘</TabsTrigger>
          <TabsTrigger value="report">报表</TabsTrigger>
        </TabsList>
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

      <TabsContent value="dashboard">
        <div
          class="grid items-start gap-4"
          :class="props.selectedSlug ? 'lg:grid-cols-[minmax(0,1fr)_28rem]' : ''"
        >
          <ArtifactCollectionGrid
            :items="artifacts.dashboards.value"
            :loading="artifacts.listLoading.value"
            :opening-slug="dashboardOpeningSlug"
            empty-title="暂无仪表盘"
            @select="openArtifact('dashboard', $event)"
            @open-preview="openPreview('dashboard', $event)"
          />
          <ArtifactDetailPanel
            v-if="props.selectedSlug"
            tab="dashboard"
            :slug="props.selectedSlug"
            :detail="artifacts.activeDetail.value"
            :loading="artifacts.detailLoading.value"
            :error="artifacts.detailError.value"
            :preview-opening="selectedPreviewOpening"
            :query-result="artifacts.queryResult.value"
            :query-loading="artifacts.queryLoading.value"
            :query-error="artifacts.queryError.value"
            :active-query-slug="artifacts.activeQuerySlug.value"
            @close="emit('close-detail')"
            @open-preview="openPreview('dashboard', props.selectedSlug)"
            @run-dashboard-query="runDashboardQuery"
          />
        </div>
      </TabsContent>

      <TabsContent value="report">
        <div
          class="grid items-start gap-4"
          :class="props.selectedSlug ? 'lg:grid-cols-[minmax(0,1fr)_28rem]' : ''"
        >
          <ArtifactCollectionGrid
            :items="artifacts.reports.value"
            :loading="artifacts.listLoading.value"
            :opening-slug="reportOpeningSlug"
            empty-title="暂无报表"
            @select="openArtifact('report', $event)"
            @open-preview="openPreview('report', $event)"
          />
          <ArtifactDetailPanel
            v-if="props.selectedSlug"
            tab="report"
            :slug="props.selectedSlug"
            :detail="artifacts.activeDetail.value"
            :loading="artifacts.detailLoading.value"
            :error="artifacts.detailError.value"
            :preview-opening="selectedPreviewOpening"
            :query-result="artifacts.queryResult.value"
            :query-loading="artifacts.queryLoading.value"
            :query-error="artifacts.queryError.value"
            :active-query-slug="artifacts.activeQuerySlug.value"
            @close="emit('close-detail')"
            @open-preview="openPreview('report', props.selectedSlug)"
          />
        </div>
      </TabsContent>
    </Tabs>
  </section>
</template>
