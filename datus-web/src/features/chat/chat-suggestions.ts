/**
 * 新会话开屏建议语句。
 *
 * 运行时从部署目录的 chat-suggestions.txt 读取（UTF-8，每行一句）。
 * 该文件由 Vite 构建时从 public/ 原样复制到 dist/ 根目录，因此部署后
 * 直接编辑部署目录里的文件即可生效，无需重新构建。
 *
 * - 文件不存在或读取失败时，回退到内置默认文案。
 * - 文件存在但没有任何有效行时，不展示任何建议语句。
 * - 空行、重复行会被自动过滤。
 */

import { request } from "@/lib/request"

const SUGGESTIONS_URL = `${import.meta.env.BASE_URL || "/"}chat-suggestions.txt`

export const DEFAULT_CHAT_SUGGESTIONS: readonly string[] = [
  "帮我分析基金持仓的关键变化",
  "列出当前数据源有哪些表",
  "运行 SQL 查询近 10 条记录",
  "查看 MCP 工具连接状态",
  "生成一份数据质量检查思路",
  "帮我总结这个会话的重点",
];

/** 按行解析文本内容，过滤空行与重复项。 */
export function parseChatSuggestions(text: string): readonly string[] {
  const suggestions: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || suggestions.includes(trimmed)) continue;
    suggestions.push(trimmed);
  }
  return suggestions;
}

// 静态资源请求，与后端 API 无关，但统一走 request 封装：
// 非 200（如文件缺失）会抛出 HttpError，由下方 catch 回退默认文案。
async function fetchSuggestions(): Promise<readonly string[]> {
  try {
    const response = await request(SUGGESTIONS_URL, { cache: "no-cache" });
    return parseChatSuggestions(await response.text());
  } catch {
    return DEFAULT_CHAT_SUGGESTIONS;
  }
}

let cachePromise: Promise<readonly string[]> | null = null;

/**
 * 加载建议语句（模块级缓存，只请求一次）。
 */
export function loadChatSuggestions(): Promise<readonly string[]> {
  cachePromise ??= fetchSuggestions();
  return cachePromise;
}
