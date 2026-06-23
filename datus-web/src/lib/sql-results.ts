function sanitizePythonRepr(raw: string): string {
  let s = raw.trim();
  const chars = [...s];
  const out: string[] = [];
  let i = 0;

  while (i < chars.length) {
    const ch = chars[i];
    if (ch === "'") {
      out.push('"');
      i++;
      while (i < chars.length) {
        if (chars[i] === "\\" && i + 1 < chars.length) {
          out.push(chars[i], chars[i + 1]);
          i += 2;
        } else if (chars[i] === "'") {
          out.push('"');
          i++;
          break;
        } else {
          out.push(chars[i] === '"' ? '\\"' : chars[i]);
          i++;
        }
      }
    } else {
      out.push(ch);
      i++;
    }
  }

  s = out.join("");
  return s
    .replace(/\bNone\b/g, "null")
    .replace(/\bTrue\b/g, "true")
    .replace(/\bFalse\b/g, "false")
    .replace(/\bDecimal\("([^"]*)"\)/g, '"$1"');
}

function isRecordArray(value: unknown): value is Array<Record<string, unknown>> {
  return Array.isArray(value) && value.every((item) => item !== null && typeof item === "object" && !Array.isArray(item));
}

export function parseSqlReturnRows(raw?: string): Array<Record<string, unknown>> {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return isRecordArray(parsed) ? parsed : [];
  } catch {
    try {
      const parsed = JSON.parse(sanitizePythonRepr(raw));
      return isRecordArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
}

export function displaySqlCellValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
