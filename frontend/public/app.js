import {
  formatDate as date,
  phoneError,
  readApiResponse,
} from "./api-client.js";

const $ = (id) => document.getElementById(id);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const state = {
  status: "",
  priority: "",
  queue: "",
  q: "",
  offset: 0,
  limit: 20,
  total: 0,
  selected: null,
  generation: 0,
  detailGeneration: 0,
  busy: false,
};
const statusNames = {
  dispatched: "Dispatched",
  failed: "Failed",
  pending: "Pending",
};
let searchTimer, toastTimer;

function name(lead) {
  return (
    [lead.first_name, lead.last_name].filter(Boolean).join(" ") ||
    lead.email ||
    lead.phone ||
    "Unnamed contact"
  );
}
function ask(lead) {
  if (lead.input_safety === "suspicious") return "Suspicious content — inspect original notes before acting.";
  const value = String((lead.summary?.startsWith("Source:") ? lead.notes : lead.summary) || lead.notes || "Ask not available yet").trim();
  const sentence = value.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() || value;
  return sentence.length > 160 ? `${sentence.slice(0, 157).trimEnd()}…` : sentence;
}
function nextAction(lead) {
  if (lead.review_status === "discarded") return "Discarded";
  if (lead.completed_at) return "Follow-up complete";
  if (lead.review_status === "accepted" && lead.response_priority === "review") return "Accepted — priority not recorded";
  const label = lead.review_status === "pending" ? "Needs review" :
    lead.response_priority ? `Respond · ${lead.response_priority}` : "Awaiting assessment";
  const due = Date.parse(lead.response_due_at);
  return Number.isFinite(due) ? `${label} · ${due < Date.now() ? "OVERDUE · " : ""}${date(lead.response_due_at, true)}` : label;
}
function initials(lead) {
  return lead.first_name || lead.last_name
    ? [lead.first_name?.[0], lead.last_name?.[0]]
        .filter(Boolean)
        .join("")
        .toUpperCase()
    : (lead.email || lead.phone || "?").slice(0, 2).toUpperCase();
}
function badge(status) {
  return `<span class="status-badge ${escape(status)}">${escape(statusNames[status] || status)}</span>`;
}
function message(error) {
  return error.message || "Something went wrong. Please try again.";
}
function showError(id, text) {
  $(id).textContent = text;
  $(id).hidden = !text;
}
function toast(text) {
  clearTimeout(toastTimer);
  $("toast").textContent = text;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => ($("toast").hidden = true), 6500);
}
function connection(online) {
  $("connection").className = `connection ${online ? "online" : "offline"}`;
  $("connection").replaceChildren(
    Object.assign(document.createElement("span"), {}),
    document.createTextNode(online ? "API connected" : "API unavailable"),
  );
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    throw new Error(
      options.method === "POST"
        ? "The request could not be confirmed. Refresh the inbox before submitting again; the lead may already be saved."
        : "Cannot reach the lead service. Check your connection and try again.",
    );
  }
  return readApiResponse(response, {
    page: (path === "/leads" && !options.method) || path.startsWith("/leads?"),
    write: options.method === "POST",
  });
}

