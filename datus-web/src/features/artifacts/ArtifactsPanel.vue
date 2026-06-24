<script setup lang="ts">
import { onMounted, ref, shallowRef } from "vue"
import { ExternalLinkIcon, RefreshCwIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { dashboardApi, reportApi } from "@/lib/api"
import { useConnection } from "@/composables/useConnection"
import type { ArtifactManifest } from "@/types"
import type { ArtifactViewTab } from "@/features/workspace/types"
import { isArtifactViewTab } from "@/features/workspace/types"

const { effectiveBase } = useConnection()
const props = withDefaults(defineProps<{
  tab?: ArtifactViewTab
}>(), {
  tab: "dashboard",
})
const emit = defineEmits<{
  "update:tab": [value: ArtifactViewTab]
}>()
const dashboards = ref<ArtifactManifest[]>([])
const reports = ref<ArtifactManifest[]>([])
const loading = shallowRef(false)

async function loadArtifacts() {
  loading.value = true
  try {
    const base = effectiveBase()
    const [dashboardResult, reportResult] = await Promise.all([
      dashboardApi.list(base),
      reportApi.list(base),
    ])
    dashboards.value = dashboardResult ?? []
    reports.value = reportResult ?? []
  } finally {
    loading.value = false
  }
}

function setTab(value: unknown) {
  if (typeof value === "string" && isArtifactViewTab(value)) {
    emit("update:tab", value)
  }
}

onMounted(loadArtifacts)
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
          :disabled="loading"
          @click="loadArtifacts"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <TabsContent value="dashboard">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Card
            v-for="item in dashboards"
            :key="item.slug"
          >
            <CardHeader>
              <CardTitle class="text-base">{{ item.name }}</CardTitle>
            </CardHeader>
            <CardContent class="flex flex-col gap-3">
              <p class="min-h-10 text-sm text-muted-foreground">{{ item.description }}</p>
              <Button
                as="a"
                target="_blank"
                :href="dashboardApi.htmlUrl(effectiveBase(), item.slug)"
                variant="outline"
                size="sm"
              >
                <ExternalLinkIcon data-icon="inline-start" />
                打开
              </Button>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="report">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Card
            v-for="item in reports"
            :key="item.slug"
          >
            <CardHeader>
              <CardTitle class="text-base">{{ item.name }}</CardTitle>
            </CardHeader>
            <CardContent class="flex flex-col gap-3">
              <p class="min-h-10 text-sm text-muted-foreground">{{ item.description }}</p>
              <Button
                as="a"
                target="_blank"
                :href="reportApi.htmlUrl(effectiveBase(), item.slug)"
                variant="outline"
                size="sm"
              >
                <ExternalLinkIcon data-icon="inline-start" />
                打开
              </Button>
            </CardContent>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  </section>
</template>
