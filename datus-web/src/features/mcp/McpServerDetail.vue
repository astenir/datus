<script setup lang="ts">
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import type { PersonalMcpSummary, PersonalMcpToolSummary } from "@/types/profile"

defineProps<{
  server: PersonalMcpSummary | null
  tools: readonly PersonalMcpToolSummary[]
  toolsLoading: boolean
  canViewTools: boolean
}>()
</script>

<template>
  <div class="rounded-md border p-4">
    <div v-if="server" class="flex flex-col gap-4">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-sm font-semibold">{{ server.display_name }}</h3>
          <Badge :variant="server.enabled ? 'secondary' : 'outline'">
            {{ server.enabled ? "启用" : "停用" }}
          </Badge>
          <Badge variant="outline">修订 {{ server.revision }}</Badge>
        </div>
        <p class="mt-1 break-all font-mono text-xs text-muted-foreground">{{ server.url }}</p>
      </div>

      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-xs text-muted-foreground">传输协议</dt>
          <dd class="mt-1">{{ server.transport.toUpperCase() }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">认证</dt>
          <dd class="mt-1">{{ server.credential_configured ? server.token_hint || "个人 Bearer 已配置" : "无认证" }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">允许工具</dt>
          <dd class="mt-1 break-words">{{ server.allowed_tools.join(", ") || "全部" }}</dd>
        </div>
        <div>
          <dt class="text-xs text-muted-foreground">禁止工具</dt>
          <dd class="mt-1 break-words">{{ server.blocked_tools.join(", ") || "无" }}</dd>
        </div>
      </dl>

      <Separator />

      <div>
        <div class="flex items-center justify-between gap-2">
          <h4 class="text-sm font-medium">可用工具</h4>
          <Spinner v-if="toolsLoading" />
        </div>
        <p v-if="!canViewTools" class="mt-2 text-sm text-muted-foreground">
          当前角色没有查看个人 MCP 工具的权限。
        </p>
        <p v-else-if="!toolsLoading && tools.length === 0" class="mt-2 text-sm text-muted-foreground">
          暂无工具，或尚未成功加载工具列表。
        </p>
        <ul v-else class="mt-2 flex flex-col gap-2">
          <li
            v-for="tool in tools"
            :key="tool.name"
            class="rounded-md border px-3 py-2"
          >
            <div class="font-mono text-xs font-medium">{{ tool.name }}</div>
            <div v-if="tool.description" class="mt-1 text-xs text-muted-foreground">
              {{ tool.description }}
            </div>
          </li>
        </ul>
      </div>
    </div>
    <div v-else class="py-8 text-center text-sm text-muted-foreground">
      选择一个个人 MCP 查看详情。
    </div>
  </div>
</template>
