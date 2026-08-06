<script setup lang="ts">
import { computed, onUnmounted, shallowRef, watch } from "vue"
import type { AcceptableValue } from "reka-ui"
import {
  BotIcon,
  LockKeyholeIcon,
  PlusIcon,
  PlugZapIcon,
  StarIcon,
} from "@lucide/vue"

import { PromptInputButton } from "@/components/ai-elements/prompt-input"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import type { SelectOption } from "@/types"
import type { PersonalMcpSummary } from "@/types/profile"

const DEFAULT_AGENT_VALUE = "__datus_default_agent__"
const DESKTOP_HOVER_QUERY = "(hover: hover) and (pointer: fine)"
const HOVER_OPEN_DELAY_MS = 150
const HOVER_CLOSE_DELAY_MS = 250

const props = defineProps<{
  selectedAgent: string
  defaultAgentId: string
  userDefaultAgentId: string
  agentOptions: readonly SelectOption[]
  loadingAgents: boolean
  savingDefaultAgent: boolean
  agentDisabled: boolean
  showPersonalMcp: boolean
  servers: readonly PersonalMcpSummary[]
  selectedIds: readonly string[]
  mcpLocked: boolean
  loadingMcp: boolean
  mcpDisabled: boolean
  maxSelected: number
  agentAllowsPersonalMcp: boolean
  organizationAvailable: boolean
}>()

const emit = defineEmits<{
  updateAgent: [value: string]
  setDefaultAgent: [value: string]
  requestAgents: []
  toggleMcp: [mcpId: string]
}>()

const menuOpen = shallowRef(false)
const agentMenuOpen = shallowRef(false)
const mcpMenuOpen = shallowRef(false)
const hoverMenuActive = shallowRef(false)
let hoverOpenTimer: ReturnType<typeof setTimeout> | undefined
let hoverCloseTimer: ReturnType<typeof setTimeout> | undefined
let hoverFocusRestoreTimer: ReturnType<typeof setTimeout> | undefined
let hoverFocusTarget: HTMLElement | undefined

const effectiveDefaultAgentLabel = computed(() =>
  optionLabel(props.defaultAgentId, props.agentOptions) || props.defaultAgentId,
)
const defaultAgentLabel = computed(() =>
  effectiveDefaultAgentLabel.value
    ? `跟随默认 Agent（当前：${effectiveDefaultAgentLabel.value}）`
    : "跟随默认 Agent",
)
const selectedAgentLabel = computed(() =>
  optionLabel(props.selectedAgent, props.agentOptions) || props.selectedAgent,
)
const selectedAgentIsUserDefault = computed(() =>
  Boolean(props.selectedAgent) && props.selectedAgent === props.userDefaultAgentId,
)
const defaultAgentActionLabel = computed(() => {
  if (selectedAgentIsUserDefault.value) return `已是默认 · ${selectedAgentLabel.value}`
  if (props.selectedAgent) return `设为默认 · ${selectedAgentLabel.value}`
  return props.userDefaultAgentId ? "清除我的默认设置" : "正在跟随默认 Agent"
})
const defaultAgentActionDisabled = computed(() =>
  props.savingDefaultAgent
  || selectedAgentIsUserDefault.value
  || (!props.selectedAgent && !props.userDefaultAgentId),
)
const agentLabel = computed(() =>
  optionLabel(props.selectedAgent, props.agentOptions) || defaultAgentLabel.value,
)
const selectedSet = computed(() => new Set(props.selectedIds))
const selectedMcpCount = computed(() => props.selectedIds.length)
const visibleServers = computed(() =>
  props.servers.filter(server => server.enabled || selectedSet.value.has(server.id)),
)
const mcpSelectionDisabled = computed(() =>
  props.mcpDisabled
  || props.mcpLocked
  || !props.agentAllowsPersonalMcp
  || !props.organizationAvailable,
)
const mcpCountLabel = computed(() => {
  if (selectedMcpCount.value === 0) return "未选择"
  if (props.maxSelected > 0) return `${selectedMcpCount.value}/${props.maxSelected}`
  return `${selectedMcpCount.value}`
})
const mcpTriggerLabel = computed(() => {
  if (selectedMcpCount.value === 0) {
    return props.mcpLocked ? "MCP（已锁定）" : "MCP"
  }
  return props.mcpLocked
    ? `MCP · ${mcpCountLabel.value}（已锁定）`
    : `MCP · ${mcpCountLabel.value}`
})
const rootTriggerLabel = computed(() =>
  selectedMcpCount.value > 0
    ? `会话设置，已选择 ${selectedMcpCount.value} 个 MCP`
    : "会话设置",
)
watch(menuOpen, (open) => {
  if (!open) {
    agentMenuOpen.value = false
    mcpMenuOpen.value = false
    hoverMenuActive.value = false
    hoverFocusTarget = undefined
    clearHoverTimers()
  }
})

