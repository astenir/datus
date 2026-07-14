const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const {
  verifyQualityGate,
  verifyQualityGateEnvironment,
} = require("./verify-quality-gate.cjs");

test("accepts success for a relevant job", () => {
  assert.doesNotThrow(() =>
    verifyQualityGate({
      changesResult: "success",
      jobs: [{ name: "WEB", relevant: "true", result: "success" }],
    }),
  );
});

test("accepts skipped only for an irrelevant job", () => {
  assert.doesNotThrow(() =>
    verifyQualityGate({
      changesResult: "success",
      jobs: [{ name: "WEB", relevant: "false", result: "skipped" }],
    }),
  );
});

test("rejects every non-success changes result", () => {
  for (const changesResult of ["", "failure", "cancelled", "skipped"]) {
    assert.throws(
      () =>
        verifyQualityGate({
          changesResult,
          jobs: [{ name: "WEB", relevant: "true", result: "success" }],
        }),
      /changes job must be success/,
    );
  }
});

test("rejects skipped when a relevant job should have run", () => {
  assert.throws(
    () =>
      verifyQualityGate({
        changesResult: "success",
        jobs: [{ name: "WEB", relevant: "true", result: "skipped" }],
      }),
    /WEB must be success when relevant=true, got skipped/,
  );
});

test("rejects success when an irrelevant job should have been skipped", () => {
  assert.throws(
    () =>
      verifyQualityGate({
        changesResult: "success",
        jobs: [{ name: "WEB", relevant: "false", result: "success" }],
      }),
    /WEB must be skipped when relevant=false, got success/,
  );
});

test("rejects failed, cancelled, and empty job results", () => {
  for (const result of ["", "failure", "cancelled"]) {
    assert.throws(() =>
      verifyQualityGate({
        changesResult: "success",
        jobs: [{ name: "WEB", relevant: "true", result }],
      }),
    );
  }
});

test("rejects empty and unknown relevance values", () => {
  for (const relevant of ["", "yes", "True"]) {
    assert.throws(
      () =>
        verifyQualityGate({
          changesResult: "success",
          jobs: [{ name: "WEB", relevant, result: "success" }],
        }),
      /relevance must be true or false/,
    );
  }
});

test("rejects an empty job declaration", () => {
  assert.throws(
    () => verifyQualityGate({ changesResult: "success", jobs: [] }),
    /must declare at least one job/,
  );
});

test("validates multiple jobs from workflow-style environment variables", () => {
  assert.deepEqual(
    verifyQualityGateEnvironment({
      CHANGES_RESULT: "success",
      QUALITY_JOBS: "AGENT, DB_ADAPTERS, STORAGE_ADAPTERS, SEMANTIC_ADAPTER, METRICFLOW",
      AGENT_RELEVANT: "true",
      AGENT_RESULT: "success",
      DB_ADAPTERS_RELEVANT: "false",
      DB_ADAPTERS_RESULT: "skipped",
      STORAGE_ADAPTERS_RELEVANT: "true",
      STORAGE_ADAPTERS_RESULT: "success",
      SEMANTIC_ADAPTER_RELEVANT: "true",
      SEMANTIC_ADAPTER_RESULT: "success",
      METRICFLOW_RELEVANT: "false",
      METRICFLOW_RESULT: "skipped",
    }),
    ["AGENT", "DB_ADAPTERS", "STORAGE_ADAPTERS", "SEMANTIC_ADAPTER", "METRICFLOW"],
  );
});

test("fails closed when a workflow environment variable is missing", () => {
  assert.throws(
    () =>
      verifyQualityGateEnvironment({
        CHANGES_RESULT: "success",
        QUALITY_JOBS: "WEB",
        WEB_RESULT: "skipped",
      }),
    /WEB relevance must be true or false, got <empty>/,
  );
});

test("command-line entry point exits nonzero for an inconsistent gate", () => {
  const result = spawnSync(process.execPath, [require.resolve("./verify-quality-gate.cjs")], {
    encoding: "utf8",
    env: {
      CHANGES_RESULT: "success",
      QUALITY_JOBS: "WEB",
      WEB_RELEVANT: "true",
      WEB_RESULT: "skipped",
    },
  });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /WEB must be success when relevant=true, got skipped/);
});
