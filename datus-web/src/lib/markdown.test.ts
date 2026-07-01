import { describe, expect, it } from "vitest";

import { md } from "./markdown";

describe("markdown renderer", () => {
  it("does not render unsafe absolute URI schemes as links", () => {
    expect(md.render("[bad](javascript://alert(1))")).not.toContain("<a ");
    expect(md.render("[bad](ftp://example.com/file.txt)")).not.toContain("<a ");
  });

  it("renders allowed links with external navigation protections", () => {
    expect(md.render("[ok](https://example.com)")).toContain('href="https://example.com"');
    expect(md.render("[ok](https://example.com)")).toContain('target="_blank"');
    expect(md.render("[ok](https://example.com)")).toContain('rel="noreferrer"');
  });
});
