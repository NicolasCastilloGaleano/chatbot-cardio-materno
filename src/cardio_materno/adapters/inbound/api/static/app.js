// Interfaz de auditoría multicanal (HU-10, ADR 0016).
// Lista los chats de todos los canales, los muestra como un chat continuo por persona
// (con un color por hilo), carga los mensajes por partes al subir con el scroll, se
// actualiza sola y solo permite escribir en los chats de consola y web.

const $ = (selector) => document.querySelector(selector);
const nodes = {
  filters: $("#channel-filters"),
  chatList: $("#chat-list"),
  newChat: $("#new-chat"),
  title: $("#chat-title"),
  eyebrow: $("#chat-eyebrow"),
  badge: $("#chat-badge"),
  lockBanner: $("#lock-banner"),
  lockText: $("#lock-text"),
  release: $("#release-chat"),
  messages: $("#messages"),
  newMessages: $("#new-messages"),
  composer: $("#composer"),
  input: $("#message-input"),
  send: $("#send-button"),
  audit: $("#audit-panel"),
};

const STORAGE_KEY = "cardio-materno:chat-abierto";
const THREAD_COLORS = 6;
const TOP_LOAD_PX = 60;
const BOTTOM_STICK_PX = 80;
const LIVE_CONSOLE_LOCK = "en_uso_en_la_consola";
const PENDING_TEXT = "procesando un mensaje de la persona… (el texto aparece al terminar el turno)";

const state = {
  config: { page_size: 30, poll_seconds: 3, channels: [] },
  filter: "",
  chats: [],
  seenActivity: new Map(),
  chatId: null,
  chat: null,
  entries: [],
  ephemeral: [],
  nextBefore: null,
  loadingOlder: false,
  sending: false,
  pending: 0,
  selectedSeq: null,
  unseen: 0,
};

// --- Utilidades ---------------------------------------------------------------------------

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text ?? "";
  if (className) node.className = className;
  return node;
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "No se pudo completar la solicitud.");
  return data;
}

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" });
}

function remember(chatId) {
  try {
    if (chatId) localStorage.setItem(STORAGE_KEY, chatId);
  } catch {
    // Sin almacenamiento local: la interfaz funciona igual.
  }
}

function remembered() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function lastSeq() {
  return state.entries.length ? state.entries[state.entries.length - 1].seq : 0;
}

function isNearBottom() {
  const box = nodes.messages;
  return box.scrollHeight - box.scrollTop - box.clientHeight < BOTTOM_STICK_PX;
}

function scrollToBottom() {
  nodes.messages.scrollTop = nodes.messages.scrollHeight;
  state.unseen = 0;
  nodes.newMessages.hidden = true;
}

// --- Colores por hilo -----------------------------------------------------------------------

function hashIndex(text) {
  let hash = 0;
  for (const char of text) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % THREAD_COLORS;
}

// Color estable por hilo; si coincide con el del hilo anterior, se usa el siguiente.
function threadColors(entries) {
  const colors = new Map();
  let previous = null;
  for (const entry of entries) {
    const id = entry.thread.id;
    if (!colors.has(id)) {
      let index = hashIndex(id);
      if (previous !== null && index === colors.get(previous)) index = (index + 1) % THREAD_COLORS;
      colors.set(id, index);
    }
    previous = id;
  }
  return colors;
}

function colorVar(index) {
  return `var(--thread-${index})`;
}

// --- Lista de chats --------------------------------------------------------------------------

function renderFilters() {
  const options = [{ id: "", label: "Todos" }, ...state.config.channels];
  nodes.filters.replaceChildren(
    ...options.map((option) => {
      const chip = textNode("button", option.label, `filter-chip${option.id === state.filter ? " active" : ""}`);
      chip.type = "button";
      chip.setAttribute("role", "tab");
      chip.setAttribute("aria-selected", String(option.id === state.filter));
      chip.addEventListener("click", () => {
        state.filter = option.id;
        renderFilters();
        loadChats();
      });
      return chip;
    }),
  );
}

async function loadChats() {
  try {
    const query = state.filter ? `?channel=${encodeURIComponent(state.filter)}` : "";
    state.chats = await request(`/api/chats${query}`);
    renderChats();
  } catch (error) {
    nodes.chatList.replaceChildren(textNode("p", error.message, "muted empty-list"));
  }
}

