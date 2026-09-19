/* PartPilot UI: server snapshots are authoritative; no client-generated business results. */
"use strict";
const icons = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v4h16v-4"/>',
  database:
    '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  sparkles:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3zM20 2v4m-2-2h4"/>',
  text: '<path d="M4 5h16M12 5v14M8 19h8"/>',
  "arrow-up": '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  "arrow-right": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  sliders:
    '<path d="M4 6h5m4 0h7M4 12h9m4 0h3M4 18h2m4 0h10"/><circle cx="11" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  edit: '<path d="m16 3 5 5-12 12-6 1 1-6L16 3zM14 5l5 5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  box: '<path d="m12 3 9 5v9l-9 5-9-5V8l9-5zM3 8l9 5 9-5M12 13v9M7.5 5.5l9 5"/>',
  route:
    '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M6 7v9a3 3 0 0 0 3 3h7M18 17V8a3 3 0 0 0-3-3h-3m0 0 2-2m-2 2 2 2"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3zM8 12l3 3 5-6"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  message:
    '<path d="M21 14a3 3 0 0 1-3 3H8l-5 4V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8z"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="m12 3 10 18H2L12 3zM12 9v5m0 3h.01"/>',
  refresh:
    '<path d="M20 7v5h-5M4 17v-5h5M5.5 7A7 7 0 0 1 19 8m-14 8a7 7 0 0 0 13.5 1"/>',
  equipment:
    '<path d="M3 16h7l3-7h5l3 7v4H3v-4zM13 9V4h5v5M5 16v-4h5m-4 8v1m12-1v1"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.01"/>',
  filter: '<path d="M3 4h18l-7 8v7l-4 2v-9L3 4z"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.box}</svg>`;
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const $ = (id) => document.getElementById(id);
const statusLabels = {
  collecting: "补充信息",
  ready: "待启动检索",
  results: "候选已就绪",
  no_results: "暂无匹配",
  conflict: "条件待澄清",
  error: "执行异常",
  confirmed: "已确认保存",
};
const slotLabels = {
  equipment_code: "设备",
  name: "配件名称",
  part_code: "配件编码",
  material: "材质",
  max_weight_kg: "重量上限",
  min_weight_kg: "重量下限",
  location: "位置",
};
let current = null,
  histories = [],
  equipment = [],
  config = {},
  busy = false,
  renameId = null,
  confirmCallback = null,
  toastTimer = null;
function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
function notify(message, error = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = "toast visible" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 5000);
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("服务返回了无法读取的响应，请检查服务是否运行。");
    }
    if (!response.ok) {
      let message =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail || "请求失败");
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error("请求超时。请检查执行轨迹和服务状态后重试。");
    if (error instanceof TypeError)
      throw new Error("无法连接本地服务，请确认应用正在运行。");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
