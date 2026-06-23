import { md } from "@/lib/markdown";

const SQL_FENCE_LANGUAGES = new Set([
  "sql",
  "postgresql",
  "mysql",
  "sqlite",
  "oracle",
  "plsql",
  "tsql",
]);

export function extractSqlCodeBlocks(markdown: string): string[] {
  return md
    .parse(markdown, {})
    .filter((token) => token.type === "fence")
    .map((token) => {
      const language = token.info.trim().split(/\s+/, 1)[0]?.toLowerCase() ?? "";
      const content = token.content.trim();
      if (!content) return null;
      if (SQL_FENCE_LANGUAGES.has(language) || (!language && looksLikeSqlSnippet(content))) {
        return content;
      }
      return null;
    })
    .filter((content): content is string => Boolean(content));
}

function looksLikeSqlSnippet(content: string): boolean {
  const normalized = content
    .replace(/^\s*(?:--[^\n]*|\/\*[\s\S]*?\*\/)\s*/g, "")
    .trimStart();
  return /^(select|with|insert|update|delete|create|alter|drop|explain)\b/i.test(normalized);
}