function hasNewActivity(chat) {
  const seen = state.seenActivity.get(chat.id);
  if (chat.id === state.chatId || seen === undefined) {
    state.seenActivity.set(chat.id, chat.last_seen_at);
    return false;
  }
  return seen !== chat.last_seen_at;
}

function chatItem(chat) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = `chat-item${chat.id === state.chatId ? " active" : ""}`;
  const flags = document.createElement("span");
  flags.className = "chat-flags";
  if (!chat.writable) flags.append(textNode("span", "🔒"));
  if (hasNewActivity(chat)) flags.append(textNode("span", "", "new-dot"));
  item.append(
    textNode("span", chat.channel_label, `channel-badge channel-${chat.channel}`),
    textNode("span", chat.short_id, "chat-title"),
    flags,
    textNode("span", `${formatDate(chat.last_seen_at)} · ${chat.message_count} mensajes`, "chat-meta"),
  );
  item.title = chat.lock_text || chat.label;
  item.addEventListener("click", () => openChat(chat.id));
  return item;
}

function renderChats() {
  if (!state.chats.length) {
    nodes.chatList.replaceChildren(textNode("p", "Aún no hay chats en este canal.", "muted empty-list"));
    return;
  }
  nodes.chatList.replaceChildren(...state.chats.map(chatItem));
}

// --- Abrir un chat y cargar páginas ----------------------------------------------------------

async function openChat(chatId) {
  try {
    const page = await request(`/api/chats/${encodeURIComponent(chatId)}/messages`);
    Object.assign(state, {
      chatId, chat: page.chat, entries: page.messages, ephemeral: [], nextBefore: page.next_before,
      pending: page.pending, selectedSeq: null, unseen: 0,
    });
    state.seenActivity.set(chatId, page.chat.last_seen_at);
    remember(chatId);
    renderChatHeader();
    renderMessages();
    scrollToBottom();
    showAudit(null);
    renderChats();
  } catch (error) {
    showError(error.message);
  }
}

async function loadOlder() {
  if (state.loadingOlder || state.nextBefore === null || !state.chatId) return;
  state.loadingOlder = true;
  const chatId = state.chatId;
  try {
    const page = await request(
      `/api/chats/${encodeURIComponent(chatId)}/messages?before=${state.nextBefore}`,
    );
    if (chatId !== state.chatId) return;
    const box = nodes.messages;
    const fromBottom = box.scrollHeight - box.scrollTop;
    state.entries = [...page.messages, ...state.entries];
    state.nextBefore = page.next_before;
    renderMessages();
    box.scrollTop = box.scrollHeight - fromBottom;
  } catch (error) {
    showError(error.message);
  } finally {
    state.loadingOlder = false;
  }
}

function mergeNew(messages) {
  const known = new Set(state.entries.map((entry) => entry.seq));
  const fresh = messages.filter((entry) => !known.has(entry.seq));
  state.entries = [...state.entries, ...fresh];
  return fresh.length;
}

// --- Encabezado y composer -------------------------------------------------------------------

function renderChatHeader() {
  const chat = state.chat;
  nodes.title.textContent = chat ? chat.label : "Selecciona un chat";
  nodes.eyebrow.textContent = chat ? `DESDE ${formatDate(chat.created_at)}` : "CONVERSACIÓN";
  nodes.badge.hidden = !chat;
  if (chat) {
    nodes.badge.textContent = chat.channel_label;
    nodes.badge.className = `channel-badge channel-${chat.channel}`;
  }
  updateComposer();
}

function updateComposer() {
  const chat = state.chat;
  const writable = Boolean(chat?.writable);
  nodes.input.disabled = !writable || state.sending;
  nodes.send.disabled = !writable || state.sending;
  nodes.input.placeholder = writable ? "Escribe un mensaje…" : chat?.lock_text || "Selecciona un chat de consola o web para escribir";
  nodes.lockBanner.hidden = !chat || writable;
  nodes.lockText.textContent = chat?.lock_text || "";
  nodes.release.hidden = chat?.lock !== LIVE_CONSOLE_LOCK;
}

// --- Mensajes --------------------------------------------------------------------------------

