const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const {
  validateWorkflow,
  validateWorkflowDirectory,
  validateWorkflowFiles,
} = require("./check-workflow-policy.cjs");

const POLICY = { contents: "read", "pull-requests": "read" };
const PINNED_SHA = "0123456789abcdef0123456789abcdef01234567";

function workflowWith(step, permissions = "permissions:\n  contents: read\n  pull-requests: read") {
  return `name: Test\non: pull_request\n${permissions}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - ${step}\n`;
}

test("current repository workflows satisfy the policy", () => {
  const workflowDirectory = path.resolve(__dirname, "../workflows");
  assert.deepEqual(validateWorkflowDirectory(workflowDirectory), []);
});

test("accepts full remote SHAs and local actions", () => {
  assert.deepEqual(
    validateWorkflow("test.yml", workflowWith(`uses: actions/example@${PINNED_SHA}`), POLICY),
    [],
  );
  assert.deepEqual(validateWorkflow("test.yml", workflowWith("uses: ./local-action"), POLICY), []);
  assert.deepEqual(
    validateWorkflow("test.yml", workflowWith(`uses: "actions/example@${PINNED_SHA}"`), POLICY),
    [],
  );
  assert.deepEqual(
    validateWorkflow(
      "test.yml",
      workflowWith(
        "run: true",
        "permissions:\n  pull-requests: read\n  contents: read",
      ),
      POLICY,
    ),
    [],
  );
});

test("rejects floating and short remote action references", () => {
  for (const reference of ["actions/checkout@v7", "actions/checkout@0123456789ab", "owner/action@main"]) {
    assert.match(
      validateWorkflow("test.yml", workflowWith(`uses: ${reference}`), POLICY).join("\n"),
      /must use a full 40-character SHA/,
    );
  }
});

test("requires an explicit top-level permission mapping", () => {
  assert.match(
    validateWorkflow("test.yml", workflowWith("run: true", ""), POLICY).join("\n"),
    /missing top-level permissions/,
  );
  assert.match(
    validateWorkflow("test.yml", workflowWith("run: true", "permissions: read-all"), POLICY).join(
      "\n",
    ),
    /must use an explicit mapping/,
  );
});

test("rejects write permissions and unexpected permission keys", () => {
  for (const permissions of [
    "permissions:\n  contents: write\n  pull-requests: read",
    "permissions:\n  contents: read\n  pull-requests: read\n  issues: read",
    "permissions:\n  contents: read",
  ]) {
    assert.match(
      validateWorkflow("test.yml", workflowWith("run: true", permissions), POLICY).join("\n"),
      /permissions must be/,
    );
  }
});

test("rejects job-level permission overrides", () => {
  const source = workflowWith("run: true").replace(
    "  test:\n    runs-on:",
    "  test:\n    permissions:\n      contents: write\n    runs-on:",
  );
  assert.match(validateWorkflow("test.yml", source, POLICY).join("\n"), /job-level permissions/);
});

test("title-check policy explicitly allows pull-requests write", () => {
  const workflows = {
    "title-check.yml": workflowWith(
      "run: true",
      "permissions:\n  contents: read\n  pull-requests: write",
    ),
  };
  assert.deepEqual(
    validateWorkflowFiles(workflows, {
      "title-check.yml": { contents: "read", "pull-requests": "write" },
    }),
    [],
  );
});

test("requires every workflow to have an explicit policy", () => {
  const workflows = {
    "known.yml": workflowWith("run: true"),
    "new.yml": workflowWith("run: true"),
  };
  assert.match(
    validateWorkflowFiles(workflows, { "known.yml": POLICY }).join("\n"),
    /new.yml: missing explicit permission policy/,
  );
});

test("rejects policies for missing workflows", () => {
  assert.match(
    validateWorkflowFiles({}, { "removed.yml": POLICY }).join("\n"),
    /removed.yml: permission policy references a missing workflow/,
  );
});