watch(agentMenuOpen, (open) => {
  if (open) emit("requestAgents")
})

watch(() => props.agentDisabled, (disabled) => {
  if (disabled) agentMenuOpen.value = false
})

watch(() => props.mcpDisabled, (disabled) => {
  if (disabled) {
    mcpMenuOpen.value = false
    menuOpen.value = false
    clearHoverTimers()
  }
})

watch(() => props.mcpLocked, (locked) => {
  if (locked) mcpMenuOpen.value = false
})

watch(() => props.showPersonalMcp, (visible) => {
  if (!visible) mcpMenuOpen.value = false
})

onUnmounted(() => {
  clearHoverTimers()
  hoverFocusTarget = undefined
})

function optionLabel(value: string, options: readonly SelectOption[]): string {
  if (!value) return ""
  return options.find(option => option.value === value)?.label ?? value
}

function clearHoverOpenTimer(): void {
  if (hoverOpenTimer === undefined) return
  clearTimeout(hoverOpenTimer)
  hoverOpenTimer = undefined
}

function clearHoverCloseTimer(): void {
  if (hoverCloseTimer === undefined) return
  clearTimeout(hoverCloseTimer)
  hoverCloseTimer = undefined
}

function clearHoverFocusRestoreTimer(): void {
  if (hoverFocusRestoreTimer === undefined) return
  clearTimeout(hoverFocusRestoreTimer)
  hoverFocusRestoreTimer = undefined
}

function clearHoverTimers(): void {
  clearHoverOpenTimer()
  clearHoverCloseTimer()
  clearHoverFocusRestoreTimer()
}

function isDesktopHoverPointer(event: PointerEvent): boolean {
  return event.pointerType === "mouse"
    && typeof window !== "undefined"
    && window.matchMedia(DESKTOP_HOVER_QUERY).matches
}

function scheduleHoverOpen(event: PointerEvent): void {
  if (!isDesktopHoverPointer(event) || menuOpen.value || hoverOpenTimer !== undefined) return

  clearHoverCloseTimer()
  hoverOpenTimer = setTimeout(() => {
    hoverOpenTimer = undefined
    if (menuOpen.value || props.mcpDisabled) return

    const activeElement = document.activeElement
    hoverFocusTarget = activeElement instanceof HTMLElement && activeElement !== document.body
      ? activeElement
      : undefined
    hoverMenuActive.value = true
    menuOpen.value = true
    const focusTarget = hoverFocusTarget
    if (focusTarget) {
      hoverFocusRestoreTimer = window.setTimeout(() => {
        hoverFocusRestoreTimer = undefined
        if (!hoverMenuActive.value || !menuOpen.value || !focusTarget.isConnected) return
        focusTarget.focus({ preventScroll: true })
      }, 0)
    }
  }, HOVER_OPEN_DELAY_MS)
}

function scheduleHoverClose(event: PointerEvent): void {
  if (!isDesktopHoverPointer(event)) return

  clearHoverOpenTimer()
  if (!hoverMenuActive.value) return

  clearHoverCloseTimer()
  hoverCloseTimer = setTimeout(() => {
    hoverCloseTimer = undefined
    if (!hoverMenuActive.value) return
    hoverMenuActive.value = false
    hoverFocusTarget = undefined
    menuOpen.value = false
  }, HOVER_CLOSE_DELAY_MS)
}

