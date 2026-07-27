# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import csv
from io import StringIO
from typing import Any

from datus.utils.json_utils import json2csv
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def sanitize_sample_rows(sample_rows: str, *, max_cell_chars: int, max_chars: int) -> str:
    """Bound metadata samples and remove oversized cell contents before embedding."""
    text = str(sample_rows)
    try:
        rows = list(csv.reader(StringIO(text)))
    except csv.Error:
        if len(text) > max_cell_chars:
            return f"<DATUS_SAMPLE_ROWS_UNPARSEABLE original_chars={len(text)}>"[:max_chars]
        rows = []

    if not rows:
        sanitized = text
    else:
        changed = False
        for row in rows:
            for index, cell in enumerate(row):
                if len(cell) > max_cell_chars:
                    row[index] = f"<DATUS_SAMPLE_CELL_TRUNCATED chars={len(cell)}>"
                    changed = True
        if changed:
            output = StringIO()
            csv.writer(output, lineterminator="\n").writerows(rows)
            sanitized = output.getvalue()
        else:
            sanitized = text

    if len(sanitized) <= max_chars:
        return sanitized

    marker = f"\n<DATUS_SAMPLE_ROWS_TRUNCATED original_chars={len(text)}>"
    if len(marker) >= max_chars:
        return marker[:max_chars]
    return sanitized[: max_chars - len(marker)] + marker


def normalize_sample_rows_for_embedding(
    sample_rows: Any,
    *,
    table_name: str,
    max_cell_chars: int,
    max_chars: int,
) -> str:
    """Convert and sanitize one metadata sample before vector storage."""
    if isinstance(sample_rows, list):
        sample_rows = json2csv(sample_rows)
    sanitized = sanitize_sample_rows(
        sample_rows,
        max_cell_chars=max_cell_chars,
        max_chars=max_chars,
    )
    if sanitized != sample_rows:
        logger.info(
            "Sanitized metadata sample rows before embedding: table=%s, original_chars=%d, sanitized_chars=%d",
            table_name,
            len(sample_rows),
            len(sanitized),
        )
    return sanitized
