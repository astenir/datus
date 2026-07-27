# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""File-level authoring for MetricFlow metrics.

The MetricFlow ``subject/semantic_models`` YAML files are the source of truth.
A metric is a top-level ``metric:`` document; its subject-tree categorization is
carried in ``locked_metadata.tags`` as ``subject_tree: a/b/c``. These helpers
read/mutate one metric while leaving the rest of the file untouched, keeping the
backend's historical MetricFlow contract (``{metric: {...}}``) intact.

Backend/editor surface only — not wired into the agent tool registry; see
``datus_semantic_core.authoring``.
"""

from __future__ import annotations

import glob
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from typing import Any, List, Optional

import yaml

from datus_semantic_core.authoring import MetricMutationResult, MetricSource
from datus_semantic_core.models import ValidationIssue, ValidationResult

FORMAT = "metricflow"

# Safe metric name for use as a filename on create: alphanumerics plus _.- ,
# never a path separator or traversal component (must start alnum/underscore, so
# ".." and "." are rejected).
_SAFE_METRIC_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


@dataclass
class _MetricLocation:
    file_path: str
    docs: List[Any]
    doc_index: int  # index of the {metric: ...} document within the file

    @property
    def node(self) -> dict:
        return self.docs[self.doc_index]["metric"]


def _yaml_files(root: str) -> List[str]:
    return sorted(
        glob.glob(os.path.join(root, "**", "*.yaml"), recursive=True)
        + glob.glob(os.path.join(root, "**", "*.yml"), recursive=True)
    )


def _read_docs(file_path: str) -> List[Any]:
    with open(file_path, encoding="utf-8") as fh:
        return list(yaml.safe_load_all(fh.read())) or []


def _dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _set_subject_tree_tag(node: dict, subject_path: List[str]) -> None:
    value = f"subject_tree: {'/'.join(subject_path)}"
    locked = node.setdefault("locked_metadata", {})
    tags = locked.setdefault("tags", [])
    for i, tag in enumerate(tags):
        if isinstance(tag, str) and tag.startswith("subject_tree:"):
            tags[i] = value
            return
    tags.append(value)


class MetricFlowMetricAuthor:
    """Read/write/delete/validate a single MetricFlow metric in its source file.

    Assumes a single writer: the read-modify-write cycle is not file-locked, so
    concurrent writes to the same file can lose updates. Callers that allow
    concurrent authoring must serialize it upstream.
    """

    def __init__(self, model_path: str):
        self._root = model_path

    def _require_root(self) -> str:
        if not self._root or not os.path.isdir(self._root):
            raise FileNotFoundError(f"model path is not a directory: {self._root}")
        return self._root

    def _locate(self, metric_name: str) -> Optional[_MetricLocation]:
        for file_path in _yaml_files(self._require_root()):
            try:
                docs = _read_docs(file_path)
            except yaml.YAMLError:
                continue
            for doc_index, doc in enumerate(docs):
                if isinstance(doc, dict) and isinstance(doc.get("metric"), dict):
                    if doc["metric"].get("name") == metric_name:
                        return _MetricLocation(file_path, docs, doc_index)
        return None

    # ---- read -----------------------------------------------------------

    def read(self, metric_name: str) -> MetricSource:
        loc = self._locate(metric_name)
        if loc is None:
            raise FileNotFoundError(f"Metric `{metric_name}` was not found in {self._root}.")
        return MetricSource(
            name=metric_name,
            format=FORMAT,
            text=_dump_yaml({"metric": loc.node}),
            file_path=loc.file_path,
        )

    # ---- write ----------------------------------------------------------

    @staticmethod
    def _parse_node(source: str) -> dict:
        try:
            doc = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML: {exc}") from exc
        node = doc.get("metric") if isinstance(doc, dict) and "metric" in doc else doc
        if not isinstance(node, dict) or not node.get("name"):
            raise ValueError("Metric source must contain a `metric:` mapping with a `name`.")
        return node

    def write(
        self,
        metric_name: str,
        source: str,
        *,
        subject_path: Optional[List[str]] = None,
        create: bool = False,
    ) -> MetricMutationResult:
        node = self._parse_node(source)
        # Validate before touching the file, using the same checks as validate().
        errors = self._node_errors(node, metric_name)
        if errors:
            raise ValueError("; ".join(errors))
        if subject_path is not None:
            _set_subject_tree_tag(node, list(subject_path))

        existing = self._locate(metric_name)
        if create and existing is not None:
            raise ValueError(f"Metric `{metric_name}` already exists at {existing.file_path}.")
        if not create and existing is None:
            raise ValueError(f"Metric `{metric_name}` does not exist; use create=True.")

        if existing is not None:
            existing.docs[existing.doc_index] = {"metric": node}
            _atomic_write(existing.file_path, existing.docs)
            file_path = existing.file_path
        else:
            # The new file is named after the metric; reject names that could
            # escape metrics_dir (path separators, traversal).
            if not _SAFE_METRIC_NAME.match(metric_name):
                raise ValueError(f"Unsafe metric name for file creation: {metric_name!r}")
            metrics_dir = os.path.join(self._require_root(), "metrics")
            os.makedirs(metrics_dir, exist_ok=True)
            file_path = os.path.join(metrics_dir, f"{metric_name}.yml")
            if os.path.exists(file_path):
                raise FileExistsError(f"File already exists: {file_path}")
            _atomic_write(file_path, [{"metric": node}])

        return MetricMutationResult(
            name=metric_name,
            format=FORMAT,
            file_path=file_path,
            created=create,
            affected_paths=[file_path],
        )

    # ---- delete ---------------------------------------------------------

    def delete(self, metric_name: str) -> MetricMutationResult:
        loc = self._locate(metric_name)
        if loc is None:
            raise FileNotFoundError(f"Metric `{metric_name}` was not found in {self._root}.")
        del loc.docs[loc.doc_index]
        # Drop empty (``None``) documents that leading/trailing ``---`` produce,
        # so we never write a literal ``null`` doc back to the file.
        remaining = [doc for doc in loc.docs if doc]
        if remaining:
            _atomic_write(loc.file_path, remaining)
        else:
            os.remove(loc.file_path)  # file held only this metric
        return MetricMutationResult(
            name=metric_name,
            format=FORMAT,
            file_path=loc.file_path,
            deleted=True,
            affected_paths=[loc.file_path],
        )

    # ---- validate -------------------------------------------------------

    @staticmethod
    def _node_errors(node: dict, metric_name: Optional[str]) -> List[str]:
        """Required-field checks shared by validate() and write()."""
        errors: List[str] = []
        if metric_name and node.get("name") != metric_name:
            errors.append(f"Metric name `{node.get('name')}` does not match `{metric_name}`.")
        if not node.get("type"):
            errors.append("Metric is missing required field `type`.")
        return errors

    def validate(self, source: str, *, metric_name: Optional[str] = None) -> ValidationResult:
        try:
            node = self._parse_node(source)
        except ValueError as exc:
            return ValidationResult(
                valid=False, issues=[ValidationIssue(severity="error", message=str(exc))]
            )
        issues = [
            ValidationIssue(severity="error", message=msg)
            for msg in self._node_errors(node, metric_name)
        ]
        return ValidationResult(valid=not any(i.severity == "error" for i in issues), issues=issues)


def _atomic_write(file_path: str, docs: List[Any]) -> None:
    directory = os.path.dirname(file_path) or "."
    payload = yaml.safe_dump_all(
        docs, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    # Preserve the existing file's permission bits; mkstemp creates 0600, which
    # would otherwise strip group/other read access on first edit.
    mode = stat.S_IMODE(os.stat(file_path).st_mode) if os.path.exists(file_path) else 0o644
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, file_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