function threadSeparator(thread, color) {
  const row = document.createElement("div");
  row.className = "thread-separator";
  row.style.setProperty("--thread", colorVar(color));
  const label = `Hilo ${thread.id.slice(0, 8)} · ${thread.domain} · ${thread.status} · ${thread.summary}`;
  const chip = textNode("span", label, "thread-chip");
  chip.title = label;
  row.append(chip);
  return row;
}

function bubbleRow(entry, color) {
  const row = document.createElement("div");
  row.className = `bubble-row ${entry.role}${entry.ephemeral ? " ephemeral" : ""}`;
  if (color !== null) row.style.setProperty("--thread", colorVar(color));
  const isAssistant = entry.role === "assistant";
  const bubble = document.createElement(isAssistant ? "button" : "div");
  bubble.className = `bubble${entry.seq && entry.seq === state.selectedSeq ? " selected" : ""}`;
  bubble.textContent = entry.content;
  if (isAssistant) {
    bubble.type = "button";
    bubble.addEventListener("click", () => selectEntry(entry, color, bubble));
  }
  row.append(bubble, textNode("span", bubbleMeta(entry), `bubble-meta${entry.alerts?.length ? " alert" : ""}`));
  return row;
}

function bubbleMeta(entry) {
  if (entry.ephemeral) return "Fuera de alcance: no se guarda en el hilo";
  const time = formatDate(entry.created_at);
  if (entry.alerts?.length) return `${time} · ⚠️ ${entry.alerts.map((a) => a.rule_ids.join(", ")).join(" · ")}`;
  return entry.role === "assistant" ? `${time} · Selecciona para ver la traza` : time;
}

function renderMessages() {
  const box = nodes.messages;
  if (!state.chat) return;
  const colors = threadColors(state.entries);
  const children = [];
  if (state.nextBefore === null && state.entries.length) children.push(textNode("div", "Inicio del chat", "history-edge"));
  if (state.nextBefore !== null) children.push(textNode("div", "Sube para cargar mensajes anteriores", "history-edge"));
  let previous = null;
  for (const entry of state.entries) {
    const color = colors.get(entry.thread.id);
    if (entry.thread.id !== previous) children.push(threadSeparator(entry.thread, color));
    previous = entry.thread.id;
    children.push(bubbleRow(entry, color));
  }
  state.ephemeral.forEach((entry) => children.push(bubbleRow(entry, null)));
  if (!children.length) children.push(textNode("div", "Este chat aún no tiene mensajes guardados.", "history-edge"));
  if (state.pending > 0) children.push(pendingRow());
  box.replaceChildren(...children);
}

function pendingRow() {
  const row = document.createElement("div");
  row.className = "bubble-row user processing-row";
  row.setAttribute("role", "status");
  const bubble = document.createElement("div");
  bubble.className = "bubble processing-bubble";
  bubble.append(textNode("span", "•••", "processing-dots"), textNode("span", `${state.chat.channel_label}: ${PENDING_TEXT}`, "processing-copy"));
  row.append(bubble);
  return row;
}

function processingRow() {
  const row = document.createElement("div");
  row.className = "bubble-row assistant processing-row";
  row.setAttribute("role", "status");
  row.setAttribute("aria-live", "polite");
  const bubble = document.createElement("div");
  bubble.className = "bubble processing-bubble";
  bubble.append(textNode("span", "•••", "processing-dots"), textNode("span", "Estoy procesando tu mensaje. Espera un momento…", "processing-copy"));
  row.append(bubble);
  return row;
}

function selectEntry(entry, color, bubble) {
  state.selectedSeq = entry.seq || null;
  nodes.messages.querySelectorAll(".bubble.selected").forEach((node) => node.classList.remove("selected"));
  bubble.classList.add("selected");
  showAudit(entry.trace, entry.ephemeral, entry.thread, entry.alerts || [], color);
}

function showError(message) {
  nodes.messages.append(textNode("div", message, "error-banner"));
  nodes.messages.scrollTop = nodes.messages.scrollHeight;
}

// --- Auditoría de una respuesta --------------------------------------------------------------

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

function alertDetails(alerts) {
  const list = document.createElement("div");
  alerts.forEach((alert) => {
    const item = document.createElement("div");
    item.className = "metric alert";
    item.append(textNode("strong", alert.rule_ids.join(", ")), textNode("span", `${alert.severity} · origen: ${alert.origin}`));
    list.append(item);
  });
  return list;
}

