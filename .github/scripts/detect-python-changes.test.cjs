const assert = require("node:assert/strict");
const test = require("node:test");

const { detectPythonChanges } = require("./detect-python-changes.cjs");

const ALL = { agent: true, db_adapters: true, storage_adapters: true };
const NONE = { agent: false, db_adapters: false, storage_adapters: false };

test("runs every project for non-pull-request events", () => {
  assert.deepEqual(detectPythonChanges("workflow_dispatch"), ALL);
  assert.deepEqual(detectPythonChanges("merge_group"), ALL);
});

test("skips every project for unrelated pull-request files", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [{ filename: "docs/README.md", status: "modified" }]),
    NONE,
  );
});

test("selects each project from its monorepo path prefix", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [{ filename: "datus-agent/datus/api/app.py" }]),
    { ...NONE, agent: true },
  );
  assert.deepEqual(
    detectPythonChanges("pull_request", [{ filename: "datus-db-adapters/uv.lock" }]),
    { ...NONE, db_adapters: true },
  );
  assert.deepEqual(
    detectPythonChanges("pull_request", [{ filename: "datus-storage-adapters/pyproject.toml" }]),
    { ...NONE, storage_adapters: true },
  );
});

test("does not match similar directory names", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [{ filename: "datus-agent-old/example.py" }]),
    NONE,
  );
});

test("runs every project when shared Python CI files change", () => {
  for (const filename of [
    ".github/workflows/python-quality.yml",
    ".github/scripts/detect-python-changes.cjs",
    ".github/scripts/detect-python-changes.test.cjs",
    ".github/scripts/verify-quality-gate.cjs",
    ".github/scripts/verify-quality-gate.test.cjs",
  ]) {
    assert.deepEqual(detectPythonChanges("pull_request", [{ filename }]), ALL);
  }

  assert.deepEqual(
    detectPythonChanges("pull_request", [
      {
        filename: ".github/workflows/python-quality-disabled.yml",
        previous_filename: ".github/workflows/python-quality.yml",
        status: "renamed",
      },
    ]),
    ALL,
  );
});

test("selects a project when one of its files is deleted", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [
      { filename: "datus-agent/datus/removed.py", status: "removed" },
    ]),
    { ...NONE, agent: true },
  );
});

test("checks the previous path when a file is renamed out of a project", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [
      {
        filename: "docs/moved.py",
        previous_filename: "datus-agent/datus/moved.py",
        status: "renamed",
      },
    ]),
    { ...NONE, agent: true },
  );
});

test("selects both projects when a file moves between them", () => {
  assert.deepEqual(
    detectPythonChanges("pull_request", [
      {
        filename: "datus-storage-adapters/shared.py",
        previous_filename: "datus-db-adapters/shared.py",
        status: "renamed",
      },
    ]),
    { agent: false, db_adapters: true, storage_adapters: true },
  );
});
