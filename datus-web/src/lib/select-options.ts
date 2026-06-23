import type { SelectOption } from "@/types";

export function filterSelectOptions(options: readonly SelectOption[], query: string): SelectOption[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [...options];

  return options.filter((option) => {
    const label = option.label.toLowerCase();
    const value = option.value.toLowerCase();
    return label.includes(normalized) || value.includes(normalized);
  });
}
