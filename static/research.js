/* Public-source research UI. Tool traces are execution summaries, never hidden reasoning. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = {
    config: null,
    run: null,
    history: [],
    busy: false,
    posting: false,
    postingRevision: null,
    pollToken: 0,
    pollTimer: null,
    chatKey: "",
    questionKey: "",
    toastTimer: null,
  };
  const apiRoot = "/api/research";
  const icons = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    research:
      '<rect x="4" y="3" width="12" height="17" rx="2"/><path d="M8 7h4M8 11h3m7 6 3 3"/><circle cx="15.5" cy="14.5" r="3.5"/>',
    box: '<path d="m12 3 9 5-9 5-9-5 9-5ZM3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8l10-5Zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
    database:
      '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    spark:
      '<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3ZM20 2v4m-2-2h4"/>',
    route:
      '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h9a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h9"/>',
    file: '<path d="M14 2H5v20h14V7l-5-5ZM14 2v6h5M8 12h8M8 16h8"/>',
    bookmark: '<path d="M5 3h14v19l-7-5-7 5V3Z"/>',
    globe:
      '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    shield:
      '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z"/><path d="m8 12 3 3 5-6"/>',
    text: '<path d="M4 5h16M12 5v15M8 20h8"/>',
    arrow: '<path d="M12 20V4m-6 6 6-6 6 6"/>',
    alert: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    x: '<path d="m6 6 12 12M18 6 6 18"/>',
    menu: '<path d="M4 5h16M4 12h16M4 19h16"/>',
    link: '<path d="M14 3h7v7M21 3 10 14M10 3H3v18h18v-7"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    compare:
      '<path d="M8 3v18M16 3v18M4 7h8M12 17h8m-15 0 3 4 3-4m2-10 3-4 3 4"/>',
    message:
      '<path d="M21 16a2 2 0 0 1-2 2H8l-5 4V4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12Z"/>',
  };
  const icon = (name) =>
    `<span data-icon="${name}" aria-hidden="true"><svg viewBox="0 0 24 24">${icons[name] || icons.file}</svg></span>`;
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (ch) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[ch],
    );
  const statuses = {
    idle: "准备就绪",
    working: "正在查证",
    needs_input: "需要补充",
    completed: "查证完成",
    insufficient: "证据不足",
    error: "查证异常",
    limit_reached: "达到执行上限",
  };
  const toolNames = {
    search_catalog: "检索配件清单",
    search_bom: "检索配件清单",
    search_parts: "检索配件清单",
    search_documents: "检索公开资料",
    read_document: "查阅资料原文",
    get_part: "读取配件条目",
    read_part: "读取配件条目",
    get_part_details: "读取配件详情",
    compare_parts: "对比配件",
    inspect_part: "读取配件条目",
    ask_user: "澄清问题",
    clarify: "澄清问题",
    finish: "形成查证报告",
    finish_report: "形成查证报告",
    answer: "形成查证报告",
    decide: "选择查证动作",
    model: "模型决策",
  };
  const examples = [
    [
      "research",
      "送丝时咬住塑料丝往里推的那个带齿小轮，在这台机器的物料表里叫什么？我不知道英文术语，请查原文，不要仅靠常识回答。",
      "不知道英文术语？从用途出发继续查证",
    ],
    ["file", "X 轴和 Y 轴分别需要多少 LM8UU 轴承？", "核对清单中的装配数量"],
    [
      "message",
      "我想换个轴承，但不知道型号，应该先确认什么？",
      "信息不足时，先澄清再查证",
    ],
    [
      "compare",
      "能把 X 轴皮带直接替换成 Y 轴那条吗？",
      "区分规格相近与可直接替代",
    ],
  ];
  const formatTime = (value) => {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? ""
      : d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  };
  const formatDate = (value) => {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? ""
      : d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
  };
  const money = (value) =>
    Number.isFinite(Number(value)) ? Number(value).toFixed(4) : "—";
  const modeText = (mode) =>
    mode === "qwen" || mode === "live"
      ? "真实模型"
      : mode === "fixed_rag_qwen"
        ? "固定流程＋Qwen"
        : mode === "fixed" || mode === "baseline"
          ? "固定流程对照"
          : "离线规则演示";
  const isBusy = () => state.busy || state.run?.status === "working";
  const safeURL = (value) => {
    try {
      const u = new URL(String(value));
      return ["http:", "https:"].includes(u.protocol) ? u.href : null;
    } catch {
      return null;
    }
  };
  const sourceLink = (url, label) => {
    const safe = safeURL(url);
    return safe
      ? `<a class="source-link" href="${esc(safe)}" target="_blank" rel="noopener noreferrer">${esc(label || "查看公开原文")}${icon("link")}</a>`
      : `<span class="source-unavailable">${esc(label || "来源链接暂不可用")}</span>`;
  };
  function rememberedRun() {
    try {
      return localStorage.getItem("partpilot.research.run");
    } catch {
      return null;
    }
  }
  function rememberRun(id) {
    try {
      localStorage.setItem("partpilot.research.run", id);
    } catch {
      /* A private browser can disable persistence. Server history still works. */
    }
  }
  function showError(message) {
    $("error-text").textContent = message;
    $("error-banner").hidden = false;
  }
  function clearError() {
    $("error-banner").hidden = true;
  }
  function toast(message) {
    clearTimeout(state.toastTimer);
    $("toast").textContent = message;
    $("toast").hidden = false;
    state.toastTimer = setTimeout(() => {
      $("toast").hidden = true;
    }, 4500);
  }
  async function request(path, options = {}, timeout = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(apiRoot + path, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const raw = data?.detail;
        const error = new Error(
          typeof raw === "string"
            ? raw
            : `请求未完成（HTTP ${response.status}）`,
        );
        error.status = response.status;
        throw error;
      }
      if (!data) throw new Error("服务返回内容为空，请重新同步。");
      return data;
    } catch (error) {
      if (error.name === "AbortError")
        throw new Error(
          "请求等待超时。服务可能仍在执行，请重新同步当前查证，避免重复提交。",
        );
      if (error instanceof TypeError)
        throw new Error(
          "无法连接本地服务。请在项目文件夹双击 Start-PartPilot.cmd，保持启动窗口打开，然后点击“重新同步”。",
        );
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
  function renderConfig() {
    const c = state.config;
    if (!c) return;
    const mode = state.run?.mode || c.mode;
    const real = ["qwen", "live", "fixed_rag_qwen"].includes(mode);
    $("mode-badge").textContent = real
      ? `${modeText(mode)} · ${c.model || "Qwen"}`
      : modeText(mode);
    $("mode-badge").classList.toggle("real", real);
    $("data-count").textContent = `${c.part_count ?? "—"} 条配件`;
    $("data-caption").textContent =
      `${c.document_count ?? "—"} 份文档 · 公开资料`;
    const used = c.usage || {};
    $("usage-summary").textContent =
      `累计调用 ${used.calls ?? 0} 次 · 已记账 ¥${money(used.accounted_cny)} / 预算 ¥${Number(c.budget_cny || 0).toFixed(2)}`;
    $("usage-summary").title =
      "应用模型 API 用量。费用依据服务端账本，含预算预留时可能暂高于最终费用。";
    const sources = Array.isArray(c.sources) ? c.sources : [];
    $("source-count").textContent = `${sources.length} 个来源`;
    $("sources-list").innerHTML = sources.length
      ? sources
          .map(
            (s, i) =>
              `<article class="source-card"><span class="source-index">${String(i + 1).padStart(2, "0")}</span><div><h3>${esc(s.title || s.id)}</h3><p>许可：${esc(typeof s.license === "string" ? s.license : JSON.stringify(s.license || "未提供"))}</p>${sourceLink(s.url, "打开公开来源")}</div></article>`,
          )
          .join("")
      : '<p class="small-empty">服务尚未提供来源记录。</p>';
  }
  function syncControls() {
    const busy = isBusy();
    $("main").setAttribute("aria-busy", String(busy));
    $("new-run").disabled = busy;
    $("send-message").disabled =
      busy || !state.run || !$("message-input").value.trim();
    $("export-run").disabled = busy || !state.run;
    const canSave = Boolean(
      state.run?.answer &&
      ["completed", "insufficient"].includes(state.run.status),
    );
    $("save-report").disabled =
      busy || !canSave || Boolean(state.run?.saved_report);
    $("confirm-save").disabled = busy || !canSave;
    document
      .querySelectorAll(".history-item,.example-button,.question-option")
      .forEach((el) => {
        el.disabled = busy;
      });
    $("message-input").setAttribute("aria-describedby", "input-count");
    $("input-count").textContent = `${$("message-input").value.length} / 2000`;
  }
  function renderHistory() {
    $("history-count").textContent = state.history.length;
    $("history-list").innerHTML = state.history.length
      ? state.history
          .map(
            (item) =>
              `<button class="history-item${item.id === state.run?.id ? " selected" : ""}" data-run-id="${esc(item.id)}" ${isBusy() ? "disabled" : ""}>${icon("message")}<span class="history-copy"><strong>${esc(item.title || "新建查证")}</strong><small>${esc(formatDate(item.updated_at))} · ${esc(statuses[item.status] || item.status)}</small></span></button>`,
          )
          .join("")
      : '<p class="history-empty">查证记录将在这里保留。<br>随时恢复问题与原文证据。</p>';
  }
  function renderMessages() {
    const run = state.run;
    const messages = run?.messages || [];
    const working = run?.status === "working" || state.posting;
    const key = JSON.stringify([run?.id, messages, working]);
    if (key === state.chatKey) return;
    const box = $("message-list");
    const nearBottom =
      box.scrollHeight - box.scrollTop - box.clientHeight < 100;
    const first = !state.chatKey;
    state.chatKey = key;
    if (!messages.length && !working) {
      box.innerHTML = `<div class="welcome"><div class="welcome-orbit">${icon("research")}</div><h3>从一个具体问题开始</h3><p>查找配件清单、阅读装配资料、比较零件信息。证据不足时，助手会先补充查证或向你追问。</p><div class="example-label">试试这些问题</div><div class="example-list">${examples.map(([name, text, description], i) => `<button class="example-button" data-example="${i}">${icon(name)}<span class="example-text">${esc(text)}<small>${esc(description)}</small></span><span class="example-arrow">↗</span></button>`).join("")}</div></div>`;
    } else {
      box.innerHTML =
        messages
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map(
            (m) =>
              `<article class="message ${m.role === "user" ? "user" : "assistant"}"><span class="message-avatar" aria-hidden="true">${m.role === "user" ? "你" : "P"}</span><div class="message-body"><div class="message-meta"><span>${m.role === "user" ? "你的问题" : "PartPilot"}</span><time>${esc(formatTime(m.at))}</time></div><div class="message-text">${esc(m.content)}</div></div></article>`,
          )
          .join("") +
        (working
          ? '<div class="working-message"><span class="spinner" aria-hidden="true"></span><span>正在查阅资料与执行工具…<br>查证过程会随执行更新。</span></div>'
          : "");
    }
    if (nearBottom || first || working) box.scrollTop = box.scrollHeight;
  }
  function renderQuestion() {
    const q = state.run?.status === "needs_input" ? state.run.question : null;
    const key = JSON.stringify([state.run?.id, q]);
    if (state.questionKey === key) return;
    state.questionKey = key;
    $("question-box").hidden = !q;
    $("question-box").innerHTML = q
      ? `<p>${esc(q.text)}</p>${Array.isArray(q.options) && q.options.length ? `<div class="question-options">${q.options.map((opt, i) => `<button class="question-option" data-question-option="${i}">${esc(opt)}</button>`).join("")}</div>` : ""}`
      : "";
  }
  function renderTrace() {
    const trace = state.run?.trace || [];
    const open = new Set(
      Array.from(document.querySelectorAll(".trace-arguments[open]")).map(
        (el) => el.dataset.traceKey,
      ),
    );
    const working = state.run?.status === "working" || state.posting;
    $("trace-count").textContent = trace.length;
    $("live-label").classList.toggle("working", working);
    $("live-label").innerHTML =
      `<i></i>${working ? "执行中 · 自动更新" : trace.length ? "执行记录" : "等待问题"}`;
    $("trace-list").innerHTML = trace.length
      ? trace
          .map((item, i) => {
            const failed = [
              "error",
              "failed",
              "timeout",
              "rejected",
              "blocked",
            ].includes(item.status);
            const key = `${state.run.id}-${i}`;
            const args =
              item.arguments && Object.keys(item.arguments).length
                ? JSON.stringify(item.arguments, null, 2)
                : null;
            const timing =
              item.status === "running"
                ? "执行中"
                : [
                    failed ? "未完成" : "",
                    Number.isFinite(Number(item.elapsed_ms))
                      ? `工具 ${Number(item.elapsed_ms).toLocaleString("zh-CN")} ms`
                      : "",
                    Number.isFinite(Number(item.model_ms)) &&
                    item.model_ms !== null
                      ? `模型 ${(Number(item.model_ms) / 1000).toFixed(1)} s`
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" · ");
            return `<article class="trace-item${failed ? " error" : ""}"><span class="step-number">${failed ? "!" : esc(item.step || i + 1)}</span><div><h3><span>${esc(toolNames[item.tool] || item.tool || "执行步骤")}</span><span class="trace-time">${esc(timing)}</span></h3><p class="trace-summary">${esc(typeof item.summary === "string" ? item.summary : JSON.stringify(item.summary || ""))}</p>${args ? `<details class="trace-arguments" data-trace-key="${esc(key)}"${open.has(key) ? " open" : ""}><summary>${esc(item.tool)} · 查看工具参数</summary><pre>${esc(args)}</pre></details>` : ""}</div></article>`;
          })
          .join("")
      : `<div class="trace-empty">${icon("route")}<div><strong>${working ? "正在确定第一个查证动作" : "问题决定查证路径"}</strong><p>${working ? "工具开始执行后，这里会显示真实记录。" : "助手根据实际查询结果，决定继续查阅、对比或澄清。"}</p><div class="empty-steps"><span>问题</span>→<span>工具与证据</span>→<span>报告 / 追问</span></div></div></div>`;
  }
  function renderReport() {
    const run = state.run;
    const answer = run?.answer;
    $("report-actions").hidden = !answer;
    $("report-label").textContent = run?.saved_report
      ? "已保存到本地"
      : answer
        ? "当前查证结果"
        : run?.status === "working" || state.posting
          ? "查证进行中"
          : "等待证据";
    if (!answer) {
      let title = "结论将出现在这里",
        description = "发送问题后，查证报告会附上对应的原文引用与资料来源。",
        name = "file";
      if (run?.status === "working" || state.posting) {
        title = "正在收集查证依据";
        description = "可以展开工具参数，查看本轮实际执行的查询。";
      } else if (run?.status === "needs_input") {
        title = "补充信息后继续查证";
        description = "请在对话中回答当前追问，或点击给出的选项。";
        name = "message";
      } else if (run?.status === "error") {
        title = "本次查证未完成";
        description =
          "执行过程中发生异常，请查看对话和执行记录。重新提交问题会发起新的查证。";
        name = "alert";
      } else if (run?.status === "limit_reached") {
        title = "已达到本轮执行上限";
        description =
          "为控制重复调用和费用，执行已停止。可以缩小问题范围后继续。";
        name = "info";
      } else if (run?.status === "insufficient") {
        title = "当前资料不足以得出结论";
        description = "补充设备或零件型号，或提供更明确的查证目标后重试。";
        name = "info";
      }
      $("report-content").innerHTML =
        `<div class="report-empty${run?.status === "error" ? " error" : ""}"><span class="empty-symbol">${icon(name)}</span><strong>${title}</strong><p>${description}</p></div>`;
      return;
    }
    const claims = Array.isArray(answer.claims) ? answer.claims : [];
    const limitations = Array.isArray(answer.limitations)
      ? answer.limitations
      : [];
    const summaryLabel =
      answer.summary_origin === "deterministic_from_citations"
        ? "原文结构化汇总"
        : ["qwen", "live", "fixed_rag_qwen"].includes(
              run.mode || state.config?.mode,
            )
          ? "模型归纳 · 以原文为准"
          : "离线资料汇总";
    $("report-content").innerHTML =
      `<div class="report-kicker"><span>${summaryLabel}</span><span>${claims.length} 条原文引用</span></div><p class="report-summary">${esc(answer.summary)}</p>${claims.length ? `<div class="report-section-label">原文依据 · 点击来源可核对</div>${claims.map((claim, i) => `<article class="claim"><span class="claim-number">${i + 1}</span><div class="claim-body"><blockquote>${esc(claim.quote)}</blockquote>${sourceLink(claim.source_url, claim.title || claim.evidence_id || "公开原文")}</div></article>`).join("")}` : '<p class="small-empty">本轮未提供可引用的原文证据。</p>'}${limitations.length ? `<div class="limitations"><h3>${icon("info")}范围与待确认事项</h3><ul>${limitations.map((value) => `<li>${esc(value)}</li>`).join("")}</ul></div>` : ""}${Array.isArray(answer.part_ids) && answer.part_ids.length ? `<div class="part-tags" aria-label="关联配件标识">${answer.part_ids.map((id) => `<span>${esc(id)}</span>`).join("")}</div>` : ""}`;
    $("save-status").textContent = run.saved_report
      ? `已保存 · ${run.saved_report.id}`
      : "确认后保存本轮报告与证据";
    $("save-report").innerHTML = run.saved_report
      ? `${icon("check")}已保存`
      : `${icon("bookmark")}保存查证报告`;
  }
  function renderEvidence() {
    const evidence = state.run?.evidence || [];
    const open = new Set(
      Array.from(document.querySelectorAll(".evidence-card[open]")).map(
        (el) => el.dataset.evidenceKey,
      ),
    );
    $("evidence-count").textContent = evidence.length;
    $("evidence-list").innerHTML = evidence.length
      ? evidence
          .map(
            (item, i) =>
              `<details class="evidence-card" data-evidence-key="${esc(item.id)}"${open.has(String(item.id)) ? " open" : ""}><summary><span><span class="evidence-id">${esc(item.id || `E${i + 1}`)}</span>${esc(item.title || "资料片段")}</span></summary><div class="evidence-body"><pre>${esc(item.text)}</pre>${sourceLink(item.source_url, "核对原始来源")}</div></details>`,
          )
          .join("")
      : '<p class="small-empty">实际查询返回的资料片段将保留在这里，可展开核对。</p>';
  }
  function renderRun() {
    if (!state.run) {
      syncControls();
      return;
    }
    $("run-status").textContent =
      statuses[state.run.status] || state.run.status;
    $("run-status").className =
      `status-badge ${Object.hasOwn(statuses, state.run.status) ? state.run.status : ""}`;
    renderMessages();
    renderQuestion();
    renderTrace();
    renderReport();
    renderEvidence();
    renderConfig();
    syncControls();
  }
  function acceptRun(run) {
    state.run = run;
    rememberRun(run.id);
    renderRun();
  }
  async function refreshMetadata() {
    const results = await Promise.allSettled([
      request("/config"),
      request("/runs"),
    ]);
    if (results[0].status === "fulfilled") {
      state.config = results[0].value;
      renderConfig();
    }
    if (results[1].status === "fulfilled") {
      state.history = results[1].value.items || [];
      renderHistory();
    }
    const failed = results.find((result) => result.status === "rejected");
    if (failed) showError(`资料或历史尚未同步：${failed.reason.message}`);
  }
  function stopPolling() {
    ++state.pollToken;
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  function startPolling() {
    stopPolling();
    const token = state.pollToken,
      id = state.run?.id;
    if (!id) return;
    async function poll() {
      if (token !== state.pollToken) return;
      try {
        const snapshot = await request(`/runs/${encodeURIComponent(id)}`);
        if (token !== state.pollToken || state.run?.id !== id) return;
        // A delayed GET may still contain the previous revision before POST starts.
        // Never flash its old report during a newly submitted question.
        if (!state.posting || snapshot.revision > state.postingRevision) {
          acceptRun(snapshot);
        }
        if (!state.posting && snapshot.status !== "working") {
          stopPolling();
          state.busy = false;
          renderRun();
          await refreshMetadata();
          return;
        }
      } catch (error) {
        if (token !== state.pollToken) return;
        showError(`执行记录暂未更新：${error.message}`);
      }
      if (token === state.pollToken) state.pollTimer = setTimeout(poll, 1000);
    }
    state.pollTimer = setTimeout(poll, 1000);
  }
  function closeSidebar() {
    $("sidebar").classList.remove("open");
    $("sidebar-backdrop").hidden = true;
    $("menu-button").setAttribute("aria-expanded", "false");
  }
  async function loadRun(id) {
    if (isBusy()) return;
    state.busy = true;
    stopPolling();
    syncControls();
    clearError();
    try {
      acceptRun(await request(`/runs/${encodeURIComponent(id)}`));
      closeSidebar();
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      renderRun();
      renderHistory();
      if (state.run?.status === "working") startPolling();
    }
  }
  async function newRun() {
    if (isBusy()) return;
    stopPolling();
    state.busy = true;
    syncControls();
    clearError();
    try {
      acceptRun(await request("/runs", { method: "POST", body: "{}" }));
      $("message-input").value = "";
      closeSidebar();
      await refreshMetadata();
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      renderRun();
      $("message-input").focus();
    }
  }
  async function submit(message) {
    if (isBusy() || !state.run) return;
    const text = String(message || "").trim();
    if (!text) return;
    const id = state.run.id,
      revision = state.run.revision;
    const previousRun = state.run;
    state.busy = true;
    state.posting = true;
    state.postingRevision = revision;
    clearError();
    // Immediately remove a previous report from the view; the server remains authoritative.
    acceptRun({
      ...previousRun,
      status: "working",
      answer: null,
      evidence: [],
      trace: [],
      question: null,
      saved_report: null,
    });
    startPolling();
    try {
      const snapshot = await request(
        `/runs/${encodeURIComponent(id)}/turn`,
        {
          method: "POST",
          body: JSON.stringify({ message: text, expected_revision: revision }),
        },
        120000,
      );
      stopPolling();
      state.posting = false;
      acceptRun(snapshot);
      $("message-input").value = "";
    } catch (error) {
      stopPolling();
      state.posting = false;
      showError(error.message);
      try {
        acceptRun(await request(`/runs/${encodeURIComponent(id)}`));
      } catch {
        acceptRun({
          ...previousRun,
          status: "error",
          answer: null,
          evidence: [],
          trace: [],
          question: null,
          saved_report: null,
        });
      }
    } finally {
      state.posting = false;
      state.busy = false;
      renderRun();
      await refreshMetadata();
      if (state.run?.status === "working") startPolling();
      else $("message-input").focus();
    }
  }
  async function saveReport() {
    if (isBusy() || !state.run?.answer || state.run.saved_report) return;
    $("save-dialog").close();
    state.busy = true;
    syncControls();
    clearError();
    try {
      acceptRun(
        await request(`/runs/${encodeURIComponent(state.run.id)}/save`, {
          method: "POST",
          body: JSON.stringify({ expected_revision: state.run.revision }),
        }),
      );
      toast("查证报告已保存到本地工作区");
      await refreshMetadata();
    } catch (error) {
      showError(error.message);
      if (error.status === 409) {
        try {
          acceptRun(await request(`/runs/${encodeURIComponent(state.run.id)}`));
        } catch {
          /* Original failure remains visible. */
        }
      }
    } finally {
      state.busy = false;
      renderRun();
    }
  }
  async function exportRun() {
    if (isBusy() || !state.run) return;
    state.busy = true;
    syncControls();
    try {
      const exported = await request(
        `/runs/${encodeURIComponent(state.run.id)}/export`,
      );
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(exported, null, 2)], {
          type: "application/json;charset=utf-8",
        }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `partpilot-research-${String(state.run.id).replace(/[^a-zA-Z0-9_-]/g, "_")}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("查证记录已导出为 JSON");
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      syncControls();
    }
  }
  async function resync() {
    if (state.busy) return;
    clearError();
    state.busy = true;
    syncControls();
    try {
      if (state.run?.id)
        acceptRun(await request(`/runs/${encodeURIComponent(state.run.id)}`));
      else acceptRun(await request("/runs", { method: "POST", body: "{}" }));
      await refreshMetadata();
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      renderRun();
      if (state.run?.status === "working") startPolling();
    }
  }
  async function init() {
    document.querySelectorAll("[data-icon]").forEach((el) => {
      el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[el.dataset.icon] || icons.file}</svg>`;
    });
    $("message-form").addEventListener("submit", (event) => {
      event.preventDefault();
      submit($("message-input").value);
    });
    $("message-input").addEventListener("input", syncControls);
    $("message-input").addEventListener("keydown", (event) => {
      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.isComposing &&
        event.keyCode !== 229
      ) {
        event.preventDefault();
        submit($("message-input").value);
      }
    });
    $("new-run").addEventListener("click", newRun);
    $("export-run").addEventListener("click", exportRun);
    $("history-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-run-id]");
      if (button) loadRun(button.dataset.runId);
    });
    $("message-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-example]");
      if (button && !isBusy()) {
        const example = examples[Number(button.dataset.example)];
        if (example) {
          $("message-input").value = example[1];
          submit(example[1]);
        }
      }
    });
    $("question-box").addEventListener("click", (event) => {
      const button = event.target.closest("[data-question-option]");
      if (button && !isBusy()) {
        const option =
          state.run?.question?.options?.[Number(button.dataset.questionOption)];
        if (typeof option === "string") submit(option);
      }
    });
    $("save-report").addEventListener("click", () => {
      if (!isBusy() && state.run?.answer && !state.run.saved_report)
        $("save-dialog").showModal();
    });
    $("confirm-save").addEventListener("click", saveReport);
    ["cancel-save", "cancel-save-icon"].forEach((id) =>
      $(id).addEventListener("click", () => $("save-dialog").close()),
    );
    $("dismiss-error").addEventListener("click", clearError);
    $("retry-connection").addEventListener("click", resync);
    $("menu-button").addEventListener("click", () => {
      const open = !$("sidebar").classList.contains("open");
      $("sidebar").classList.toggle("open", open);
      $("sidebar-backdrop").hidden = !open;
      $("menu-button").setAttribute("aria-expanded", String(open));
    });
    $("sidebar-backdrop").addEventListener("click", closeSidebar);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeSidebar();
    });
    state.busy = true;
    syncControls();
    try {
      await refreshMetadata();
      const remembered = rememberedRun();
      if (remembered) {
        try {
          acceptRun(await request(`/runs/${encodeURIComponent(remembered)}`));
        } catch (error) {
          if (error.status !== 404) throw error;
        }
      }
      if (!state.run)
        acceptRun(await request("/runs", { method: "POST", body: "{}" }));
      await refreshMetadata();
    } catch (error) {
      showError(`未能连接查证工作区：${error.message}`);
      $("mode-badge").textContent = "连接尚未完成";
    } finally {
      state.busy = false;
      renderRun();
      renderHistory();
      if (state.run?.status === "working") startPolling();
    }
  }
  init();
})();
