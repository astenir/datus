<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  BarChart3Icon,
  EyeIcon,
  FilePenLineIcon,
  RefreshCwIcon,
  Share2Icon,
  Trash2Icon,
} from "@lucide/vue"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"
import { artifactPreviewKey, useArtifacts } from "@/composables/useArtifacts"
import ArtifactCollectionGrid from "@/features/artifacts/ArtifactCollectionGrid.vue"
import ArtifactDetailPanel from "@/features/artifacts/ArtifactDetailPanel.vue"
import ArtifactShareDialog from "@/features/artifacts/ArtifactShareDialog.vue"
import ArtifactViewerFrame from "@/features/artifacts/ArtifactViewerFrame.vue"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import {
  artifactRepairPrompt,
  type ArtifactPreviewQueryRequest,
  type ArtifactRenderError,
} from "@/lib/artifact-preview-bridge"
import type { ArtifactEditSession, ArtifactShareUpdate } from "@/types"
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
  "edit-artifact": [session: ArtifactEditSession]
  "repair-artifact": [session: ArtifactEditSession, prompt: string]
}>()

const artifacts = useArtifacts()
const shareDialogOpen = shallowRef(false)
const shareTargetTab = shallowRef<ArtifactViewTab>("dashboard")
const shareTargetSlug = shallowRef<string | null>(null)
const detailDialogOpen = shallowRef(false)
const detailTargetSlug = shallowRef<string | null>(null)
const deleteConfirmOpen = shallowRef(false)
const deleteTargetTab = shallowRef<ArtifactViewTab>("dashboard")
const deleteTargetSlug = shallowRef<string | null>(null)

const selectedViewerSlug = computed(() => props.selectedSlug?.trim() || null)
const selectedDetailSlug = computed(() => detailTargetSlug.value)
const detailKindLabel = computed(() => props.tab === "report" ? "报表" : "仪表盘")
const artifactPageDescription = computed(() => props.tab === "report"
  ? "浏览、预览和管理报表产物。"
  : "浏览、预览和管理仪表盘产物。")
const artifactCount = computed(() => props.tab === "report"
  ? artifacts.reports.value.length
  : artifacts.dashboards.value.length)
const detailDialogTitle = computed(() => {
  if (artifacts.detailLoading.value) return `${detailKindLabel.value}详情`
  return artifacts.activeDetail.value?.name?.trim() || `${detailKindLabel.value}详情`
})
const viewerPreviewKey = computed(() => {
  const slug = selectedViewerSlug.value
  return slug ? artifactPreviewKey(props.tab, slug) : null
})

const viewerPreviewOpening = computed(() => {
  return Boolean(viewerPreviewKey.value && artifacts.previewLoadingKey.value === viewerPreviewKey.value)
})
const viewerRepairing = computed(() => editingSlugFor(props.tab) === selectedViewerSlug.value)
const viewerPreviewUrl = computed(() => {
  if (!viewerPreviewKey.value) return null
  const activeKey = artifacts.activePreviewTab.value && artifacts.activePreviewSlug.value
    ? artifactPreviewKey(artifacts.activePreviewTab.value, artifacts.activePreviewSlug.value)
    : null
  return activeKey === viewerPreviewKey.value ? artifacts.activePreviewUrl.value : null
})
const selectedViewerCanEdit = computed(() => {
  const slug = selectedViewerSlug.value
  if (!slug) return false

  const items = props.tab === "report" ? artifacts.reports.value : artifacts.dashboards.value
  return items.some(item => item.slug === slug && item.can_edit === true)
})
const selectedShareLoading = computed(() => {
  const slug = selectedDetailSlug.value
  if (!slug) return false
  return artifacts.shareLoadingKey.value === artifactPreviewKey(props.tab, slug)
})
const selectedPreviewOpening = computed(() => {
  const slug = selectedDetailSlug.value
  if (!slug) return false
  return artifacts.previewLoadingKey.value === artifactPreviewKey(props.tab, slug)
})
const selectedDetailCanManageShare = computed(() => {
  const slug = selectedDetailSlug.value
  if (!slug) return false

  const items = props.tab === "report" ? artifacts.reports.value : artifacts.dashboards.value
  return items.some(item => item.slug === slug && item.can_manage_share === true)
})
const selectedDetailCanEdit = computed(() => {
  const slug = selectedDetailSlug.value
  if (!slug) return false

  const items = props.tab === "report" ? artifacts.reports.value : artifacts.dashboards.value
  return items.some(item => item.slug === slug && item.can_edit === true)
})
const selectedEditLoading = computed(() => editingSlugFor(props.tab) === selectedDetailSlug.value)
const selectedDeleting = computed(() => {
  const slug = selectedDetailSlug.value
  if (!slug) return false
  return artifacts.deleteLoadingKey.value === artifactPreviewKey(props.tab, slug)
})
const deleteTargetName = computed(() => {
  const slug = deleteTargetSlug.value
  if (!slug) return ""
  const items = deleteTargetTab.value === "report" ? artifacts.reports.value : artifacts.dashboards.value
  return items.find(item => item.slug === slug)?.name?.trim() || slug
})
const deleteTargetKindLabel = computed(() => deleteTargetTab.value === "report" ? "报表" : "仪表盘")
const deleteConfirmLoading = computed(() => {
  const slug = deleteTargetSlug.value
  if (!slug) return false
  return artifacts.deleteLoadingKey.value === artifactPreviewKey(deleteTargetTab.value, slug)
})

