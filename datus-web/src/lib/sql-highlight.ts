const SQL_KEYWORDS = new Set([
  "ADD",
  "ALL",
  "ALTER",
  "AND",
  "AS",
  "ASC",
  "BETWEEN",
  "BY",
  "CASE",
  "CAST",
  "CREATE",
  "CROSS",
  "CURRENT_DATE",
  "CURRENT_TIMESTAMP",
  "DELETE",
  "DESC",
  "DISTINCT",
  "DROP",
  "ELSE",
  "END",
  "EXISTS",
  "FALSE",
  "FROM",
  "FULL",
  "GROUP",
  "HAVING",
  "IN",
  "INNER",
  "INSERT",
  "INTERVAL",
  "INTO",
  "IS",
  "JOIN",
  "LEFT",
  "LIKE",
  "LIMIT",
  "NOT",
  "NULL",
  "ON",
  "OR",
  "ORDER",
  "OUTER",
  "OVER",
  "PARTITION",
  "RIGHT",
  "ROW_NUMBER",
  "SELECT",
  "SET",
  "THEN",
  "TRUE",
  "UNION",
  "UPDATE",
  "VALUES",
  "WHEN",
  "WHERE",
  "WITH"
]);

export function highlightSql(sql: string): string {
  let index = 0;
  let html = "";

  while (index < sql.length) {
    const char = sql[index];
    const next = sql[index + 1];

    if (char === "-" && next === "-") {
      const end = sql.indexOf("\n", index + 2);
      const tokenEnd = end === -1 ? sql.length : end;
      html += wrapSqlToken("comment", sql.slice(index, tokenEnd));
      index = tokenEnd;
      continue;
    }

    if (char === "/" && next === "*") {
      const end = sql.indexOf("*/", index + 2);
      const tokenEnd = end === -1 ? sql.length : end + 2;
      html += wrapSqlToken("comment", sql.slice(index, tokenEnd));
      index = tokenEnd;
      continue;
    }

    if (char === "'") {
      const tokenEnd = readQuotedSqlString(sql, index);
      html += wrapSqlToken("string", sql.slice(index, tokenEnd));
      index = tokenEnd;
      continue;
    }

    if (char === '"' || char === "`" || char === "[") {
      const tokenEnd = readSqlIdentifier(sql, index);
      html += wrapSqlToken("identifier", sql.slice(index, tokenEnd));
      index = tokenEnd;
      continue;
    }

    if (isDigit(char)) {
      const tokenEnd = readSqlNumber(sql, index);
      html += wrapSqlToken("number", sql.slice(index, tokenEnd));
      index = tokenEnd;
      continue;
    }

    if (isWordStart(char)) {
      const tokenEnd = readSqlWord(sql, index);
      const token = sql.slice(index, tokenEnd);
      if (SQL_KEYWORDS.has(token.toUpperCase())) {
        html += wrapSqlToken("keyword", token);
      } else {
        html += escapeHtml(token);
      }
      index = tokenEnd;
      continue;
    }

    if (isOperator(char)) {
      html += wrapSqlToken("operator", char);
      index += 1;
      continue;
    }

    html += escapeHtml(char);
    index += 1;
  }

  return html;
}

function readQuotedSqlString(sql: string, start: number): number {
  let index = start + 1;
  while (index < sql.length) {
    if (sql[index] === "'" && sql[index + 1] === "'") {
      index += 2;
      continue;
    }
    if (sql[index] === "'") return index + 1;
    index += 1;
  }
  return sql.length;
}

function readSqlIdentifier(sql: string, start: number): number {
  const open = sql[start];
  const close = open === "[" ? "]" : open;
  let index = start + 1;
  while (index < sql.length) {
    if (sql[index] === close) return index + 1;
    index += 1;
  }
  return sql.length;
}

function readSqlNumber(sql: string, start: number): number {
  let index = start;
  while (index < sql.length && /[\d._]/.test(sql[index])) index += 1;
  return index;
}

function readSqlWord(sql: string, start: number): number {
  let index = start;
  while (index < sql.length && /[A-Za-z0-9_$]/.test(sql[index])) index += 1;
  return index;
}

function wrapSqlToken(kind: string, value: string): string {
  return `<span class="sqlToken sqlToken-${kind}">${escapeHtml(value)}</span>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function isWordStart(char: string): boolean {
  return /[A-Za-z_]/.test(char);
}

function isDigit(char: string): boolean {
  return /\d/.test(char);
}

function isOperator(char: string): boolean {
  return /[=<>+\-*/%,.;()]/.test(char);
}
