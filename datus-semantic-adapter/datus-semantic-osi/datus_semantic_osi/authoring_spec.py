# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""OSI core authoring specification text for LLM prompts.

The upstream spec document is vendored next to the JSON schema under the same
version so both ship from one package and cannot drift. ``authoring_spec_text``
renders the prompt-facing form: license header stripped, the dialect enum
collapsed to the single dialect this deployment executes, and the Datus
execution-subset notes appended.
"""

from __future__ import annotations

import re
from importlib import resources

from datus_semantic_osi.profile import CORE_SCHEMA_VERSION

_SPEC_RESOURCE = f"osi-core-{CORE_SCHEMA_VERSION}.spec.yaml"
_SPEC_TITLE_MARKER = "# Apache Ossie - Core Metadata Spec"

_DIALECTS_BLOCK_RE = re.compile(
    r"(# Supported expression language dialects\ndialects:\n)(?:  - \"[^\"]+\"[^\n]*\n)+",
)

_SUBSET_NOTES = """\

---
# Datus execution subset notes
# The Datus OSI compiler executes the spec above with these constraints:
#
# 1. Expression dialect: every `expression.dialects[].dialect` must be
#    `{dialect}` (the active datasource's dialect); other dialects are not
#    executed in this deployment.
# 2. Relationships: `from_columns` / `to_columns` support exactly one column
#    each. Composite join keys are rejected with a validation error.
# 3. One element name maps to one element type (key / time / dimension)
#    model-wide after compilation; the validator reports conflicts with the
#    structural fix.
# 4. Datus execution hints the spec has no core field for go into
#    `custom_extensions: [{{vendor_name: DATUS, data: '<JSON>'}}]`:
#    field `time_granularity`; dataset `source_type: "query"`; metric
#    `time_dimension`, `window`, `grain_to_date`, `offset_window`,
#    `window_aggregation`, `period_over_period`, `metric_kind`, `inputs`,
#    `numerator`, `denominator`, `subject_path`, `format`, `unit`.
"""


def authoring_spec_text(dialect: str) -> str:
    """Render the vendored OSI core spec for prompt injection."""
    raw = (
        resources.files("datus_semantic_osi.schema")
        .joinpath(_SPEC_RESOURCE)
        .read_text(encoding="utf-8")
    )
    title_at = raw.find(_SPEC_TITLE_MARKER)
    if title_at >= 0:
        raw = raw[title_at:]
    replacement = (
        "# Supported expression language dialects\n"
        "dialects:\n"
        f'  - "{dialect}"              # the only dialect executed in this deployment\n'
    )
    raw = _DIALECTS_BLOCK_RE.sub(replacement, raw, count=1)
    return raw + _SUBSET_NOTES.format(dialect=dialect)
