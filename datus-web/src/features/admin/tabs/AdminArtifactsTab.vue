<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { SearchIcon, ShieldCheckIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import AdminMobileRecord from "@/features/admin/AdminMobileRecord.vue"
import AdminPaginationBar from "@/features/admin/AdminPaginationBar.vue"
import type { AdminArtifactsTabProps } from "@/features/admin/types"
import {
  matchesKeyword,
  searchKeyword,
  type ArtifactTypeFilter,
} from "@/features/admin/tab-utils"

const props = defineProps<AdminArtifactsTabProps>()

const artifactTypeFilter = shallowRef<ArtifactTypeFilter>("all")
const artifactSearchKeyword = shallowRef("")

const filteredArtifacts = computed(() => {
  const typeFilter = artifactTypeFilter.value
  const keyword = searchKeyword(artifactSearchKeyword.value)

  return props.overview.data.value.artifacts.filter((artifact) => {
    if (typeFilter !== "all" && artifact.artifact_type !== typeFilter) {
      return false
    }
    if (!keyword) {
      return true
    }

    const manifest = artifact.manifest
    return matchesKeyword(keyword, [
      artifact.artifact_type,
      manifest.slug,
      manifest.name,
      manifest.description,
      manifest.datasources?.join(" "),
    ])
  })
})
</script>
<template>
    <TabsContent
      v-if="canViewArtifacts"
      value="artifacts"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">产物</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="artifactTypeFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="产物类型"
              >
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="dashboard">Dashboard</SelectItem>
                  <SelectItem value="report">Report</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="artifactSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Slug / 名称 / 数据源"
                aria-label="搜索产物"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="artifact in filteredArtifacts"
              :key="overview.artifactKey(artifact)"
              :title="artifact.manifest.name"
              :description="artifact.manifest.slug"
            >
              <template #status>
                <Badge variant="outline">{{ artifact.artifact_type }}</Badge>
              </template>
              <span class="break-all">数据源 {{ artifact.manifest.datasources?.join(", ") || "-" }}</span>
              <span>更新于 {{ formatOptionalDate(artifact.manifest.updated_at || artifact.manifest.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestArtifactAcl(artifact)"
                >
                  <ShieldCheckIcon data-icon="inline-start" />
                  查看 ACL
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredArtifacts.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.artifacts.length === 0 ? "暂无产物" : "没有匹配的产物" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead class="text-center">类型</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>名称</TableHead>
                <TableHead>数据源</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="artifact in filteredArtifacts"
                :key="overview.artifactKey(artifact)"
              >
                <TableCell class="text-center">
                  <Badge variant="outline">{{ artifact.artifact_type }}</Badge>
                </TableCell>
                <TableCell class="font-medium">{{ artifact.manifest.slug }}</TableCell>
                <TableCell>{{ artifact.manifest.name }}</TableCell>
                <TableCell>{{ artifact.manifest.datasources?.join(", ") || "-" }}</TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(artifact.manifest.updated_at || artifact.manifest.created_at) }}</TableCell>
                <TableCell class="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="requestArtifactAcl(artifact)"
                  >
                    <ShieldCheckIcon data-icon="inline-start" />
                    ACL
                  </Button>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredArtifacts.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.artifacts.length === 0 ? "暂无产物" : "没有匹配的产物" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.artifactPagination.currentPage.value"
            :page-size="overview.artifactPagination.pageSize.value"
            :has-previous="overview.artifactPagination.hasPrevious.value"
            :has-more="overview.artifactPagination.hasMore.value"
            :item-count="overview.data.value.artifacts.length"
            :loading="overview.loading.value"
            @previous="overview.artifactPageActions.previous"
            @next="overview.artifactPageActions.next"
            @update:page-size="overview.artifactPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
