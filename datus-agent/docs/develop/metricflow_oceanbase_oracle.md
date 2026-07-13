# Releasing MetricFlow for OceanBase Oracle

This guide defines the repository and release boundary for the OceanBase
Oracle MetricFlow engine. The implementation spans separate packages and must
not be vendored into `datus-agent`.

## Repository boundary

The ownership chain is:

1. `datus-db-adapters/datus-oceanbase-oracle` owns JDBC connectivity, pooling,
   metadata, and parameterized DataFrame queries.
2. `Datus-ai/metricflow` owns the `oceanbase-oracle` dialect, engine capability
   profile, SQL renderer, bind conversion, dry-run behavior, and SQL client.
3. `Datus-ai/datus-semantic-adapter` owns the Datus semantic adapter and passes
   datasource configuration into MetricFlow.
4. `datus-agent` selects the runtime datasource, loads the semantic adapter,
   and gates publishing on successful semantic validation.

Keep these as sibling source checkouts during development and install them as
editable packages. Do not clone `datus-semantic-adapter` or MetricFlow inside
the Datus project, and do not copy their source into `datus-agent`.

## Initial support boundary

The initial profile is read-only. It covers adapter initialization, semantic
validation, dry runs, live metric reads, `SUM`, `COUNT`, common grouping,
Oracle day/week/month/quarter/year truncation, time subtraction, Oracle row
limiting, and JDBC bind parameters.

It does not cover MetricFlow-managed schema/table creation or deletion,
DataFrame writes, query cancellation, percentile capabilities, or a general
write-oriented MetricFlow workload. These methods must fail explicitly rather
than silently claiming support.

## Source-development setup

Use one virtual environment and install the package chain in editable mode.
Adjust paths for the checkout layout:

```bash
python -m pip install -e /path/to/datus/datus-db-adapters/datus-db-core
python -m pip install -e /path/to/datus/datus-db-adapters/datus-oceanbase-oracle
python -m pip install -e /path/to/metricflow
python -m pip install -e /path/to/datus-semantic-adapter/datus-semantic-core
python -m pip install -e /path/to/datus-semantic-adapter/datus-semantic-metricflow
```

Do not add local paths to release metadata or commit editable-install artifacts
or generated lock files from a sibling repository.

## Package release order

Publish in dependency order. The current candidate sequence is:

1. Publish `datus-oceanbase-oracle` `0.1.0` and confirm that the wheel is
   installable from the intended package index. Connector/J remains an
   external runtime file and is not embedded in the wheel.
2. Bump and publish `datus-metricflow` (candidate `0.2.8`). Only after step 1
   resolves from the package index, add a resolvable `oceanbase-oracle`
   optional extra or document the separate adapter install.
3. Bump and publish `datus-semantic-metricflow` (candidate `0.2.9`) with a
   minimum `datus-metricflow` version that contains the engine. Decide whether
   its OceanBase extra delegates to the MetricFlow extra; do not force the JDBC
   adapter onto users of other databases.
4. Update `datus-agent` dependency constraints and `uv.lock` only after all
   referenced artifacts resolve from the configured package index.

If another release consumes one of these version numbers, advance the version
while preserving this order. Never publish the semantic adapter first with an
unresolvable transitive dependency.

## Real-tenant acceptance gate

The public OceanBase CE Docker image is not a substitute for an Oracle-mode
tenant. Supply an existing tenant and a compatible Connector/J jar:

```bash
ADAPTERS_METRICFLOW_OCEANBASE_ORACLE=1 \
OCEANBASE_ORACLE_HOST=ob.example.com \
OCEANBASE_ORACLE_PORT=2883 \
OCEANBASE_ORACLE_USERNAME='app@tenant#cluster' \
OCEANBASE_ORACLE_PASSWORD='...' \
OCEANBASE_ORACLE_DATABASE=tenant \
OCEANBASE_ORACLE_SCHEMA=APP \
OCEANBASE_ORACLE_JAR_PATH=/opt/datus/jars/oceanbase-client.jar \
uv run pytest \
  tests/integration/adapters/test_semantic_metricflow_oceanbase_oracle.py -v
```

Before marking the profile production-ready, the run must prove:

- connection and schema context initialization;
- semantic validation;
- a zero-row dry run;
- live `SUM` and `COUNT` metric reads;
- time filtering and all declared truncation granularities;
- grouping and row limiting;
- ratio casting, full outer join capability, and the random function if those
  capabilities remain declared;
- bind parameters with strings, dates, repeated names, and comments;
- expected failures for write, cancellation, and percentile surfaces.

Archive the exact OceanBase version, Connector/J version, connection mode,
test command, and result with the release evidence. Unit and mocked tests are
required but are not sufficient for the production-ready label.
