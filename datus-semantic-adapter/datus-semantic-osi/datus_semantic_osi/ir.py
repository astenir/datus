# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus Semantic IR.

A stable, backend-agnostic execution semantic model. The OSI compiler lowers
OSI authoring into these structures; backends lower these structures into their
own artifacts (e.g. MetricFlow YAML). The IR never depends on MetricFlow.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MetricKind(str, Enum):
    """The kind of a metric, independent of any execution backend."""

    AGGREGATE = "aggregate"
    EXPRESSION = "expression"
    RATIO = "ratio"
    CUMULATIVE = "cumulative"
    DERIVED = "derived"


class Aggregation(str, Enum):
    """Row-to-group aggregation functions the IR knows how to lower."""

    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"


class NonAdditiveDimensionIR(BaseModel):
    """Semi-additive semantics: a measure that does not sum over this dimension.

    ``window_choice`` (min|max) picks which row to keep along the dimension
    (e.g. an account balance: sum across accounts, but take the LAST value over
    time -> ``name: ds, window_choice: max``).
    """

    name: str
    window_choice: str = "max"  # min | max
    window_groupings: List[str] = Field(default_factory=list)


class MeasureIR(BaseModel):
    """A backing measure: a single aggregation over a row-level expression."""

    name: str
    agg: Aggregation
    expr: str
    description: str = ""
    non_additive_dimension: Optional[NonAdditiveDimensionIR] = None


class FieldIR(BaseModel):
    """A row-level scalar field on a dataset (no aggregation)."""

    name: str
    expr: str
    type: str = "categorical"  # categorical | time | numeric
    is_primary_time: bool = False
    time_granularity: Optional[str] = None
    description: str = ""


class IdentifierIR(BaseModel):
    """A primary / unique / foreign key used for joins and grain."""

    name: str
    type: str  # primary | unique | foreign
    expr: str


class DatasetIR(BaseModel):
    """A logical dataset backed by a table or a query."""

    name: str
    sql_table: Optional[str] = None
    sql_query: Optional[str] = None
    fields: List[FieldIR] = Field(default_factory=list)
    identifiers: List[IdentifierIR] = Field(default_factory=list)
    primary_time_dimension: Optional[str] = None


class MetricInputIR(BaseModel):
    """A reference to another metric used by a derived metric."""

    name: str
    alias: Optional[str] = None
    offset_window: Optional[str] = None


class PeriodOverPeriodIR(BaseModel):
    """Fixed period-over-period execution semantics for a metric."""

    time_grain: str
    offset_window: str
    calculation: str


class MetricIR(BaseModel):
    """A metric expressed over backing measures or other metrics."""

    name: str
    kind: MetricKind
    description: str = ""
    dataset: Optional[str] = None
    measures: List[MeasureIR] = Field(default_factory=list)
    inputs: List[MetricInputIR] = Field(default_factory=list)
    expression: Optional[str] = None
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    time_dimension: Optional[str] = None
    window: Optional[str] = None
    grain_to_date: Optional[str] = None
    offset_window: Optional[str] = None
    period_over_period: Optional[PeriodOverPeriodIR] = None
    format: Optional[str] = None
    unit: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)


class RelationshipIR(BaseModel):
    """A join path between two datasets (first version: many-to-one / one-to-one)."""

    name: str
    type: str  # many_to_one | one_to_one
    from_dataset: str
    from_identifier: str
    to_dataset: str
    to_identifier: str


class SemanticModelIR(BaseModel):
    """The root IR object for one executable semantic model."""

    name: str = "datus_semantic_model"
    datasets: List[DatasetIR] = Field(default_factory=list)
    relationships: List[RelationshipIR] = Field(default_factory=list)
    metrics: List[MetricIR] = Field(default_factory=list)