function emptyAudit(outOfScope) {
  const empty = document.createElement("div");
  empty.className = "empty-audit";
  const detail = outOfScope
    ? "El mensaje fue clasificado fuera del alcance y no se guardó en el hilo."
    : "Este turno no consultó al agente (p. ej., una urgencia detectada por las reglas) o no tiene traza.";
  empty.append(textNode("p", "SIN TRAZA", "eyebrow"), textNode("h2", "Turno sin traza del agente"), textNode("p", detail));
  return empty;
}

function auditHeader(thread, color) {
  const header = document.createElement("div");
  header.className = "audit-header";
  if (color !== null && color !== undefined) header.style.setProperty("--thread", colorVar(color));
  header.append(
    textNode("p", "TRAZABILIDAD DEL AGENTE", "eyebrow"),
    textNode("h2", thread?.summary || "Detalle del turno"),
    textNode("div", `${thread?.id || "Hilo no disponible"} · ${thread?.domain || "—"} · ${thread?.status || "—"}`, "audit-subtitle"),
  );
  return header;
}

function showAudit(trace, outOfScope = false, thread = null, alerts = [], color = null) {
  nodes.audit.replaceChildren();
  if (trace === null && thread === null && !alerts.length && !outOfScope) {
    nodes.audit.append(defaultAudit());
    return;
  }
  if (!trace) {
    nodes.audit.append(emptyAudit(outOfScope));
    if (alerts.length) nodes.audit.append(section("Alertas deterministas", alertDetails(alerts)));
    return;
  }
  nodes.audit.append(auditHeader(thread, color));
  if (alerts.length) nodes.audit.append(section("Alertas deterministas", alertDetails(alerts)));
  nodes.audit.append(...traceSections(trace, thread));
}

function traceSections(trace, thread) {
  const sections = [
    section("Hilo y alcance", metricGrid([["Dominio", thread?.domain], ["Estado", thread?.status], ["Alcance", trace.scope], ["Motivo", trace.scope_reason]])),
    section("Síntomas reportados", tags(trace.reported_symptoms)),
    section("Signos del catálogo", tags(trace.reported_signs)),
  ];
  if (trace.reminded_rules?.length) sections.push(section("Alarmas ya avisadas (solo recordatorio)", tags(trace.reminded_rules, true)));
  if (trace.unstated_symptoms?.length) sections.push(section("Datos que no escribió la persona", tags(trace.unstated_symptoms, true)));
  sections.push(
    section("Consulta de búsqueda", (trace.search_query || "No se registró consulta.") + (trace.domain_fallback ? " · ampliada a los dos dominios" : "")),
    section("Recuperación de evidencia", metricGrid([["Estado", trace.retrieval_status], ["Mejor puntaje", trace.best_score == null ? "—" : Number(trace.best_score).toFixed(2)], ["Citas", trace.cited_evidence.join(", ") || "Ninguna"], ["Respuesta sin citas", trace.uncited ? "Sí" : "No"]])),
    section("Registros recuperados", evidenceList(trace)),
    ...groundingSections(trace.grounding),
  );
  if (trace.timings?.length) sections.push(section("Tiempos por etapa", metricGrid(trace.timings.map((t) => [t.stage, `${t.seconds.toFixed(1)} s`]))));
  return sections;
}

function groundingSections(check) {
  if (!check) return [section("Verificación del respaldo", "No aplica en este turno.")];
  const sections = [section("Verificación del respaldo", metricGrid([["Frases respaldadas", `${check.supported}/${check.total}`], ["Texto literal", check.literal ? "Sí" : "No"]]))];
  if (check.dropped.length) sections.push(section("Frases descartadas", tags(check.dropped, true)));
  return sections;
}

function defaultAudit() {
  const empty = document.createElement("div");
  empty.className = "empty-audit";
  empty.append(
    textNode("div", "⌕", "inspect-icon"),
    textNode("p", "TRAZABILIDAD DEL AGENTE", "eyebrow"),
    textNode("h2", "Explora una respuesta"),
    textNode("p", "Haz clic en una respuesta para ver el hilo, los síntomas, la evidencia, su verificación y las alertas del turno."),
  );
  return empty;
}

// --- Enviar -----------------------------------------------------------------------------------

