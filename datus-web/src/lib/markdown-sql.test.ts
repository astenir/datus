import { describe, expect, it } from "vitest";

import { extractSqlCodeBlocks } from "./markdown-sql";

describe("extractSqlCodeBlocks", () => {
  it("extracts fenced SQL blocks", () => {
    expect(
      extractSqlCodeBlocks("```sql\nSELECT * FROM funds LIMIT 5;\n```")
    ).toEqual(["SELECT * FROM funds LIMIT 5;"]);
  });

  it("extracts unlabeled fences that look like SQL", () => {
    expect(
      extractSqlCodeBlocks("```\n-- fund query\nWITH latest AS (SELECT 1) SELECT * FROM latest;\n```")
    ).toEqual(["-- fund query\nWITH latest AS (SELECT 1) SELECT * FROM latest;"]);
  });

  it("ignores non-SQL fenced code", () => {
    expect(
      extractSqlCodeBlocks("```ts\nconst sql = 'SELECT 1';\n```")
    ).toEqual([]);
  });
});
