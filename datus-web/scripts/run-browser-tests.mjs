import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = "4187";
const baseUrl = `http://${host}:${port}`;
const startupTimeoutMs = 90_000;
const viteCli = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const playwrightCli = fileURLToPath(new URL("../node_modules/playwright/cli.js", import.meta.url));

function waitForVite(server) {
  return new Promise((resolve, reject) => {
    let output = "";
    let probeTimer;
    let settled = false;
    const timeout = setTimeout(
      () => finish(reject, new Error(`Timed out while starting the browser test server\n${output}`)),
      startupTimeoutMs,
    );

    function finish(callback, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      clearTimeout(probeTimer);
      server.stdout.off("data", handleOutput);
      server.stderr.off("data", handleOutput);
      server.off("exit", handleExit);
      callback(value);
    }

    function handleOutput(chunk) {
      output += chunk.toString();
    }

    function handleExit(code) {
      finish(reject, new Error(`Browser test server exited before startup with code ${code ?? "unknown"}\n${output}`));
    }

    async function probe() {
      try {
        const response = await fetch(baseUrl, { signal: AbortSignal.timeout(2_000) });
        if (response.ok) {
          finish(resolve);
          return;
        }
      } catch {
        // The server is still starting.
      }
      if (!settled) probeTimer = setTimeout(probe, 250);
    }

    server.stdout.on("data", handleOutput);
    server.stderr.on("data", handleOutput);
    server.on("exit", handleExit);
    void probe();
  });
}

function waitForExit(child) {
  return new Promise(resolve => child.once("exit", code => resolve(code ?? 1)));
}

const server = spawn(process.execPath, [viteCli, "--host", host, "--port", port, "--strictPort"], {
  stdio: ["ignore", "pipe", "pipe"],
});

try {
  await waitForVite(server);
  const tests = spawn(process.execPath, [playwrightCli, "test"], {
    env: { ...process.env, DATUS_BROWSER_TEST_URL: baseUrl },
    stdio: "inherit",
  });
  process.exitCode = await waitForExit(tests);
} finally {
  server.kill("SIGTERM");
}