function setBusy(value) {
  busy = value;
  document
    .querySelectorAll("button")
    .forEach((el) => (el.disabled = value || el.dataset.selected === "true"));
  $("message-input").disabled = value;
  document.querySelector("main").setAttribute("aria-busy", String(value));
  $("session-status").textContent = value
    ? "正在处理…"
    : statusLabels[current?.status] || "准备就绪";
  if (!value) {
    $("start-search").disabled = !current || current.status === "conflict";
    $("send-message").disabled = !$("message-input").value.trim();
    $("export-session").disabled = !current;
  }
}
function activeSlot(name) {
  const item = current?.slots?.[name];
  return item && typeof item === "object" && "value" in item
    ? item.value
    : item;
}
function storeSessionId(id) {
  try {
    localStorage.setItem("partpilot.session", id);
  } catch {}
}
function savedSessionId() {
  try {
    return localStorage.getItem("partpilot.session");
  } catch {
    return null;
  }
}
async function refreshHistory() {
  const data = await api("/api/sessions");
  histories = data.items || [];
  renderHistory();
}
function adopt(session) {
  current = session;
  storeSessionId(session.id);
  render();
}
async function run(action) {
  if (busy) return;
  setBusy(true);
  try {
    await action();
  } catch (error) {
    if (error.status === 409 && current) {
      try {
        adopt(await api(`/api/sessions/${encodeURIComponent(current.id)}`));
      } catch {}
    }
    notify(error.message, true);
  } finally {
    setBusy(false);
  }
}
async function newSession() {
  await run(async () => {
    adopt(await api("/api/sessions", { method: "POST", body: "{}" }));
    await refreshHistory();
    $("message-input").value = "";
    $("message-input").focus();
  });
}
async function loadSession(id) {
  if ($("history-dialog").open) $("history-dialog").close();
  await run(async () => {
    adopt(await api(`/api/sessions/${encodeURIComponent(id)}`));
    $("message-input").value = "";
  });
}
async function turn(action, text = "", slot = null) {
  if (!current) return;
  await run(async () => {
    if (action === "message") {
      renderPendingMessage(text);
    }
    if (action === "search") renderLoading();
    const session = await api(
      `/api/sessions/${encodeURIComponent(current.id)}/turn`,
      {
        method: "POST",
        body: JSON.stringify({
          action,
          text,
          slot,
          expected_revision: current.revision,
        }),
      },
    );
    adopt(session);
    if (action === "message") $("message-input").value = "";
    await refreshHistory();
  });
  render();
}
function renderHistory() {
  $("history-count").textContent = histories.length;
  $("history-list").innerHTML = histories.length
    ? histories
        .map(
          (h) =>
            `<div class="history-item${h.id === current?.id ? " active" : ""}"><button class="history-main" data-history="${esc(h.id)}" title="${esc(h.title || "新配件查找")}">${icon("message")}<span class="history-text">${esc(h.title || "新配件查找")}</span></button><button class="history-action" data-rename="${esc(h.id)}" title="重命名会话" aria-label="重命名 ${esc(h.title || "会话")}">${icon("edit")}</button><button class="history-action" data-delete="${esc(h.id)}" title="删除会话" aria-label="删除 ${esc(h.title || "会话")}">${icon("trash")}</button></div>`,
        )
        .join("")
    : '<div class="history-empty">新的查找会保存在这里<br>随时回来，接着查找</div>';
  $("mobile-history-list").innerHTML = $("history-list").innerHTML;
}
function renderWelcome() {
  return `<div class="welcome-badge">${icon("sparkles")}</div><h3 class="welcome-title">你好，今天在找什么配件？</h3><p class="welcome-copy">告诉我配件名称、使用位置或已知特征。<br>我会帮你整理条件，再由你启动检索。</p><div class="examples-label">试着从这些描述开始</div><button class="example-button" data-example="找液压回油滤芯"><span>${icon("filter")}</span>找液压回油滤芯<span>${icon("arrow-right")}</span></button><button class="example-button" data-example="设备 DEMO-EX-001，找液压泵"><span>${icon("equipment")}</span>设备 DEMO-EX-001，找液压泵<span>${icon("arrow-right")}</span></button><button class="example-button" data-example="设备 DEMO-EX-002"><span>${icon("box")}</span>我只知道设备编码<span>${icon("arrow-right")}</span></button><div class="welcome-note">${icon("info")}<span>当前为离线规则演示，使用合成数据。<br>不调用外部模型，不代表生产检索效果。</span></div>`;
}
function messageHtml(m) {
  if (m.role === "system")
    return `<div class="message-system">${esc(m.content)}</div>`;
  const isUser = m.role === "user";
  return `<article class="message ${isUser ? "user" : "assistant"}"><div class="message-avatar">${isUser ? "我" : icon("sparkles")}</div><div class="message-body"><div class="message-label">${isUser ? "你" : "PartPilot"}</div><div class="message-text">${esc(m.content)}</div></div></article>`;
}
function renderMessages() {
  const messages = current?.messages || [];
  $("message-list").innerHTML = messages.length
    ? messages.map(messageHtml).join("")
    : renderWelcome();
  $("message-list").scrollTop = $("message-list").scrollHeight;
  const suggestions = (current?.suggestions || [])
    .filter((v) => typeof v === "string")
    .slice(0, 3);
  $("suggestions").innerHTML = suggestions
    .map(
      (s) =>
        `<button class="suggestion" data-example="${esc(s)}">${esc(s)}</button>`,
    )
    .join("");
}
function renderPendingMessage(text) {
  const list = $("message-list");
  if (!current.messages?.length) list.innerHTML = "";
  list.insertAdjacentHTML(
    "beforeend",
    messageHtml({ role: "user", content: text }) +
      `<div class="message assistant"><div class="message-avatar">${icon("sparkles")}</div><div class="message-body"><div class="message-label">正在整理你的信息</div><div class="typing"><i></i><i></i><i></i></div></div></div>`,
  );
  list.scrollTop = list.scrollHeight;
}
function renderConditions() {
  const slots = current?.slots || {};
  let entries = Object.entries(slots).filter(
    ([key, item]) =>
      slotLabels[key] &&
      item != null &&
      (typeof item === "object" ? item.value : item) !== null,
  );
  entries.sort(([a], [b]) =>
    a === "equipment_code" ? -1 : b === "equipment_code" ? 1 : 0,
  );
  $("conditions-list").innerHTML = entries.length
    ? entries
        .map(([key, item]) => {
          const value = typeof item === "object" ? item.value : item;
          const inferred =
            ["model", "inferred"].includes(item.source) && !item.confirmed;
          return `<span class="slot-chip${key === "equipment_code" ? " equipment" : ""}${inferred ? " inferred" : ""}"><span class="slot-label">${esc(slotLabels[key])}</span><strong>${esc(value)}${key.endsWith("_kg") ? " kg" : ""}${key.endsWith("_kg") && item.inclusive === false ? "（不含）" : ""}</strong>${inferred ? '<span class="slot-source">推断，非硬条件</span>' : ""}${key !== "equipment_code" ? `<button data-clear-slot="${esc(key)}" title="移除${esc(slotLabels[key])}" aria-label="移除${esc(slotLabels[key])}">${icon("x")}</button>` : ""}</span>`;
        })
        .join("")
    : `<div class="condition-empty">${icon("equipment")}尚未设置条件 · 描述配件或先选择设备</div>`;
  $("edit-equipment").innerHTML =
    icon("edit") + (activeSlot("equipment_code") ? "更换设备" : "设置设备");
  $("conditions-help").textContent =
    current?.status === "conflict"
      ? "条件存在冲突，请先在对话中澄清"
      : activeSlot("equipment_code")
        ? "条件变化后请重新启动检索"
        : "先提供设备编码，再启动检索";
}
function partIllustration(part) {
  const kind = part.illustration;
  let shape;
  if (kind === "filter") {
    shape =
      '<ellipse cx="75" cy="123" rx="37" ry="7" fill="#a7b49a" opacity=".2"/><path d="M49 42h52v63c0 11-52 11-52 0z" fill="url(#metal)" stroke="#889b7c" stroke-width="1.3"/><path d="M54 48v56m6-57v60m6-59v60m6-59v60m6-60v60m6-61v61m6-62v61m6-64v62" stroke="#8c9e80" stroke-width="1.5" opacity=".6"/><ellipse cx="75" cy="42" rx="26" ry="9" fill="#d2dac9" stroke="#869978"/><ellipse cx="75" cy="42" rx="11" ry="4" fill="#798c6e"/><path d="M48 102c0 11 54 11 54 0v7c0 11-54 11-54 0z" fill="#bac6ac" stroke="#8ea17f"/>';
  } else if (kind === "bolt") {
    shape =
      '<ellipse cx="79" cy="123" rx="42" ry="7" fill="#a7b49a" opacity=".2"/><path d="m50 46 19-13 22 11 2 23-20 13-22-11z" fill="url(#metal)" stroke="#859a79"/><path d="m50 46 23 12 18-14M73 58v22" stroke="#879b7b" fill="none"/><path d="m72 77 14-8 23 34-14 12z" fill="#bfccb1" stroke="#849a75"/><path d="m78 79 14-8m-10 14 14-8m-10 14 14-8m-10 14 14-8m-10 14 14-8" stroke="#8fa47e"/>';
  } else if (kind === "hose") {
    shape =
      '<ellipse cx="75" cy="122" rx="45" ry="7" fill="#a7b49a" opacity=".2"/><path d="M48 43c-37 48-15 74 34 56 32-12 34-33 17-51" fill="none" stroke="#73856c" stroke-width="18"/><path d="M48 43c-37 48-15 74 34 56 32-12 34-33 17-51" fill="none" stroke="#a9b59b" stroke-width="11"/><path d="m40 37 15 8 7-16-15-8zM91 44l16 10 8-13-16-10z" fill="#ced8bf" stroke="#829675"/>';
  } else if (kind === "seal" || kind === "bearing") {
    shape =
      '<ellipse cx="76" cy="121" rx="43" ry="8" fill="#a7b49a" opacity=".2"/><ellipse cx="75" cy="78" rx="44" ry="36" fill="url(#metal)" stroke="#8fa280"/><ellipse cx="75" cy="72" rx="44" ry="36" fill="#c9d4bd" stroke="#8fa280"/><ellipse cx="75" cy="72" rx="25" ry="21" fill="#f6f8f1" stroke="#8fa280"/><ellipse cx="75" cy="72" rx="35" ry="29" fill="none" stroke="#a1b291" stroke-width="6"/>';
  } else {
    shape =
      '<ellipse cx="76" cy="123" rx="43" ry="8" fill="#a7b49a" opacity=".2"/><path d="m39 55 35-20 37 20v45l-36 19-36-21z" fill="url(#metal)" stroke="#8a9e7b"/><path d="m39 55 37 20 35-20M76 75v44" fill="none" stroke="#8d9f7f"/><path d="m51 48 24 14 22-12-23-14z" fill="#cfdbc1" stroke="#8d9f7f"/><path d="M63 39V26l17-8 15 9v15l-14 8z" fill="#c2d0b3" stroke="#8d9f7f"/><path d="m63 26 17 10 15-9M80 36v14" fill="none" stroke="#8d9f7f"/><ellipse cx="48" cy="82" rx="8" ry="13" fill="#b0c19f" stroke="#8d9f7f"/><path d="m92 89 22-12 9 6v13l-23 12-8-6z" fill="#b9c9a8" stroke="#8d9f7f"/>';
  }
  return `<svg viewBox="0 0 150 140" aria-hidden="true"><defs><linearGradient id="metal" x1="0" x2="1"><stop offset="0" stop-color="#dce4d2"/><stop offset=".5" stop-color="#b6c4a7"/><stop offset="1" stop-color="#dae3ce"/></linearGradient></defs>${shape}</svg>`;
}
function cardHtml(part) {
  const locked = current?.status === "confirmed";
  const selected = current?.selection && current.selection.part_id === part.id;
  return `<article class="part-card"><div class="part-visual">${partIllustration(part)}<span class="part-category">${esc(part.category || "演示配件")}</span><span class="illustration-label">类别示意 · 非实物图</span></div><div class="part-info"><div class="part-code">${esc(part.id)}</div><h3>${esc(part.name)}</h3><div class="part-meta"><span>${esc(part.material || "材质未提供")}</span><span>${part.weight_kg != null ? esc(part.weight_kg) + " kg" : "重量未提供"}</span></div><div class="part-reasons">${(
    part.reasons || []
  )
    .slice(0, 2)
    .map((r) => `<span>${esc(r)}</span>`)
    .join(
      "",
    )}</div><div class="part-actions"><button class="secondary-button" data-detail="${esc(part.id)}">查看详情</button><button class="primary-button" data-select="${esc(part.id)}" ${locked ? 'disabled data-selected="true"' : ""}>${selected ? icon("check") + " 已确认" : locked ? "本次已确认" : "就是这个"}</button></div></div></article>`;
}
function emptyGraphic(large = "box", small = "search") {
  return `<div class="empty-graphic"><div class="orbit"></div><span class="big-icon">${icon(large)}</span><span class="little-icon">${icon(small)}</span></div>`;
}
function diagnosticText(d) {
  if (typeof d === "string") return d;
  if (d.message) return d.message;
  if (d.summary) return d.summary;
  const label = slotLabels[d.slot || d.field] || d.slot || d.field || "条件";
  const count =
    d.without_count ??
    d.count ??
    d.remaining_count ??
    d.result_count ??
    d.relaxed_count;
  return count != null
    ? `移除「${label}」后可匹配 ${count} 条配件；是否放宽由你决定。`
    : JSON.stringify(d);
}
function renderResults() {
  const parts = current?.results || [];
  const status = current?.status || "collecting";
  $("result-count").textContent = parts.length;
  $("results-caption").textContent =
    status === "results" || status === "confirmed"
      ? `共 ${current?.total ?? parts.length} 条匹配 · 展示 ${parts.length} 条`
      : {
          no_results: "条件没有匹配结果",
          error: "工具未成功执行",
          conflict: "请先解决条件冲突",
          ready: "条件已更新，等待检索",
        }[status] || "等待启动检索";
  let html = "";
  if (status === "confirmed") {
    const selection = current.selection || {};
    html += `<div class="state-banner success">${icon("check")}<div><strong>配件已确认，记录已保存</strong>${esc(selection.part_id || "当前候选")} · 可在历史会话中继续查看</div></div>`;
  }
  if (parts.length && (status === "results" || status === "confirmed")) {
    html += `<div class="results-grid">${parts.map(cardHtml).join("")}</div><p class="results-note">候选来自当前设备与条件的实际目录查询。请查看详情后确认，示意图不用于外观核验。</p>`;
  } else if (status === "no_results") {
    html += `<div class="empty-state">${emptyGraphic("search", "filter")}<h3>当前条件下，没有找到匹配配件</h3><p>可以修改条件后重试，或仅保留设备编码重新查找。系统不会自动放宽你的条件。</p>${(current.diagnostics || []).length ? `<ul class="diagnostics">${current.diagnostics.map((d) => `<li>${esc(diagnosticText(d))}</li>`).join("")}</ul>` : ""}<div class="state-action"><button class="secondary-button" data-action="fallback">${icon("refresh")}仅按设备重新检索</button></div></div>`;
  } else if (status === "error") {
    html += `<div class="empty-state">${emptyGraphic("alert", "refresh")}<h3>这次查询未能完成</h3><p>工具执行失败不代表没有匹配配件。请展开执行轨迹查看原因，恢复服务后可以重试。</p><div class="state-action"><button class="primary-button" data-action="search">${icon("refresh")}重新尝试检索</button></div></div>`;
  } else if (status === "conflict") {
    html += `<div class="empty-state">${emptyGraphic("sliders", "alert")}<h3>需要先澄清检索条件</h3><p>条件存在冲突，请在对话中说明正确的信息。澄清后再启动检索，避免使用错误结果。</p></div>`;
  } else {
    html += `<div class="empty-state">${emptyGraphic()}<h3>${status === "ready" ? "条件已准备好，开始一次查找吧" : "合适的配件，从清晰的条件开始"}</h3><p>${status === "ready" ? "检查上方条件，点击「启动检索」。修改条件后，旧候选会失效，确保结果与你的需求一致。" : "提供设备编码和配件描述后，候选结果会出现在这里。每一次检索都保留可追溯的执行记录。"}</p><div class="empty-steps"><span><i>1</i>描述需求</span><b>→</b><span><i>2</i>启动检索</span><b>→</b><span><i>3</i>确认配件</span></div></div>`;
  }
  $("result-content").innerHTML = html;
}
function renderLoading() {
  $("results-caption").textContent = "正在查询演示目录…";
  $("result-content").innerHTML =
    '<div class="results-grid"><div class="skeleton-card"></div><div class="skeleton-card"></div></div>';
}
function renderTrace() {
  const trace = current?.trace || [];
  $("trace-count").textContent = trace.length;
  $("trace-list").innerHTML = trace.length
    ? trace
        .slice(-40)
        .reverse()
        .map(
          (t) =>
            `<div class="trace-row"><span class="trace-dot${["error", "failed", "timeout"].includes(t.status) ? " fail" : ""}"></span><div><div class="trace-name">${esc(t.tool || t.node || "业务状态")} · ${esc(t.status || "完成")}</div><div class="trace-description">${esc(t.summary || "")}</div></div><span class="trace-duration">${t.elapsed_ms != null ? esc(Math.round(t.elapsed_ms)) + " ms" : ""}</span></div>`,
        )
        .join("")
    : '<p class="trace-description">尚无执行记录，开始对话后将在这里显示。</p>';
}
function render() {
  renderHistory();
  renderMessages();
  renderConditions();
  renderResults();
  renderTrace();
  $("session-status").textContent = statusLabels[current?.status] || "准备就绪";
  $("session-status").className = "session-status " + (current?.status || "");
  setBusy(busy);
}
function askConfirmation(title, description, action, label = "确认") {
  confirmCallback = action;
  $("confirm-title").textContent = title;
  $("confirm-description").textContent = description;
  $("confirm-action").textContent = label;
  $("confirm-dialog").showModal();
}
function confirmPart(id) {
  const part = (current?.results || []).find((p) => p.id === id);
  if (!part) {
    notify("候选已经更新，请重新检索后选择。", true);
    return;
  }
  const sessionId = current.id,
    queryId = current.query_id,
    revision = current.revision;
  askConfirmation(
    "确认就是这个配件？",
    `${part.name}（${part.id}）\n确认后将保存选择记录。本项目为合成数据演示，不创建采购订单。`,
    async () => {
      await run(async () => {
        adopt(
          await api(`/api/sessions/${encodeURIComponent(sessionId)}/confirm`, {
            method: "POST",
            body: JSON.stringify({
              part_id: id,
              query_id: queryId,
              expected_revision: revision,
            }),
          }),
        );
        if ($("detail-dialog").open) $("detail-dialog").close();
        await refreshHistory();
        notify("确认记录已保存");
      });
    },
    "确认并保存",
  );
}
async function showDetail(id) {
  await run(async () => {
    const part = await api(`/api/parts/${encodeURIComponent(id)}`);
    const canConfirm =
      (current?.results || []).some((p) => p.id === id) &&
      (current.status === "results" || current?.selection?.part_id === id);
    const selected = current?.selection?.part_id === id;
    $("detail-content").innerHTML =
      `<div class="detail-hero"><div class="detail-image">${partIllustration(part)}<span class="illustration-label">类别示意 · 非实物图</span></div><div><div class="detail-code">${esc(part.id)}</div><h2>${esc(part.name)}</h2><div class="detail-category">${esc(part.category || "配件")}</div><p class="detail-description">${esc(part.description || "暂无描述")}</p></div></div><div class="detail-grid"><div class="detail-field"><label>材质</label><span>${esc(part.material || "未提供")}</span></div><div class="detail-field"><label>重量</label><span>${part.weight_kg != null ? esc(part.weight_kg) + " kg" : "未提供，不视为 0"}</span></div><div class="detail-field"><label>尺寸（长 × 宽 × 高）</label><span>${Array.isArray(part.dimensions_mm) ? part.dimensions_mm.map(esc).join(" × ") + " mm" : "未提供"}</span></div><div class="detail-field"><label>别名</label><span>${(part.aliases || []).map(esc).join("、") || "未提供"}</span></div><div class="detail-field wide"><label>适用设备</label><span>${(part.equipment_codes || []).map(esc).join(" / ") || "未提供"}</span></div><div class="detail-field wide"><label>装配层级路径（非爆炸图核验）</label><span>${(part.assembly_path || []).map(esc).join(" → ") || "未提供"}</span></div></div><div class="detail-source">${icon("shield")}合成演示数据，仅用于验证业务流程；不能用于真实设备采购与安装。</div>${canConfirm ? `<div class="dialog-actions"><button class="secondary-button" data-close="detail-dialog">返回候选</button><button class="primary-button" data-select="${esc(part.id)}" ${selected ? 'disabled data-selected="true"' : ""}>${selected ? "已确认保存" : "就是这个 · 确认选择"}</button></div>` : ""}`;
    $("detail-dialog").showModal();
  });
}
async function exportSession() {
  if (!current) return;
  await run(async () => {
    const data = await api(
      `/api/sessions/${encodeURIComponent(current.id)}/export`,
    );
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json;charset=utf-8",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `partpilot-${current.id}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("会话及执行记录已导出");
  });
}
function bindEvents() {
  $("new-session").addEventListener("click", newSession);
  $("open-history").addEventListener("click", () =>
    $("history-dialog").showModal(),
  );
  $("export-session").addEventListener("click", exportSession);
  $("start-search").addEventListener("click", () => turn("search"));
  $("message-input").addEventListener("input", () => {
    $("send-message").disabled = busy || !$("message-input").value.trim();
  });
  $("message-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("message-form").requestSubmit();
    }
  });
  $("message-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("message-input").value.trim();
    if (text && !busy) turn("message", text);
  });
  $("edit-equipment").addEventListener("click", () => {
    if (!equipment.length) {
      notify("暂无设备目录，请检查服务。", true);
      return;
    }
    $("equipment-select").value =
      activeSlot("equipment_code") || equipment[0].code;
    $("equipment-dialog").showModal();
  });
  $("equipment-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const code = $("equipment-select").value;
    $("equipment-dialog").close();
    turn("message", `设备编码改为 ${code}`);
  });
  $("confirm-action").addEventListener("click", async () => {
    const callback = confirmCallback;
    confirmCallback = null;
    $("confirm-dialog").close();
    if (callback) await callback();
  });
  $("rename-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const title = $("rename-input").value.trim();
    if (!title) return;
    $("rename-dialog").close();
    run(async () => {
      const session = await api(
        `/api/sessions/${encodeURIComponent(renameId)}`,
        { method: "PATCH", body: JSON.stringify({ title }) },
      );
      if (current?.id === session.id) adopt(session);
      await refreshHistory();
      notify("会话名称已更新");
    });
  });
  document.addEventListener("click", (e) => {
    const button = e.target.closest("button");
    if (!button || button.disabled) return;
    const data = button.dataset;
    if (data.close) {
      $(data.close).close();
      return;
    }
    if (data.example !== undefined) {
      $("message-input").value = data.example;
      turn("message", data.example);
    } else if (data.history) {
      loadSession(data.history);
    } else if (data.rename) {
      const item = histories.find((h) => h.id === data.rename);
      renameId = data.rename;
      $("rename-input").value = item?.title || "配件查找";
      $("rename-dialog").showModal();
      $("rename-input").select();
    } else if (data.delete) {
      const id = data.delete;
      askConfirmation(
        "删除这个会话？",
        "将删除会话内容、执行记录及该会话的确认记录。此操作无法撤销。",
        async () =>
          run(async () => {
            await api(`/api/sessions/${encodeURIComponent(id)}`, {
              method: "DELETE",
            });
            if (current?.id === id) {
              await refreshHistory();
              adopt(
                histories.length
                  ? await api(
                      `/api/sessions/${encodeURIComponent(histories[0].id)}`,
                    )
                  : await api("/api/sessions", { method: "POST", body: "{}" }),
              );
            }
            await refreshHistory();
            notify("会话已删除");
          }),
        "删除会话",
      );
    } else if (data.clearSlot) {
      turn("clear_slot", "", data.clearSlot);
    } else if (data.action) {
      turn(data.action);
    } else if (data.detail) {
      showDetail(data.detail);
    } else if (data.select) {
      confirmPart(data.select);
    }
  });
  document.querySelectorAll("dialog").forEach((dialog) =>
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) {
        const r = dialog.getBoundingClientRect();
        if (
          e.clientX < r.left ||
          e.clientX > r.right ||
          e.clientY < r.top ||
          e.clientY > r.bottom
        )
          dialog.close();
      }
    }),
  );
}
async function init() {
  hydrateIcons();
  bindEvents();
  setBusy(true);
  try {
    const [cfg, devices, sessions] = await Promise.all([
      api("/api/config"),
      api("/api/equipment"),
      api("/api/sessions"),
    ]);
    config = cfg;
    equipment = devices.items || [];
    histories = sessions.items || [];
    $("catalog-count").textContent = cfg.part_count ?? "—";
    $("equipment-count").textContent = cfg.equipment_count ?? equipment.length;
    $("mode-badge").innerHTML =
      "<i></i>" +
      esc(
        cfg.mode === "demo"
          ? "离线规则演示 · 合成数据"
          : `${cfg.model || "在线模型"} · 合成数据`,
      );
    $("call-budget").textContent = cfg.external_calls_enabled
      ? `API 预算 ¥${cfg.budget_cny}`
      : "外部调用已关闭 · ¥0";
    $("equipment-select").innerHTML = equipment
      .map(
        (d) =>
          `<option value="${esc(d.code)}">${esc(d.code)} · ${esc(d.name || d.model)}</option>`,
      )
      .join("");
    const saved = savedSessionId();
    const initial = histories.find((h) => h.id === saved) || histories[0];
    adopt(
      initial
        ? await api(`/api/sessions/${encodeURIComponent(initial.id)}`)
        : await api("/api/sessions", { method: "POST", body: "{}" }),
    );
    await refreshHistory();
  } catch (error) {
    $("message-list").innerHTML =
      `<div class="state-banner error">${icon("alert")}<div><strong>连接本地工作区失败</strong>${esc(error.message)}</div></div><button class="secondary-button" onclick="location.reload()">重新连接</button>`;
    $("result-content").innerHTML =
      `<div class="empty-state">${emptyGraphic("alert", "refresh")}<h3>等待服务连接</h3><p>请根据 README 启动本地应用，再重新加载页面。</p></div>`;
    notify(error.message, true);
  } finally {
    setBusy(false);
  }
}
init();
