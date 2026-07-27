<script setup lang="ts">
import { ChevronLeftIcon, ChevronRightIcon } from "@lucide/vue"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { adminPageSizeOptions } from "@/composables/useAdminPagination"

const props = defineProps<{
  page: number
  pageSize: number
  hasPrevious: boolean
  hasMore: boolean
  itemCount: number
  loading: boolean
}>()

const emit = defineEmits<{
  previous: []
  next: []
  "update:pageSize": [value: number]
}>()

function updatePageSize(value: unknown): void {
  const pageSize = Number(value)
  if (adminPageSizeOptions.includes(pageSize as (typeof adminPageSizeOptions)[number])) {
    emit("update:pageSize", pageSize)
  }
}
</script>

<template>
  <div class="flex w-full flex-wrap items-center justify-between gap-3">
    <p class="text-sm text-muted-foreground">
      第 {{ props.page }} 页 · 本页 {{ props.itemCount }} 条
    </p>
    <div class="flex items-center gap-2">
      <span class="hidden text-sm text-muted-foreground sm:inline">每页</span>
      <Select
        :model-value="String(props.pageSize)"
        :disabled="props.loading"
        @update:model-value="updatePageSize"
      >
        <SelectTrigger
          class="w-20"
          size="sm"
          aria-label="每页条数"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="option in adminPageSizeOptions"
              :key="option"
              :value="String(option)"
            >
              {{ option }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Button
        variant="outline"
        size="sm"
        :disabled="props.loading || !props.hasPrevious"
        @click="emit('previous')"
      >
        <ChevronLeftIcon data-icon="inline-start" />
        上一页
      </Button>
      <Button
        variant="outline"
        size="sm"
        :disabled="props.loading || !props.hasMore"
        @click="emit('next')"
      >
        下一页
        <ChevronRightIcon data-icon="inline-end" />
      </Button>
    </div>
  </div>
</template>
