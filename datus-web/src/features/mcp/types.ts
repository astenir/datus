export type McpScope = "public" | "personal"

export interface McpServerListItem {
  id: string
  name: string
  target: string
  transport: string
  authLabel?: string
  statusLabel?: string
  connectionLabel?: string
}

export interface McpDetailField {
  label: string
  value: string
  monospace?: boolean
}

export interface McpServerDetailModel {
  name: string
  target: string
  badges: readonly string[]
  fields: readonly McpDetailField[]
}

export interface McpToolView {
  name: string
  description?: string | null
}
