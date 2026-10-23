const messagesNode = document.querySelector("#messages");
const composer = document.querySelector("#composer");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");
const auditPanel = document.querySelector("#audit-panel");
const threadList = document.querySelector("#thread-list");
const activeThread = document.querySelector("#active-thread");
const threadCount = document.querySelector("#thread-count");
let currentThreadId = null;
let readOnlyHistory = false;

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text ?? "";
  if (className) node.className = className;
  return node;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "No se pudo completar la solicitud.");
  return data;
}

function addMessage(role, content, trace = null, outOfScope = false, alerts = [], thread = null) {
  const row = document.createElement("div");
  row.className = `bubble-row ${role}`;
  const bubble = role === "assistant" ? document.createElement("button") : document.createElement("div");
  bubble.className = "bubble";
  bubble.type = role === "assistant" ? "button" : undefined;
  bubble.textContent = content;
  if (role === "assistant") {
    bubble.addEventListener("click", () => showAudit(trace, outOfScope, thread, alerts));
    row.append(bubble, textNode("span", "Selecciona para ver la traza", "bubble-meta"));
  } else {
    row.append(bubble);
  }
  messagesNode.append(row);
  messagesNode.scrollTop = messagesNode.scrollHeight;
}

function addProcessingMessage() {
  const row = document.createElement("div");
  row.className = "bubble-row assistant processing-row";
  row.setAttribute("role", "status");
  row.setAttribute("aria-live", "polite");
  const bubble = document.createElement("div");
  bubble.className = "bubble processing-bubble";
  bubble.append(
    textNode("span", "•••", "processing-dots"),
    textNode("span", "Estoy procesando tu mensaje. Espera un momento…", "processing-copy"),
  );
  row.append(bubble);
  messagesNode.append(row);
  messagesNode.scrollTop = messagesNode.scrollHeight;
  return row;
}

function addWelcome() {
  messagesNode.replaceChildren();
  const card = document.createElement("div");
  card.className = "welcome-card";
  card.append(
    textNode("div", "✦", "welcome-icon"),
    textNode("h3", "Hola, ¿en qué puedo orientarte?"),
    textNode("p", "Escribe una consulta cardiovascular o materno-infantil. Selecciona cualquier respuesta del asistente para explorar cómo se construyó."),
  );
  messagesNode.append(card);
}

function section(title, content) {
  const block = document.createElement("section");
  block.className = "audit-section";
  block.append(textNode("h3", title));
  if (content instanceof Node) block.append(content);
  else block.append(textNode("p", content || "No disponible.", "detail-text"));
  return block;
}

function tags(values, warning = false) {
  const list = document.createElement("div");
  list.className = "tag-list";
  if (!values?.length) return textNode("p", "Ninguno registrado.", "detail-text");
  values.forEach((value) => list.append(textNode("span", value, `tag${warning ? " warning" : ""}`)));
  return list;
}

function metricGrid(values) {
  const grid = document.createElement("div");
  grid.className = "audit-grid";
  values.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "metric";
    item.append(textNode("span", label), textNode("strong", value || "—"));
    grid.append(item);
  });
  return grid;
}

function evidenceList(trace) {
  const list = document.createElement("div");
  if (!trace.evidence?.length) return textNode("p", evidenceEmptyMessage(trace), "detail-text");
  trace.evidence.forEach((evidence) => {
    const card = document.createElement("article");
    card.className = "evidence-card";
    const header = document.createElement("div");
    header.className = "evidence-top";
    header.append(
      textNode("span", evidence.label, "evidence-label"),
      textNode("span", evidence.category, "evidence-category"),
      textNode("span", Number(evidence.score).toFixed(2), "score"),
    );
    card.append(header, textNode("p", evidence.question, "evidence-question"), textNode("p", evidence.answer, "evidence-answer"));
    if (trace.cited_evidence.includes(evidence.label)) card.append(textNode("span", "Citada por el agente", "tag"));
    list.append(card);
  });
  return list;
}

function evidenceEmptyMessage(trace) {
  const reasons = {
    insuficiente: "No se halló evidencia suficiente; el sistema se abstuvo de llamar al modelo de respuesta.",
    no_disponible: "El RAG no estuvo disponible.",
  };
  if (!trace.retrieval_status) return "No se buscó evidencia en este turno.";
  return reasons[trace.retrieval_status] || "La búsqueda no devolvió registros.";
}