const dashboardOpeningSlug = computed(() => loadingSlugFor("dashboard"))
const reportOpeningSlug = computed(() => loadingSlugFor("report"))
const dashboardSharingSlug = computed(() => sharingSlugFor("dashboard"))
const reportSharingSlug = computed(() => sharingSlugFor("report"))
const dashboardEditingSlug = computed(() => editingSlugFor("dashboard"))
const reportEditingSlug = computed(() => editingSlugFor("report"))
const dashboardDeletingSlug = computed(() => deletingSlugFor("dashboard"))
const reportDeletingSlug = computed(() => deletingSlugFor("report"))

function loadingSlugFor(tab: ArtifactViewTab): string | null {
  const key = artifacts.previewLoadingKey.value
  const prefix = `${tab}:`
  return key?.startsWith(prefix) ? key.slice(prefix.length) : null
}

function sharingSlugFor(tab: ArtifactViewTab): string | null {
  const key = artifacts.shareLoadingKey.value
  const prefix = `${tab}:`
  return key?.startsWith(prefix) ? key.slice(prefix.length) : null
}

function editingSlugFor(tab: ArtifactViewTab): string | null {
  const key = artifacts.editLoadingKey.value
  const prefix = `${tab}:`
  return key?.startsWith(prefix) ? key.slice(prefix.length) : null
}

function deletingSlugFor(tab: ArtifactViewTab): string | null {
  const key = artifacts.deleteLoadingKey.value
  const prefix = `${tab}:`
  return key?.startsWith(prefix) ? key.slice(prefix.length) : null
}

function runDashboardQuery(querySlug: string, params: Record<string, unknown>) {
  if (props.tab !== "dashboard" || !selectedDetailSlug.value) return
  void artifacts.runDashboardQuery(selectedDetailSlug.value, querySlug, params)
}

function runViewerDashboardQuery(request: ArtifactPreviewQueryRequest, signal: AbortSignal) {
  return artifacts.runDashboardPreviewQuery(
    request.dashboardSlug,
    request.querySlug,
    request.params,
    request.publishedVersion,
    signal,
  )
}

function openPreview(tab: ArtifactViewTab, slug: string | null | undefined) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  detailDialogOpen.value = false
  detailTargetSlug.value = null
  emit("open-artifact", tab, normalizedSlug)
}

function openDetail(tab: ArtifactViewTab, slug: string | null | undefined) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  detailTargetSlug.value = normalizedSlug
  detailDialogOpen.value = true
  void artifacts.loadDetail(tab, normalizedSlug)
}

function openShare(tab: ArtifactViewTab, slug: string | null | undefined) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  shareTargetTab.value = tab
  shareTargetSlug.value = normalizedSlug
  shareDialogOpen.value = true
  void artifacts.loadShare(tab, normalizedSlug)
  void artifacts.loadShareDirectory(tab)
}

async function saveShare(share: ArtifactShareUpdate) {
  const saved = await artifacts.saveShare(share)
  if (saved) {
    shareDialogOpen.value = false
    artifacts.clearShare()
  }
}

async function editArtifact(tab: ArtifactViewTab, slug: string | null | undefined) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  const session = await artifacts.createArtifactEditSession(tab, normalizedSlug)
  if (!session) return

  detailDialogOpen.value = false
  detailTargetSlug.value = null
  emit("edit-artifact", session)
}

async function repairArtifact(
  tab: ArtifactViewTab,
  slug: string | null | undefined,
  error: ArtifactRenderError,
) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  const session = await artifacts.createArtifactEditSession(tab, normalizedSlug)
  if (!session) return

  emit("repair-artifact", session, artifactRepairPrompt(tab, normalizedSlug, error))
}

function handleShareDialogOpen(open: boolean) {
  shareDialogOpen.value = open
  if (!open) {
    artifacts.clearShare()
    shareTargetSlug.value = null
  }
}

function handleDeleteConfirmOpen(open: boolean) {
  deleteConfirmOpen.value = open
  if (!open) {
    deleteTargetSlug.value = null
  }
}

