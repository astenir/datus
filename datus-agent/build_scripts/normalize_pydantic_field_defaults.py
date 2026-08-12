#!/usr/bin/env python3
"""Rewrite positional Field(<literal>, ...) to Field(default=<literal>, ...).

Semantically identical for pydantic; avoids basedpyright mis-analysis of
positional defaults with additional kwargs (pydantic 2.12+ overloads).
Only touches datus/ and datus_enterprise/ source trees.

Provenance:
  - Generator: this script (one-shot migration, 2026-08)
  - Ran with: python3 build_scripts/normalize_pydantic_field_defaults.py
  - Scope: datus/ + datus_enterprise/ *.py under the datus-agent repo root
  - Manual follow-up after generation: reverted `FtsField(default=` rewrites
    back to `FtsField(` (tantivy's FtsField rejects the `default` kwarg);
    recorded as part of the same commit.
"""

import pathlib
import re
import sys

ROOTS = (
    pathlib.Path(__file__).resolve().parent.parent / "datus",
    pathlib.Path(__file__).resolve().parent.parent / "datus_enterprise",
)

# Single-line:  Field(None, / Field("", / Field(5, / Field([], / Field({}, / Field(True,
SINGLE = re.compile(r'Field\((?P<v>(?:None|True|False|"[^"\n]*"|\'[^\'\n]*\'|\[\]|\{\}|-?\d+(?:\.\d+)?)),')
# Multi-line:  Field(\n<indent><literal>,
MULTI = re.compile(
    r'Field\(\s*\n(?P<ind>\s*)(?P<v>(?:None|True|False|"[^"\n]*"|\'[^\'\n]*\'|\[\]|\{\}|-?\d+(?:\.\d+)?)),'
)


def rewrite(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    new = SINGLE.sub(lambda m: f"Field(default={m.group('v')},", text)
    new = MULTI.sub(lambda m: f"Field(\n{m.group('ind')}default={m.group('v')},", new)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return 1
    return 0


def main() -> int:
    changed = 0
    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            changed += rewrite(path)
    print(f"changed files: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