function showAudit(trace, outOfScope = false, thread = null, alerts = []) {
  auditPanel.replaceChildren();
  if (!trace) {
    const empty = document.createElement("div");
    empty.className = "empty-audit";
    empty.append(textNode("p", "SIN TRAZA", "eyebrow"), textNode("h2", "Turno no registrado"), textNode("p", outOfScope ? "El mensaje fue clasificado fuera del alcance: sin búsqueda ni respuesta del agente (queda en el hilo activo, si lo hay)." : "Este turno no tiene información de auditoría asociada."));
    auditPanel.append(empty);
    if (alerts.length) auditPanel.append(section("Alertas deterministas", alertDetails(alerts)));
    return;
  }
  const header = document.createElement("div");
  header.className = "audit-header";
  header.append(textNode("p", "TRAZABILIDAD DEL AGENTE", "eyebrow"), textNode("h2", thread?.summary || "Detalle del turno"), textNode("div", `${thread?.id || "Hilo no disponible"} · ${thread?.domain || "—"} · ${thread?.status || "—"}`, "audit-subtitle"));
  auditPanel.append(header);
  if (alerts.length) auditPanel.append(section("Alertas deterministas", alertDetails(alerts)));
  auditPanel.append(section("Hilo y alcance", metricGrid([["Dominio", thread?.domain], ["Estado", thread?.status], ["Alcance", trace.scope], ["Motivo", trace.scope_reason]])));
  auditPanel.append(section("Síntomas reportados", tags(trace.reported_symptoms)));
  auditPanel.append(section("Signos del catálogo", tags(trace.reported_signs)));
  if (trace.unstated_symptoms?.length) auditPanel.append(section("Datos que no escribió la persona", tags(trace.unstated_symptoms, true)));
  auditPanel.append(section("Consulta de búsqueda", trace.search_query || "No se registró consulta."));
  if (trace.case) auditPanel.append(section("Cuadro y etapa (base v2)", metricGrid([["Cuadro", trace.case.motive], ["Etapa", trace.case.stage], ["Etapas vistas", trace.case.visited.join(", ")]])));
  auditPanel.append(section("Recuperación de evidencia", metricGrid([["Estado", trace.retrieval_status], ["Mejor puntaje", trace.best_score == null ? "—" : Number(trace.best_score).toFixed(2)], ["Citas", trace.cited_evidence.join(", ") || "Ninguna"], ["Respuesta sin citas", trace.uncited ? "Sí" : "No"]])));
  auditPanel.append(section("Registros recuperados", evidenceList(trace)));
  if (trace.grounding) {
    const check = trace.grounding;
    auditPanel.append(section("Verificación del respaldo", metricGrid([["Frases respaldadas", `${check.supported}/${check.total}`], ["Texto literal", check.literal ? "Sí" : "No"]])));
    if (check.dropped.length) auditPanel.append(section("Frases descartadas", tags(check.dropped, true)));
  } else {
    auditPanel.append(section("Verificación del respaldo", "No aplica en este turno."));
  }
  if (trace.timings?.length) {
    const timingGrid = metricGrid(trace.timings.map((timing) => [timing.stage, `${timing.seconds.toFixed(1)} s`]));
    auditPanel.append(section("Tiempos por etapa", timingGrid));
  }
}

function alertDetails(alerts) {
  const list = document.createElement("div");
  alerts.forEach((alert) => {
    const item = document.createElement("div");
    item.className = "metric";
    item.append(
      textNode("strong", alert.rule_ids.join(", ")),
      textNode("span", `${alert.severity} · origen: ${alert.origin}`),
    );
    list.append(item);
  });
  return list;
}

function updateContext(thread) {
  currentThreadId = thread?.id || null;
  activeThread.textContent = thread
    ? `Hilo ${thread.id.slice(0, 8)} · ${thread.domain} · ${thread.status} · ${thread.summary}`
    : "Sin hilo activo · el siguiente mensaje iniciará un caso";
}

async function loadThreads() {
  try {
    const threads = await request("/api/threads");
    threadCount.textContent = String(threads.length);
    threadList.replaceChildren();
    if (!threads.length) {
      threadList.append(textNode("p", "Aún no hay conversaciones guardadas.", "muted empty-list"));
      return;
    }
    threads.forEach((thread) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `thread-item${thread.id === currentThreadId ? " active" : ""}`;
      button.append(textNode("span", thread.summary, "thread-title"), textNode("span", `${thread.domain} · ${thread.status}`, "thread-meta"));
      button.addEventListener("click", () => openThread(thread.id));
      threadList.append(button);
    });
  } catch (error) {
    threadList.replaceChildren(textNode("p", error.message, "muted empty-list"));
  }
}

async function openThread(threadId) {
  try {
    const data = await request(`/api/threads/${encodeURIComponent(threadId)}`);
    messagesNode.replaceChildren();
    updateContext(data.thread);
    readOnlyHistory = true;
    input.disabled = true;
    input.placeholder = "Historial de solo lectura";
    sendButton.disabled = true;
    data.messages.forEach((message) =>
      addMessage(message.role, message.content, message.trace, false, [], data.thread),
    );
    showAudit(null);
    await loadThreads();
  } catch (error) {
    showError(error.message);
  }
}

function showError(message) {
  messagesNode.append(textNode("div", message, "error-banner"));
  messagesNode.scrollTop = messagesNode.scrollHeight;
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || readOnlyHistory) return;
  addMessage("user", text);
  input.value = "";
  sendButton.disabled = true;
  newChatButton.disabled = true;
  const processingMessage = addProcessingMessage();
  try {
    const result = await request("/api/messages", { method: "POST", body: JSON.stringify({ text }) });
    processingMessage.remove();
    updateContext(result.thread);
    addMessage(
      "assistant", result.reply, result.trace, result.out_of_scope, result.alerts, result.thread,
    );
    showAudit(result.trace, result.out_of_scope, result.thread, result.alerts);
    await loadThreads();
  } catch (error) {
    processingMessage.remove();
    showError(error.message);
    input.value = text;
  } finally {
    sendButton.disabled = false;
    newChatButton.disabled = false;
    input.focus();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  composer.requestSubmit();
});

newChatButton.addEventListener("click", async () => {
  try {
    await request("/api/session/end", { method: "POST" });
  } catch (error) {
    showError(error.message);
    return;
  }
  readOnlyHistory = false;
  input.disabled = false;
  input.placeholder = "Escribe un mensaje…";
  sendButton.disabled = false;
  addWelcome();
  updateContext(null);
  showAudit(null);
  loadThreads();
  input.focus();
});

loadThreads();
