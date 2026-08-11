/**
 * 新会话空态欢迎标题。
 *
 * 运行时从部署目录的 chat-welcome-title.txt 读取（UTF-8，取第一个非空行）。
 * 该文件由 Vite 构建时从 public/ 原样复制到 dist/ 根目录，因此部署后
 * 直接编辑部署目录里的文件即可生效，无需重新构建。
 *
 * - 文件不存在、读取失败或内容为空时，回退到内置默认标题。
 */

import { request } from "@/lib/request"

const WELCOME_TITLE_URL = `${import.meta.env.BASE_URL || "/"}chat-welcome-title.txt`

export const DEFAULT_WELCOME_TITLE = "有什么我能帮你的吗？";

/** 取文本的第一个非空行作为标题，没有有效行时返回空字符串。 */
export function parseWelcomeTitle(text: string): string {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return "";
}

// 静态资源请求，与后端 API 无关，但统一走 request 封装：
// 非 200（如文件缺失）会抛出 HttpError，由下方 catch 回退默认标题。
async function fetchWelcomeTitle(): Promise<string> {
  try {
    const response = await request(WELCOME_TITLE_URL, { cache: "no-cache" });
    const title = parseWelcomeTitle(await response.text());
    return title || DEFAULT_WELCOME_TITLE;
  } catch {
    return DEFAULT_WELCOME_TITLE;
  }
}

let cachePromise: Promise<string> | null = null;

/**
 * 加载欢迎标题（模块级缓存，只请求一次）。
 */
export function loadWelcomeTitle(): Promise<string> {
  cachePromise ??= fetchWelcomeTitle();
  return cachePromise;
}
