/* Real local API + Qwen, rendered in JSDOM. No actual browser/visual claim. */
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  base = process.env.PARTPILOT_TEST_URL || "http://127.0.0.1:8765";
if (!process.argv.includes("--live"))
  throw new Error(
    "This test calls the configured model. Pass --live only with authorized budget.",
  );
const checks = [],
  polls = [];
let dom,
  runId,
  exported = false,
  pending = 0;
function check(name, value) {
  assert.ok(value, name);
  checks.push({ name, passed: true });
}
async function waitFor(test, label, max = 100000) {
  const deadline = Date.now() + max;
  while (Date.now() < deadline) {
    if (test()) return;
    await new Promise((r) => setTimeout(r, 30));
  }
  throw Error("Timed out: " + label);
}
(async () => {
  let error;
  const before = await fetch(base + "/api/research/config").then((r) =>
    r.json(),
  );
  try {
    check(
      "live model enabled",
      before.mode === "qwen" && before.budget_cny > 0,
    );
    dom = new JSDOM(
      fs.readFileSync(path.join(root, "static/research.html"), "utf8"),
      {
        url: base + "/research",
        runScripts: "outside-only",
        pretendToBeVisual: true,
        virtualConsole: new VirtualConsole(),
      },
    );
    const w = dom.window,
      d = w.document,
      $ = (id) => d.getElementById(id);
    w.AbortController = global.AbortController;
    w.AbortSignal = global.AbortSignal;
    w.HTMLDialogElement.prototype.showModal = function () {
      this.open = true;
    };
    w.HTMLDialogElement.prototype.close = function () {
      this.open = false;
    };
    w.URL.createObjectURL = () => {
      exported = true;
      return "blob:partpilot-research-test";
    };
    w.URL.revokeObjectURL = () => {};
    w.fetch = async (url, options = {}) => {
      pending++;
      try {
        const r = await fetch(new URL(url, base), options);
        if (r.ok && String(url).includes("/runs")) {
          const body = await r.clone().json();
          if (body.id) {
            runId = body.id;
            if (!options.method)
              polls.push({
                status: body.status,
                trace: body.trace?.length || 0,
              });
          }
        }
        return r;
      } finally {
        pending--;
      }
    };
    w.eval(fs.readFileSync(path.join(root, "static/research.js"), "utf8"));
    await waitFor(
      () => runId && !$("new-run").disabled,
      "initialization",
      10000,
    );
    const taskId = runId;
    check(
      "real mode is shown",
      $("mode-badge").textContent.includes("qwen3.8-flash"),
    );
    check(
      "licensed public source visible",
      $("sources-list").textContent.includes("GPL"),
    );
    check("examples ready", d.querySelectorAll("[data-example]").length === 4);
    $("message-input").value =
      "Original Prusa MINI 的 X 轴和 Y 轴皮带规格一样吗？给出原文依据。";
    $("message-input").dispatchEvent(new w.Event("input", { bubbles: true }));
    $("message-form").dispatchEvent(
      new w.Event("submit", { bubbles: true, cancelable: true }),
    );
    check("busy prevents duplicate submit", $("send-message").disabled);
    await waitFor(
      () =>
        $("run-status").classList.contains("completed") &&
        !$("new-run").disabled,
      "live report",
    );
    check(
      "server was polled during actual work",
      polls.some((p) => p.status === "working" && p.trace > 0),
    );
    check(
      "actual tool trail rendered",
      $("trace-list").textContent.includes("检索") &&
        $("trace-list").textContent.includes("原文"),
    );
    check(
      "both belt specifications displayed",
      $("report-content").textContent.includes("561") &&
        $("report-content").textContent.includes("496"),
    );
    check(
      "summary provenance explicit",
      $("report-content")
        .querySelector(".report-kicker")
        .textContent.includes("原文结构化"),
    );
    const links = [...$("report-content").querySelectorAll("a")];
    check(
      "citations point to actual pinned source",
      links.length >= 2 &&
        links.every((a) =>
          a.href.includes(
            "github.com/prusa3d/Original-Prusa-MINI/blob/853bc30",
          ),
        ),
    );
    $("save-report").click();
    check("save requires confirmation", $("save-dialog").open);
    const unsaved = await fetch(base + `/api/research/runs/${taskId}`).then(
      (r) => r.json(),
    );
    check("dialog alone does not save", unsaved.saved_report === null);
    $("confirm-save").click();
    await waitFor(
      () =>
        $("save-status").textContent.includes("保存") && !$("new-run").disabled,
      "save report",
      10000,
    );
    const saved = await fetch(base + `/api/research/runs/${taskId}`).then((r) =>
      r.json(),
    );
    check("report actually persisted", !!saved.saved_report?.id);
    check("repeat save disabled", $("save-report").disabled);
    $("export-run").click();
    await waitFor(() => exported && !$("new-run").disabled, "export", 10000);
    check("JSON download generated", exported);
    $("new-run").click();
    await waitFor(
      () => runId !== taskId && !$("new-run").disabled,
      "new run",
      10000,
    );
    check("new run clears old report", $("report-actions").hidden);
    d.querySelector(`[data-run-id="${taskId}"]`).click();
    await waitFor(
      () =>
        runId === taskId &&
        $("run-status").classList.contains("completed") &&
        !$("new-run").disabled,
      "restore",
      10000,
    );
    check(
      "history restores saved report",
      $("save-status").textContent.includes("保存"),
    );
    check("old baseline accessible", !!d.querySelector('a[href="/baseline"]'));
    fs.writeFileSync(
      path.join(root, "artifacts/research-ui-dom-snapshot.html"),
      dom.serialize(),
    );
  } catch (e) {
    error = e;
    process.exitCode = 1;
    console.error(e.stack);
    if (dom)
      fs.writeFileSync(
        path.join(root, "artifacts/research-ui-dom-failure.html"),
        dom.serialize(),
      );
  } finally {
    await waitFor(() => pending === 0, "outstanding metadata requests", 10000);
    if (dom) dom.window.close();
    const after = await fetch(base + "/api/research/config").then((r) =>
      r.json(),
    );
    const report = {
      kind: "JSDOM + real local API + Qwen; not browser visual verification",
      passed: !error,
      checks,
      before: before.usage,
      after: after.usage,
      run_id: runId,
      error: error?.message || null,
      polls,
    };
    fs.writeFileSync(
      path.join(root, "artifacts/research-ui-live-report.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(
      JSON.stringify({
        passed: !error,
        checks: checks.length,
        error: error?.message || null,
        ledger: after.usage,
      }),
    );
  }
})();