async function sendMessage(text) {
  const chatId = state.chatId;
  state.sending = true;
  updateComposer();
  nodes.messages.append(bubbleRow({ role: "user", content: text, ephemeral: false, created_at: new Date().toISOString() }, null), processingRow());
  scrollToBottom();
  try {
    const result = await request(`/api/chats/${encodeURIComponent(chatId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ text, after: lastSeq() }),
    });
    if (chatId !== state.chatId) return;
    applySendResult(result, text);
  } catch (error) {
    renderMessages();
    showError(error.message);
    nodes.input.value = text;
  } finally {
    state.sending = false;
    updateComposer();
    nodes.input.focus();
  }
}

function applySendResult(result, text) {
  mergeNew(result.messages);
  state.chat = result.chat;
  const turn = result.turn;
  if (turn.out_of_scope) {
    state.ephemeral.push({ role: "user", content: text, ephemeral: true }, { role: "assistant", content: turn.reply, ephemeral: true, trace: turn.trace, alerts: turn.alerts });
  }
  renderMessages();
  scrollToBottom();
  const last = state.entries[state.entries.length - 1];
  if (turn.out_of_scope) showAudit(turn.trace, true, null, turn.alerts);
  else if (last) showAudit(last.trace, false, last.thread, last.alerts, threadColors(state.entries).get(last.thread.id));
  loadChats();
}

// --- Actualización automática -----------------------------------------------------------------

async function poll() {
  if (state.chatId && !state.sending) await pollChat();
  await loadChats();
}

async function pollChat() {
  const chatId = state.chatId;
  try {
    const page = await request(`/api/chats/${encodeURIComponent(chatId)}/messages?after=${lastSeq()}`);
    if (chatId !== state.chatId || state.sending) return;
    const stick = isNearBottom();
    const added = mergeNew(page.messages);
    const changed = added || page.pending !== state.pending || page.chat.writable !== state.chat.writable;
    state.chat = page.chat;
    state.pending = page.pending;
    if (!changed) return;
    renderChatHeader();
    renderMessages();
    if (stick) scrollToBottom();
    else if (added) showNewMessages(added);
  } catch {
    // Un fallo puntual de la consulta no interrumpe la auditoría; se reintenta.
  }
}

function showNewMessages(count) {
  state.unseen += count;
  nodes.newMessages.textContent = `↓ ${state.unseen} mensajes nuevos`;
  nodes.newMessages.hidden = false;
}

// --- Eventos ----------------------------------------------------------------------------------

nodes.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = nodes.input.value.trim();
  if (!text || !state.chat?.writable || state.sending) return;
  nodes.input.value = "";
  nodes.input.style.height = "auto";
  sendMessage(text);
});

nodes.input.addEventListener("input", () => {
  nodes.input.style.height = "auto";
  nodes.input.style.height = `${Math.min(nodes.input.scrollHeight, 130)}px`;
});

nodes.input.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  nodes.composer.requestSubmit();
});

nodes.messages.addEventListener("scroll", () => {
  if (nodes.messages.scrollTop < TOP_LOAD_PX) loadOlder();
  if (isNearBottom()) {
    state.unseen = 0;
    nodes.newMessages.hidden = true;
  }
});

nodes.newMessages.addEventListener("click", scrollToBottom);

nodes.newChat.addEventListener("click", async () => {
  nodes.newChat.disabled = true;
  try {
    const chat = await request("/api/chats", { method: "POST" });
    if (state.filter && state.filter !== chat.channel) {
      state.filter = "";
      renderFilters();
    }
    await loadChats();
    await openChat(chat.id);
    nodes.input.focus();
  } catch (error) {
    showError(error.message);
  } finally {
    nodes.newChat.disabled = false;
  }
});

nodes.release.addEventListener("click", async () => {
  try {
    state.chat = await request(`/api/chats/${encodeURIComponent(state.chatId)}/release`, { method: "POST" });
    updateComposer();
    loadChats();
  } catch (error) {
    showError(error.message);
  }
});

// --- Inicio ----------------------------------------------------------------------------------

async function init() {
  try {
    state.config = await request("/api/config");
  } catch (error) {
    showError(error.message);
  }
  renderFilters();
  await loadChats();
  const saved = remembered();
  if (saved && state.chats.some((chat) => chat.id === saved)) await openChat(saved);
  setInterval(poll, state.config.poll_seconds * 1000);
}

init();