function requestDelete(tab: ArtifactViewTab, slug: string | null | undefined) {
  const normalizedSlug = slug?.trim() || null
  if (!normalizedSlug) return

  deleteTargetTab.value = tab
  deleteTargetSlug.value = normalizedSlug
  deleteConfirmOpen.value = true
}

async function confirmDelete() {
  const tab = deleteTargetTab.value
  const slug = deleteTargetSlug.value
  if (!slug) return

  const deleted = await artifacts.deleteArtifact(tab, slug)
  if (!deleted) return

  deleteConfirmOpen.value = false
  deleteTargetSlug.value = null
  if (detailTargetSlug.value === slug) {
    detailDialogOpen.value = false
    detailTargetSlug.value = null
  }
  void artifacts.loadArtifacts(tab)
}

function handleDetailDialogOpen(open: boolean) {
  detailDialogOpen.value = open
  if (!open) {
    detailTargetSlug.value = null
  }
}

watch(
  () => props.tab,
  tab => {
    void artifacts.loadArtifacts(tab)
  },
  { immediate: true },
)

watch(
  () => [props.tab, selectedViewerSlug.value] as const,
  ([tab, slug]) => {
    if (slug) {
      void artifacts.openHtmlPreview(tab, slug)
      return
    }

    artifacts.clearPreview()
  },
  { immediate: true },
)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-hidden">
    <ArtifactViewerFrame
      v-if="selectedViewerSlug"
      class="h-full rounded-none border-0"
      :title="detailKindLabel"
      :url="viewerPreviewUrl"
      :loading="viewerPreviewOpening"
      :error="artifacts.previewError.value"
      :show-chrome="false"
      :dashboard-slug="props.tab === 'dashboard' ? selectedViewerSlug : null"
      :query="props.tab === 'dashboard' ? runViewerDashboardQuery : undefined"
      :can-repair="selectedViewerCanEdit"
      :repairing="viewerRepairing"
      @reload="artifacts.openHtmlPreview(props.tab, selectedViewerSlug)"
      @repair="repairArtifact(props.tab, selectedViewerSlug, $event)"
    />

    <div
      v-else
      class="flex h-full flex-col gap-4 overflow-y-auto p-4"
    >
      <PageHeaderToolbar
        :title="detailKindLabel"
        :description="artifactPageDescription"
        aria-label="产物页头工具栏"
      >
        <template #leading>
          <BarChart3Icon />
        </template>

        <template #meta>
          <Badge variant="secondary">{{ artifactCount }} 个</Badge>
        </template>

        <template #actions>
          <Button
            variant="outline"
            size="sm"
            :disabled="artifacts.listLoading.value"
            @click="artifacts.loadArtifacts(props.tab)"
          >
            <RefreshCwIcon
              data-icon="inline-start"
              :class="artifacts.listLoading.value && 'animate-spin'"
            />
            {{ artifacts.listLoading.value ? "刷新中" : "刷新" }}
          </Button>
        </template>
      </PageHeaderToolbar>

      <template v-if="props.tab === 'dashboard'">
        <ArtifactCollectionGrid
          :items="artifacts.dashboards.value"
          :loading="artifacts.listLoading.value"
          :opening-slug="dashboardOpeningSlug"
          :sharing-slug="dashboardSharingSlug"
          :editing-slug="dashboardEditingSlug"
          :deleting-slug="dashboardDeletingSlug"
          :edit-enabled="true"
          empty-title="暂无仪表盘"
          @select="openDetail('dashboard', $event)"
          @open-preview="openPreview('dashboard', $event)"
          @share="openShare('dashboard', $event)"
          @edit="editArtifact('dashboard', $event)"
          @delete="requestDelete('dashboard', $event)"
        />
      </template>

      <template v-else>
        <ArtifactCollectionGrid
          :items="artifacts.reports.value"
          :loading="artifacts.listLoading.value"
          :opening-slug="reportOpeningSlug"
          :sharing-slug="reportSharingSlug"
          :editing-slug="reportEditingSlug"
          :deleting-slug="reportDeletingSlug"
          :edit-enabled="true"
          empty-title="暂无报表"
          @select="openDetail('report', $event)"
          @open-preview="openPreview('report', $event)"
          @share="openShare('report', $event)"
          @edit="editArtifact('report', $event)"
          @delete="requestDelete('report', $event)"
        />
      </template>
    </div>

    <Dialog
      :open="detailDialogOpen"
      @update:open="handleDetailDialogOpen"
    >
      <DialogScrollContent class="my-0 grid h-[100dvh] max-h-[100dvh] w-screen max-w-none min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden border-0 p-0 sm:my-8 sm:h-auto sm:max-h-[88vh] sm:w-[calc(100vw-2rem)] sm:max-w-3xl sm:rounded-lg sm:border md:w-[calc(100vw-2rem)] lg:max-w-5xl">
        <DialogHeader class="min-w-0 border-b px-4 py-4 pr-12 sm:px-6 sm:py-5 sm:pr-14">
          <div class="flex min-w-0 items-center gap-2">
            <Badge
              class="shrink-0"
              variant="secondary"
            >
              {{ detailKindLabel }}
            </Badge>
            <DialogTitle class="min-w-0 truncate">{{ detailDialogTitle }}</DialogTitle>
          </div>
          <DialogDescription class="truncate">
            {{ selectedDetailSlug ?? "未选择产物" }}
          </DialogDescription>
        </DialogHeader>

        <div class="min-h-0 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          <ArtifactDetailPanel
            v-if="selectedDetailSlug"
            :tab="props.tab"
            :detail="artifacts.activeDetail.value"
            :loading="artifacts.detailLoading.value"
            :error="artifacts.detailError.value"
            :query-result="artifacts.queryResult.value"
            :query-loading="artifacts.queryLoading.value"
            :query-error="artifacts.queryError.value"
            :active-query-slug="artifacts.activeQuerySlug.value"
            @run-dashboard-query="runDashboardQuery"
          />
        </div>

        <DialogFooter
          v-if="artifacts.activeDetail.value && !artifacts.detailLoading.value && !artifacts.detailError.value"
          class="shrink-0 border-t px-4 py-3 sm:px-6"
        >
          <Button
            v-if="selectedDetailCanManageShare"
            variant="outline"
            size="sm"
            :disabled="selectedShareLoading"
            @click="openShare(props.tab, selectedDetailSlug)"
          >
            <Spinner
              v-if="selectedShareLoading"
              data-icon="inline-start"
            />
            <Share2Icon
              v-else
              data-icon="inline-start"
            />
            {{ selectedShareLoading ? "加载中" : "分享设置" }}
          </Button>
          <Button
            v-if="selectedDetailCanEdit"
            variant="outline"
            size="sm"
            :disabled="selectedEditLoading"
            @click="editArtifact(props.tab, selectedDetailSlug)"
          >
            <Spinner
              v-if="selectedEditLoading"
              data-icon="inline-start"
            />
            <FilePenLineIcon
              v-else
              data-icon="inline-start"
            />
            {{ selectedEditLoading ? "创建中" : `编辑${detailKindLabel}` }}
          </Button>
          <Button
            v-if="selectedDetailCanEdit"
            variant="destructive"
            size="sm"
            :disabled="selectedDeleting"
            @click="requestDelete(props.tab, selectedDetailSlug)"
          >
            <Spinner
              v-if="selectedDeleting"
              data-icon="inline-start"
            />
            <Trash2Icon
              v-else
              data-icon="inline-start"
            />
            {{ selectedDeleting ? "删除中" : "删除" }}
          </Button>
          <Button
            size="sm"
            :disabled="selectedPreviewOpening"
            @click="openPreview(props.tab, selectedDetailSlug)"
          >
            <Spinner
              v-if="selectedPreviewOpening"
              data-icon="inline-start"
            />
            <EyeIcon
              v-else
              data-icon="inline-start"
            />
            {{ selectedPreviewOpening ? "加载中" : "查看" }}
          </Button>
        </DialogFooter>
      </DialogScrollContent>
    </Dialog>

    <ArtifactShareDialog
      :open="shareDialogOpen"
      :tab="shareTargetTab"
      :slug="shareTargetSlug"
      :share="artifacts.activeShare.value"
      :user-options="artifacts.shareUserOptions.value"
      :role-options="artifacts.shareRoleOptions.value"
      :loading="Boolean(artifacts.shareLoadingKey.value)"
      :directory-loading="artifacts.shareDirectoryLoading.value"
      :saving="artifacts.shareSaving.value"
      :error="artifacts.shareError.value"
      :directory-error="artifacts.shareDirectoryError.value"
      @update:open="handleShareDialogOpen"
      @save="saveShare"
    />

    <AlertDialog
      :open="deleteConfirmOpen"
      @update:open="handleDeleteConfirmOpen"
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>删除{{ deleteTargetKindLabel }}「{{ deleteTargetName }}」？</AlertDialogTitle>
          <AlertDialogDescription>
            删除后无法恢复，其分享设置将一并移除。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel as-child>
            <Button variant="outline">取消</Button>
          </AlertDialogCancel>
          <Button
            variant="destructive"
            :disabled="deleteConfirmLoading"
            @click="confirmDelete"
          >
            <Spinner
              v-if="deleteConfirmLoading"
              data-icon="inline-start"
            />
            <Trash2Icon
              v-else
              data-icon="inline-start"
            />
            {{ deleteConfirmLoading ? "删除中" : "确认删除" }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </section>
</template>