async function loadLeads() {
  const generation = ++state.generation;
  $("inbox-heading").textContent = state.queue
    ? `${state.queue[0].toUpperCase()}${state.queue.slice(1)} leads`
    : state.priority
    ? `${state.priority === "review" ? "Needs review" : state.priority} leads`
    : state.status
      ? `${statusNames[state.status]} contacts`
      : "All contacts";
  $("lead-rows").replaceChildren();
  $("empty-state").hidden = false;
  $("empty-title").textContent = "Loading your inbox";
  $("empty-description").textContent = "Fetching the latest lead activity.";
  $("empty-create").hidden = true;
  $("previous").disabled = $("next").disabled = true;
  $("refresh").disabled = true;
  $("page-summary").textContent = "Loading…";
  showError("list-error", "");
  try {
    const params = new URLSearchParams({
      limit: state.limit,
      offset: state.offset,
    });
    if (state.q) params.set("q", state.q);
    if (state.status) params.set("status", state.status);
    if (state.priority) params.set("priority", state.priority);
    if (state.queue) params.set("queue", state.queue);
    const result = await api(`/leads?${params}`);
    if (generation !== state.generation) return;
    connection(true);
    state.total = result.total;
    if (state.offset && state.offset >= result.total) {
      state.offset = Math.max(
        0,
        Math.floor((result.total - 1) / state.limit) * state.limit,
      );
      return loadLeads();
    }
    const all = Object.values(result.counts).reduce((a, b) => a + b, 0);
    $("total-count").textContent = all;
    $("nav-count").textContent = all;
    $("dispatched-count").textContent = result.counts.dispatched;
    $("failed-count").textContent = result.counts.failed;
    $("review-count").textContent = result.priority_counts?.review ?? 0;
    $("action-overdue-count").textContent = result.action_counts?.overdue ?? 0;
    $("action-accepted-count").textContent = result.action_counts?.accepted ?? 0;
    $("action-caption").textContent = `${result.action_counts?.review ?? 0} waiting for review; ${result.action_counts?.overdue ?? 0} overdue; ${result.action_counts?.accepted ?? 0} accepted for follow-up.`;
    $("action-review-count").textContent = result.priority_counts?.review ?? 0;
    $("action-failed-count").textContent = result.counts.failed;
    $("action-immediate-count").textContent =
      result.priority_counts?.immediate ?? 0;
    $("list-caption").textContent =
      `${state.priority || ["overdue", "accepted"].includes(state.queue) ? "Earliest due first" : "Latest first"} · ${result.total} contacts${state.q ? " matching your search" : ""}`;
    $("lead-rows").innerHTML = result.items
      .map(
        (lead, i) => `<tr>
      <td><div class="contact"><span class="avatar tone-${i % 4}" aria-hidden="true">${escape(initials(lead))}</span><div class="contact-copy"><button class="contact-button" data-lead="${escape(lead.id)}">${escape(name(lead))}</button><small>${escape(lead.email || lead.phone || "No contact details")}</small></div></div></td>
      <td class="company-cell">${escape(lead.company || "—")}</td><td class="ask-cell">${escape(ask(lead))}</td><td class="next-action-cell">${escape(nextAction(lead))}</td><td><span class="source-tag">${escape(lead.source)}</span></td><td>${badge(lead.status)}</td><td class="date-cell">${escape(date(lead.created_at))}</td><td><button class="row-open" data-lead="${escape(lead.id)}" aria-label="View ${escape(name(lead))}">↗</button></td></tr>`,
      )
      .join("");
    $("empty-state").hidden = result.items.length > 0;
    $("empty-title").textContent =
      all === 0 ? "Your next connection starts here" : "No leads found";
    $("empty-description").textContent =
      all === 0
        ? "Add your first lead and we’ll take care of the handoff."
        : "Try a different search or delivery filter.";
    $("empty-create").hidden = all !== 0;
    $("page-summary").textContent = result.total
      ? `Showing ${state.offset + 1}–${state.offset + result.items.length} of ${result.total} contacts`
      : "0 contacts";
    $("previous").disabled = state.offset === 0;
    $("next").disabled = state.offset + state.limit >= result.total;
  } catch (error) {
    if (generation !== state.generation) return;
    connection(false);
    showError("list-error", message(error));
    $("empty-title").textContent = "Your inbox is temporarily unavailable";
    $("empty-description").textContent =
      "Your saved leads are still in the database. Refresh to try again.";
    $("page-summary").textContent = "Could not load contacts";
    $("list-caption").textContent =
      "Connection unavailable · displayed totals may be out of date";
  } finally {
    if (generation === state.generation) $("refresh").disabled = false;
  }
}

