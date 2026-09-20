/* JSDOM network failure/recovery check against the local API; no model calls. */
const { JSDOM } = require("jsdom");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const base = process.env.PARTPILOT_TEST_URL || "http://127.0.0.1:8765";
async function waitFor(test) {
  const deadline = Date.now() + 10000;
  while (!test()) {
    if (Date.now() > deadline) throw Error("Connection recovery timed out");
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}
(async () => {
  const before = await fetch(base + "/api/research/config").then((r) =>
    r.json(),
  );
  const dom = new JSDOM(
    fs.readFileSync(path.join(root, "static/research.html"), "utf8"),
    { url: base + "/", runScripts: "outside-only" },
  );
  const w = dom.window;
  const $ = (id) => w.document.getElementById(id);
  let offline = true;
  try {
    w.AbortController = global.AbortController;
    w.fetch = async (url, options) => {
      if (offline) throw new w.TypeError("Failed to fetch");
      assert.ok(!String(url).endsWith("/turn"), "No paid model turn");
      return fetch(new URL(url, base), options);
    };
    w.eval(fs.readFileSync(path.join(root, "static/research.js"), "utf8"));
    await waitFor(() => !$("new-run").disabled && !$("error-banner").hidden);
    assert.match($("error-text").textContent, /Start-PartPilot\.cmd/);
    assert.match($("error-text").textContent, /重新同步/);
    assert.ok($("send-message").disabled, "Cannot submit before connection");
    offline = false;
    $("retry-connection").click();
    await waitFor(
      () =>
        !$("new-run").disabled &&
        !!w.localStorage.getItem("partpilot.research.run"),
    );
    assert.ok($("error-banner").hidden, "Recovery clears connection error");
    assert.match($("data-count").textContent, /48/);
    assert.ok(!$("export-run").disabled, "Recovered session is usable");
    const after = await fetch(base + "/api/research/config").then((r) =>
      r.json(),
    );
    assert.deepEqual(after.usage, before.usage, "Recovery does not call model");
    console.log(
      "PASS: network failure guidance, retry with real local API, usable session, unchanged model ledger (JSDOM; not visual QA)",
    );
  } finally {
    dom.window.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
