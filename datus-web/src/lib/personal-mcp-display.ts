/**
 * 个人 MCP 显示名解析。
 *
 * 个人 MCP 在运行时的服务别名是 `personal_<记录ID>`（见后端
 * `datus_enterprise/personal_mcp.py` 的 `personal_mcp_alias`），工具调用事件、
 * 连接失败摘要、权限请求里出现的都是这个别名。聊天展示需要把它还原为用户
 * 配置的 MCP 名称（display_name），否则工具卡片会直接显示数据 ID。
 *
 * 这里用模块级注册表保存当前会话上下文的「别名 → 显示名」映射，由
 * `usePersonalMcp` 在加载会话绑定 / 服务列表时填充（merge 语义，空列表不会
 * 清空已加载的映射），在会话或应用卸载时清空。解析函数保持纯函数签名，
 * 未命中时原样返回，便于在工具卡片、错误文案、权限请求等纯渲染路径复用。
 */

const ALIAS_PREFIX = "personal_";
const MCP_ID_PATTERN = /^[A-Fa-f0-9]{32}$/;
const ALIAS_PATTERN = /^personal_[A-Fa-f0-9]{32}$/;
const ALIAS_SEGMENT_PATTERN = /personal_[A-Fa-f0-9]{32}/g;

export type PersonalMcpDisplayNameEntry = {
  id: string;
  displayName: string;
};

let displayNames = new Map<string, string>();

export function setPersonalMcpDisplayNames(
  entries: readonly PersonalMcpDisplayNameEntry[],
): void {
  const next = new Map(displayNames);
  for (const entry of entries) {
    const id = entry.id.trim().toLowerCase();
    const displayName = entry.displayName.trim();
    if (!MCP_ID_PATTERN.test(id) || !displayName) continue;
    next.set(`${ALIAS_PREFIX}${id}`, displayName);
  }
  displayNames = next;
}

export function clearPersonalMcpDisplayNames(): void {
  displayNames = new Map();
}

export function personalMcpDisplayName(value: string): string | undefined {
  const alias = value.trim().toLowerCase();
  if (!ALIAS_PATTERN.test(alias)) return undefined;
  return displayNames.get(alias);
}

/** 把文本中出现的 `personal_<id>` 片段替换为已知的 MCP 名称，未命中保持不变。 */
export function resolvePersonalMcpDisplayName(value: string): string {
  if (!value || !value.includes(ALIAS_PREFIX)) return value;
  return value.replace(ALIAS_SEGMENT_PATTERN, (alias) => displayNames.get(alias) ?? alias);
}