function renderDetail(lead) {
  state.selected = lead;
  $("retry-lead").disabled = $("detail-refresh").disabled = false;
  $("review-accept").hidden = !(
    lead.response_priority === "review" && lead.review_status === "pending"
  );
  $("review-discard").hidden = $("review-accept").hidden;
  $("review-fields").hidden = $("review-accept").hidden;
  $("complete-lead").hidden = !lead.response_priority || lead.response_priority === "review" ||
    ["pending", "discarded"].includes(lead.review_status) || !!lead.completed_at;
  $("retry-lead").textContent = "Retry delivery ↗";
  const item = (label, value) =>
    `<div><dt>${label}</dt><dd>${escape(value || "—")}</dd></div>`;
  const note =
    lead.status === "dispatched"
      ? "Automation accepted this lead. Dispatched confirms delivery, not completion of downstream work."
      : lead.status === "failed"
        ? "This contact is safely saved. Resolve the delivery issue, then retry the handoff."
        : "The contact has been saved. Refresh to check delivery progress.";
  const priorityNames = {
    immediate: "Immediate · within 15 minutes",
    priority: "Priority · within 1 hour",
    standard: "Standard · within 1 business day",
    low: "Low · within 2 days",
    review: "Human review required",
  };
  const decision = lead.response_priority
    ? `<section class="detail-section"><h3>NEXT ACTION</h3><dl>${item("Priority", priorityNames[lead.response_priority] || lead.response_priority)}${item("Respond by", date(lead.response_due_at, true))}${item("Confidence", lead.decision_confidence == null ? "Not available" : `${Math.round(lead.decision_confidence * 100)}%`)}</dl>${lead.summary ? `<p class="delivery-note">${escape(lead.summary)}</p>` : ""}${lead.decision_error ? `<p class="error-banner">${escape(lead.decision_error)}</p>` : ""}</section>`
    : `<section class="detail-section"><h3>NEXT ACTION</h3><p class="delivery-note">Waiting for the decision workflow. Refresh in a moment.</p></section>`;
  $("detail-content").innerHTML =
    `<div class="avatar detail-avatar" aria-hidden="true">${escape(initials(lead))}</div><h2 id="detail-name">${escape(name(lead))}</h2><p class="detail-company">${escape(lead.company || "Individual contact")}</p>${badge(lead.status)}
    <section class="detail-section"><h3>CONTACT</h3><dl>${item("Email", lead.email)}${item("Phone", lead.phone)}${item("Source", lead.source)}${item("Added", date(lead.created_at, true))}</dl></section>
    <section class="detail-section"><h3>DELIVERY</h3><dl>${item("Attempts", String(lead.dispatch_attempts))}${item("Last response", lead.last_webhook_status_code ? `HTTP ${lead.last_webhook_status_code}` : "No HTTP response")}${item("Updated", date(lead.updated_at, true))}</dl><p class="delivery-note">${note}</p>${lead.last_error ? `<p class="error-banner">${escape(lead.last_error)}</p>` : ""}</section>${decision}
    ${lead.notes ? `<section class="detail-section"><h3>NOTES</h3><p>${escape(lead.notes)}</p></section>` : ""}<section class="detail-section"><h3>LEAD ID</h3><div class="lead-id">${escape(lead.id)}</div></section>`;
  $("retry-lead").hidden = lead.status !== "failed";
  const audit = document.createElement("section");
  audit.className = "detail-section";
  const percent = (v) => v == null ? "Not recorded" : `${Math.round(v * 100)}%`;
  audit.innerHTML = `<h3>DECISION DETAILS</h3><dl>${item("Next action", nextAction(lead))}${item("Summary fidelity", `${lead.summary_fidelity || "Not recorded"} · ${percent(lead.summary_fidelity_confidence)}`)}${item("Input safety", `${lead.input_safety || "Not recorded"} · ${percent(lead.input_safety_confidence)}`)}${item("Reviewer", lead.reviewer_name)}${item("Decision note", lead.review_note)}${item("Reviewed", lead.reviewed_at ? date(lead.reviewed_at, true) : "Not recorded")}</dl>`;
  $("detail-content").append(audit);
}

