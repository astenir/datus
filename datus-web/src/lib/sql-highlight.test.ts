import { describe, expect, it } from "vitest";

import { highlightSql } from "./sql-highlight";

describe("highlightSql", () => {
  it("highlights SQL keywords, strings, numbers, identifiers, and comments", () => {
    const html = highlightSql("-- fund query\nSELECT \"name\", nav FROM funds WHERE nav > 1.2 AND type = 'bond'");

    expect(html).toContain('<span class="sqlToken sqlToken-comment">-- fund query</span>');
    expect(html).toContain('<span class="sqlToken sqlToken-keyword">SELECT</span>');
    expect(html).toContain('<span class="sqlToken sqlToken-identifier">&quot;name&quot;</span>');
    expect(html).toContain('<span class="sqlToken sqlToken-number">1.2</span>');
    expect(html).toContain('<span class="sqlToken sqlToken-string">&#039;bond&#039;</span>');
  });

  it("does not highlight keywords inside strings or comments", () => {
    const html = highlightSql("SELECT '-- FROM fake' AS note /* WHERE ignored */ FROM funds");

    expect(html).toContain('<span class="sqlToken sqlToken-string">&#039;-- FROM fake&#039;</span>');
    expect(html).toContain('<span class="sqlToken sqlToken-comment">/* WHERE ignored */</span>');
    expect(html).not.toContain('<span class="sqlToken sqlToken-keyword">fake</span>');
  });

  it("escapes HTML before rendering highlighted SQL", () => {
    const html = highlightSql("SELECT '<script>' AS tag FROM funds WHERE nav < 2");

    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).toContain('<span class="sqlToken sqlToken-operator">&lt;</span>');
  });
});
