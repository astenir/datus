import { describe, expect, it } from "vitest";

import {
  datasourceGrantAllowsCatalog,
  mergeSelectOptions,
} from "./workspace-datasource-policy";

describe("workspace datasource policy", () => {
  it("merges datasource options without duplicate values", () => {
    expect(mergeSelectOptions(
      [
        { value: "fund", label: "Fund" },
        { value: "", label: "Empty" },
      ],
      [
        { value: "fund", label: "Duplicate" },
        { value: "demo", label: "Demo" },
      ],
    )).toEqual([
      { value: "fund", label: "Fund" },
      { value: "demo", label: "Demo" },
    ]);
  });

  it("allows catalog access for the legacy boolean grant", () => {
    expect(datasourceGrantAllowsCatalog(true)).toBe(true);
    expect(datasourceGrantAllowsCatalog(false)).toBe(false);
  });

  it("defaults structured grants to allow catalog access", () => {
    expect(datasourceGrantAllowsCatalog({ effect: "allow" })).toBe(true);
    expect(datasourceGrantAllowsCatalog({})).toBe(true);
    expect(datasourceGrantAllowsCatalog({ effect: "ALLOW", allow_catalog: true })).toBe(true);
  });

  it("rejects denied or malformed catalog grants", () => {
    expect(datasourceGrantAllowsCatalog({ effect: "deny" })).toBe(false);
    expect(datasourceGrantAllowsCatalog({ effect: "allow", allow_catalog: false })).toBe(false);
    expect(datasourceGrantAllowsCatalog(null)).toBe(false);
    expect(datasourceGrantAllowsCatalog([])).toBe(false);
  });
});