async function openDetail(id) {
  const generation = ++state.detailGeneration;
  state.selected = null;
  $("review-note").value = "";
  $("review-priority").value = "";
  ["review-fields", "review-accept", "review-discard", "complete-lead"].forEach((id) => $(id).hidden = true);
  showError("detail-error", "");
  $("detail-content").innerHTML = '<h2 id="detail-name">Loading contact…</h2>';
  $("retry-lead").hidden = true;
  $("detail-refresh").disabled = true;
  $("detail-dialog").showModal();
  try {
    const lead = await api(`/leads/${id}`);
    if (generation === state.detailGeneration && $("detail-dialog").open)
      renderDetail(lead);
  } catch (error) {
    if (generation === state.detailGeneration) {
      $("detail-content").innerHTML =
        '<h2 id="detail-name">Contact unavailable</h2>';
      showError("detail-error", message(error));
      state.selected = null;
    }
  } finally {
    if (generation === state.detailGeneration)
      $("detail-refresh").disabled = !state.selected;
  }
}

function openCreate() {
  showError("form-error", "");
  $("create-dialog").showModal();
}
$("new-lead").addEventListener("click", openCreate);
$("empty-create").addEventListener("click", openCreate);
document
  .querySelectorAll("[data-close]")
  .forEach((button) =>
    button.addEventListener("click", () => $(button.dataset.close).close()),
  );
$("create-dialog").addEventListener("cancel", (event) => {
  if (state.busy) event.preventDefault();
});
$("detail-dialog").addEventListener("close", () => {
  state.detailGeneration++;
  state.selected = null;
});
$("detail-dialog").addEventListener("click", (event) => {
  const box = $("detail-dialog").getBoundingClientRect();
  if (event.target === $("detail-dialog") &&
      (event.clientX < box.left || event.clientX > box.right ||
       event.clientY < box.top || event.clientY > box.bottom)) $("detail-dialog").close();
});
$("lead-rows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-lead]");
  if (button) openDetail(button.dataset.lead);
});
$("refresh").addEventListener("click", loadLeads);
$("previous").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadLeads();
});
$("next").addEventListener("click", () => {
  state.offset += state.limit;
  loadLeads();
});
function setFilter(status, priority = "", queue = "") {
  state.status = status;
  state.priority = priority;
  state.queue = queue;
  state.offset = 0;
  document.querySelectorAll(".filter").forEach((button) => {
    const active =
      (button.dataset.status || "") === status &&
      (button.dataset.priority || "") === priority && (button.dataset.queue || "") === queue;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}
document.querySelectorAll(".filter").forEach((button) =>
  button.addEventListener("click", () => {
    setFilter(button.dataset.status || "", button.dataset.priority || "", button.dataset.queue || "");
    loadLeads();
  }),
);
document.querySelectorAll(".action-item").forEach((button) =>
  button.addEventListener("click", () => {
    setFilter(button.dataset.status || "", button.dataset.priority || "", button.dataset.queue || "");
    loadLeads();
  }),
);
$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = $("search").value.trim();
    state.offset = 0;
    loadLeads();
  }, 250);
});

$("lead-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy) return;
  showError("form-error", "");
  const payload = Object.fromEntries(
    [...new FormData(event.target)]
      .map(([key, value]) => [key, value.trim()])
      .filter(([, value]) => value),
  );
  if (!payload.email && !payload.phone) {
    showError(
      "form-error",
      "Add an email address or phone number so this lead can be contacted.",
    );
    event.target.elements.email.focus();
    return;
  }
  if (!payload.source) {
    showError("form-error", "Enter a source for this lead.");
    event.target.elements.source.focus();
    return;
  }
  const phoneMessage = phoneError(payload.phone);
  if (phoneMessage) {
    showError("form-error", phoneMessage);
    event.target.elements.phone.focus();
    return;
  }
  state.busy = true;
  $("form-progress").hidden = false;
  $("create-dialog")
    .querySelectorAll("button,input,textarea")
    .forEach((el) => (el.disabled = true));
  try {
    const lead = await api("/leads", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("create-dialog").close();
    event.target.reset();
    clearTimeout(searchTimer);
    state.q = "";
    $("search").value = "";
    setFilter("");
    await loadLeads();
    renderDetail(lead);
    $("detail-refresh").disabled = false;
    showError("detail-error", "");
    $("detail-dialog").showModal();
    toast(
      lead.status === "dispatched"
        ? "Lead saved and dispatched to automation."
        : "Lead saved. Open delivery details to check its status.",
    );
  } catch (error) {
    showError("form-error", message(error));
  } finally {
    state.busy = false;
    $("form-progress").hidden = true;
    $("create-dialog")
      .querySelectorAll("button,input,textarea")
      .forEach((el) => (el.disabled = false));
  }
});

