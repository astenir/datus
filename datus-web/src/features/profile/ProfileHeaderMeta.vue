<script setup lang="ts">
import { computed } from "vue"
import { Badge } from "@/components/ui/badge"
import type { UserInfo } from "@/composables/useAuth"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "ghost" | "link"

const props = defineProps<{
  user: UserInfo | null
  userId: string
  roles: readonly string[]
  isAdmin: boolean
  loaded: boolean
}>()

function clean(value: string | null | undefined): string {
  return value?.trim() ?? ""
}

const displayName = computed(() => {
  return clean(props.user?.realname)
    || clean(props.user?.username)
    || (props.userId !== "-" ? props.userId : "当前用户")
})

const username = computed(() => clean(props.user?.username) || (props.userId !== "-" ? props.userId : ""))
const identityLabel = computed(() => {
  return username.value && username.value !== displayName.value
    ? `${displayName.value} · ${username.value}`
    : displayName.value
})

const accountStatus = computed<{ label: string; variant: BadgeVariant }>(() => {
  const status = clean(props.user?.userStatus).toLowerCase()
  if (["正常", "normal", "active", "enabled"].includes(status)) {
    return { label: "账号正常", variant: "secondary" }
  }
  if (["禁用", "停用", "disabled", "inactive", "locked"].includes(status)) {
    return { label: "账号停用", variant: "destructive" }
  }
  return { label: "已登录", variant: "outline" }
})

const roleSummary = computed(() => {
  if (props.isAdmin) return "全局管理"

  const roles = props.roles.map(clean).filter(Boolean)
  if (roles.length === 0) return "暂无角色"

  const visibleRoles = roles.slice(0, 2)
  const hiddenRoleCount = roles.length - visibleRoles.length
  return `${visibleRoles.join("、")}${hiddenRoleCount > 0 ? ` +${hiddenRoleCount}` : ""}`
})
</script>

<template>
  <span
    class="max-w-64 truncate text-base font-semibold text-foreground"
    :title="identityLabel"
  >
    {{ identityLabel }}
  </span>
  <Badge :variant="accountStatus.variant">
    {{ accountStatus.label }}
  </Badge>
  <Badge
    v-if="loaded"
    variant="outline"
    class="max-w-52 truncate"
    :title="`当前角色：${roleSummary}`"
  >
    角色 {{ roleSummary }}
  </Badge>
</template>