function handleTriggerPointerEnter(event: PointerEvent): void {
  clearHoverCloseTimer()
  scheduleHoverOpen(event)
}

function handleTriggerPointerLeave(event: PointerEvent): void {
  scheduleHoverClose(event)
}

function handleMenuPointerEnter(event: PointerEvent): void {
  if (!isDesktopHoverPointer(event)) return
  clearHoverCloseTimer()
}

function handleMenuPointerLeave(event: PointerEvent): void {
  scheduleHoverClose(event)
}

function handleMenuFocusOutside(event: Event): void {
  if (hoverMenuActive.value) event.preventDefault()
}

function handleTriggerInteraction(): void {
  clearHoverTimers()
  hoverMenuActive.value = false
  hoverFocusTarget = undefined
}

function handleTriggerKeydown(event: KeyboardEvent): void {
  if (event.key === "Enter" || event.key === " ") handleTriggerInteraction()
}

function selectAgent(value: AcceptableValue): void {
  if (typeof value !== "string") return
  emit("updateAgent", value === DEFAULT_AGENT_VALUE ? "" : value)
}

function setDefaultAgent(): void {
  emit("setDefaultAgent", props.selectedAgent)
}

function isSelected(id: string): boolean {
  return selectedSet.value.has(id)
}

function handleMcpSelect(event: Event, id: string): void {
  event.preventDefault()
  if (mcpSelectionDisabled.value) return
  emit("toggleMcp", id)
}
</script>