$("detail-refresh").addEventListener("click", async () => {
  if (!state.selected) return;
  const generation = state.detailGeneration;
  $("detail-refresh").disabled = true;
  showError("detail-error", "");
  try {
    const lead = await api(`/leads/${state.selected.id}`);
    if (generation === state.detailGeneration) renderDetail(lead);
    await loadLeads();
  } catch (error) {
    if (generation === state.detailGeneration)
      showError("detail-error", message(error));
  } finally {
    if (generation === state.detailGeneration)
      $("detail-refresh").disabled = false;
  }
});
$("retry-lead").addEventListener("click", async () => {
  if (!state.selected) return;
  const generation = state.detailGeneration;
  $("retry-lead").disabled = $("detail-refresh").disabled = true;
  $("retry-lead").textContent = "Retrying…";
  showError("detail-error", "");
  try {
    const lead = await api(`/leads/${state.selected.id}/retry`, {
      method: "POST",
    });
    if (generation === state.detailGeneration) renderDetail(lead);
    await loadLeads();
    toast(
      lead.status === "dispatched"
        ? "Delivery recovered. Lead dispatched."
        : "Delivery still needs attention. Your lead remains saved.",
    );
  } catch (error) {
    if (generation === state.detailGeneration)
      showError("detail-error", message(error));
  } finally {
    if (generation === state.detailGeneration) {
      $("retry-lead").disabled = $("detail-refresh").disabled = false;
      $("retry-lead").textContent = "Retry delivery ↗";
    }
  }
});
async function decideReview(decision) {
  if (!state.selected) return;
  const generation = state.detailGeneration;
  const payload = { reviewer_name: $("reviewer-name").value.trim(), note: $("review-note").value.trim(), priority: $("review-priority").value || null };
  if (!payload.reviewer_name || !payload.note || (decision === "accepted" && !payload.priority)) {
    showError("detail-error", "Enter your name and a decision note; choose a priority to accept.");
    return;
  }
  $("review-accept").disabled = $("review-discard").disabled = true;
  showError("detail-error", "");
  try {
    const lead = await api(`/leads/${state.selected.id}/review/${decision}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (generation === state.detailGeneration) renderDetail(lead);
    await loadLeads();
    toast(
      decision === "accepted"
        ? "Review accepted. It is ready for CRM follow-up."
        : "Review discarded and retained in the audit history.",
    );
  } catch (error) {
    if (generation === state.detailGeneration)
      showError("detail-error", message(error));
  } finally {
    $("review-accept").disabled = $("review-discard").disabled = false;
  }
}
$("review-accept").addEventListener("click", () => decideReview("accepted"));
$("review-discard").addEventListener("click", () => decideReview("discarded"));
loadLeads();
$("complete-lead").addEventListener("click", async () => {
  if (!state.selected) return;
  const generation = state.detailGeneration;
  $("complete-lead").disabled = true;
  showError("detail-error", "");
  try {
    const lead = await api(`/leads/${state.selected.id}/complete`, { method: "POST" });
    if (generation === state.detailGeneration) renderDetail(lead);
    await loadLeads();
    toast("Follow-up marked complete.");
  } catch (error) {
    if (generation === state.detailGeneration) showError("detail-error", message(error));
  }
  finally { $("complete-lead").disabled = false; }
});
