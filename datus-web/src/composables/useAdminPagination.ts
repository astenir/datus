import { computed, shallowRef } from "vue";

import type { PaginatedApiResponse } from "@/types/admin";

export const adminPageSizeOptions = [20, 50, 100] as const;
export const defaultAdminPageSize = 20;

export function useAdminPagination() {
  const pageSize = shallowRef(defaultAdminPageSize);
  const offset = shallowRef(0);
  const hasMore = shallowRef(false);

  const currentPage = computed(() => Math.floor(offset.value / pageSize.value) + 1);
  const hasPrevious = computed(() => offset.value > 0);

  function applyResponse<T>(response: PaginatedApiResponse<T[]> | null | undefined): T[] {
    const items = response?.data ?? [];
    const pagination = response?.pagination;
    if (pagination) {
      hasMore.value = pagination.has_more;
      offset.value = pagination.offset;
      return items.slice(0, pageSize.value);
    }

    const pageEnd = offset.value + pageSize.value;
    hasMore.value = items.length > pageEnd;
    return items.slice(offset.value, pageEnd);
  }

  function reset(): void {
    offset.value = 0;
    hasMore.value = false;
  }

  function setPageSize(value: number): boolean {
    if (!adminPageSizeOptions.includes(value as (typeof adminPageSizeOptions)[number])) return false;
    if (pageSize.value === value) return false;
    pageSize.value = value;
    reset();
    return true;
  }

  function prepareNext(): boolean {
    if (!hasMore.value) return false;
    offset.value += pageSize.value;
    return true;
  }

  function preparePrevious(): boolean {
    if (!hasPrevious.value) return false;
    offset.value = Math.max(0, offset.value - pageSize.value);
    return true;
  }

  return {
    pageSize,
    offset,
    hasMore,
    currentPage,
    hasPrevious,
    applyResponse,
    reset,
    setPageSize,
    prepareNext,
    preparePrevious,
  };
}