<template>
  <DropdownMenu
    v-model:open="menuOpen"
    :modal="!hoverMenuActive"
  >
    <DropdownMenuTrigger as-child>
      <PromptInputButton
        type="button"
        size="icon-sm"
        :disabled="mcpDisabled"
        :aria-busy="loadingAgents || loadingMcp"
        aria-label="会话设置"
        :title="rootTriggerLabel"
        class="shrink-0 rounded-full text-muted-foreground opacity-60 transition-opacity hover:opacity-100 focus-visible:opacity-100"
        @click="handleTriggerInteraction"
        @keydown="handleTriggerKeydown"
        @pointerenter="handleTriggerPointerEnter"
        @pointerleave="handleTriggerPointerLeave"
      >
        <span
          aria-hidden="true"
          data-session-settings-icon
          class="flex size-4 items-center justify-center"
        >
          <Spinner
            v-if="loadingAgents || loadingMcp"
            aria-hidden="true"
            class="size-4"
          />
          <PlusIcon
            v-else
            class="size-4"
          />
        </span>
      </PromptInputButton>
    </DropdownMenuTrigger>

    <DropdownMenuContent
      side="top"
      align="start"
      :side-offset="8"
      class="w-[min(calc(100vw-1rem),18rem)] max-w-[calc(100vw-1rem)] rounded-2xl shadow-xl"
      @focus-outside="handleMenuFocusOutside"
      @pointerenter="handleMenuPointerEnter"
      @pointerleave="handleMenuPointerLeave"
    >
      <DropdownMenuGroup>
        <DropdownMenuSub v-model:open="agentMenuOpen">
          <DropdownMenuSubTrigger :disabled="agentDisabled">
            <BotIcon data-icon="inline-start" />
            <span class="min-w-0 flex-1 truncate">Agent</span>
            <DropdownMenuShortcut class="max-w-32 truncate text-right tracking-normal sm:max-w-40">
              {{ agentLabel }}
            </DropdownMenuShortcut>
          </DropdownMenuSubTrigger>

          <DropdownMenuSubContent
            :side-offset="6"
            class="flex max-h-(--reka-dropdown-menu-content-available-height) w-[min(calc(100vw-1rem),22rem)] max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-2xl"
            @pointerenter="handleMenuPointerEnter"
            @pointerleave="handleMenuPointerLeave"
          >
            <div
              data-agent-list
              class="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1"
            >
              <div
                v-if="loadingAgents"
                role="status"
                aria-live="polite"
                aria-label="正在加载 Agent"
                class="flex min-h-10 items-center justify-center rounded-xl px-3 py-2 text-sm text-muted-foreground"
              >
                <Spinner aria-hidden="true" />
              </div>

              <DropdownMenuRadioGroup
                :model-value="selectedAgent || DEFAULT_AGENT_VALUE"
                @update:model-value="selectAgent"
              >
                <DropdownMenuRadioItem
                  :value="DEFAULT_AGENT_VALUE"
                  :disabled="agentDisabled"
                  @select.prevent
                >
                  <BotIcon data-icon="inline-start" class="text-muted-foreground" />
                  <span class="min-w-0 truncate">{{ defaultAgentLabel }}</span>
                </DropdownMenuRadioItem>
                <DropdownMenuRadioItem
                  v-for="agent in agentOptions"
                  :key="agent.value"
                  :value="agent.value"
                  :disabled="agentDisabled"
                  @select.prevent
                >
                  <BotIcon data-icon="inline-start" class="text-muted-foreground" />
                  <span class="min-w-0 truncate">{{ agent.label }}</span>
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>

              <div
                v-if="!loadingAgents && agentOptions.length === 0"
                class="px-3 py-2 text-sm text-muted-foreground"
              >
                暂无可选 Agent
              </div>
            </div>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              class="shrink-0"
              :disabled="defaultAgentActionDisabled"
              @select="setDefaultAgent"
            >
              <Spinner
                v-if="savingDefaultAgent"
                data-icon="inline-start"
              />
              <StarIcon
                v-else
                data-icon="inline-start"
                :class="cn(selectedAgentIsUserDefault && 'fill-current')"
              />
              {{ defaultAgentActionLabel }}
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSub
          v-if="showPersonalMcp"
          v-model:open="mcpMenuOpen"
        >
          <DropdownMenuSubTrigger
            :disabled="mcpDisabled"
            :class="cn(
              !agentAllowsPersonalMcp && 'text-muted-foreground',
              !organizationAvailable && 'text-muted-foreground',
            )"
          >
            <LockKeyholeIcon
              v-if="mcpLocked"
              data-icon="inline-start"
            />
            <PlugZapIcon
              v-else
              data-icon="inline-start"
            />
            <span class="min-w-0 flex-1 truncate">MCP</span>
            <DropdownMenuShortcut class="max-w-36 truncate text-right tracking-normal sm:max-w-44">
              {{ mcpTriggerLabel }}
            </DropdownMenuShortcut>
          </DropdownMenuSubTrigger>

          <DropdownMenuSubContent
            :side-offset="6"
            class="max-h-(--reka-dropdown-menu-content-available-height) w-[min(calc(100vw-1rem),22rem)] max-w-[calc(100vw-1rem)] overflow-y-auto overscroll-contain rounded-2xl"
            @pointerenter="handleMenuPointerEnter"
            @pointerleave="handleMenuPointerLeave"
          >
            <div
              v-if="loadingMcp"
              role="status"
              aria-live="polite"
              aria-label="正在加载 MCP"
              class="flex min-h-10 items-center justify-center rounded-xl px-3 py-2 text-sm text-muted-foreground"
            >
              <Spinner aria-hidden="true" />
            </div>

            <div
              v-if="visibleServers.length > 0"
            >
              <DropdownMenuCheckboxItem
                v-for="server in visibleServers"
                :key="server.id"
                :model-value="isSelected(server.id)"
                :disabled="mcpSelectionDisabled"
                @select="handleMcpSelect($event, server.id)"
              >
                <PlugZapIcon data-icon="inline-start" class="text-muted-foreground" />
                <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ server.display_name }}</span>
              </DropdownMenuCheckboxItem>
            </div>

            <div
              v-else-if="!loadingMcp"
              class="px-3 py-3 text-center text-sm text-muted-foreground"
            >
              暂无可配置的 MCP
            </div>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuGroup>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
