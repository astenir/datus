import { describe, expect, it } from "vitest";

import { useAdminPagination } from "@/composables/useAdminPagination";

describe("useAdminPagination", () => {
  it("applies backend metadata and moves through bounded pages", () => {
    const pagination = useAdminPagination();

    const items = pagination.applyResponse({
      success: true,
      data: Array.from({ length: 20 }, (_, index) => index),
      pagination: { limit: 20, offset: 0, has_more: true },
    });

    expect(items).toHaveLength(20);
    expect(pagination.hasMore.value).toBe(true);
    expect(pagination.prepareNext()).toBe(true);
    expect(pagination.offset.value).toBe(20);
    expect(pagination.currentPage.value).toBe(2);
    expect(pagination.preparePrevious()).toBe(true);
    expect(pagination.offset.value).toBe(0);
  });

  it("client-pages legacy array responses without rendering the full list", () => {
    const pagination = useAdminPagination();
    const response = {
      success: true,
      data: Array.from({ length: 75 }, (_, index) => index),
    };
    const firstPage = pagination.applyResponse(response);

    expect(firstPage).toEqual(Array.from({ length: 20 }, (_, index) => index));
    expect(pagination.hasMore.value).toBe(true);
    expect(pagination.prepareNext()).toBe(true);

    const secondPage = pagination.applyResponse(response);
    expect(secondPage).toEqual(Array.from({ length: 20 }, (_, index) => index + 20));
    expect(pagination.hasMore.value).toBe(true);
  });
});
