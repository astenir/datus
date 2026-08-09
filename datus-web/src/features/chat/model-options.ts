import type { SelectOption } from "@/types"

export type ModelOptionGroup = {
  provider: string
  label: string
  options: SelectOption[]
}

export function modelOptionLabel(value: string, options: readonly SelectOption[]): string {
  if (!value) return ""
  return options.find(option => option.value === value)?.label ?? value
}

export function modelProviderKey(option: SelectOption): string {
  if (option.group) return option.group
  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim().toLowerCase()

  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim().toLowerCase()

  return "other"
}

export function modelProviderLabel(option: SelectOption): string {
  if (option.group) return option.group
  const separatorIndex = option.label.indexOf(":")
  if (separatorIndex > 0) return option.label.slice(0, separatorIndex).trim()

  const [rawProvider] = option.value.split("/")
  if (rawProvider && rawProvider !== option.value) return rawProvider.trim()

  return "其他模型"
}

export function groupModelOptions(options: readonly SelectOption[]): ModelOptionGroup[] {
  const groups = new Map<string, ModelOptionGroup>()

  for (const option of options) {
    const key = modelProviderKey(option)
    const group = groups.get(key)

    if (group) {
      group.options.push(option)
      continue
    }

    groups.set(key, {
      provider: key,
      label: modelProviderLabel(option),
      options: [option],
    })
  }

  return Array.from(groups.values())
}
