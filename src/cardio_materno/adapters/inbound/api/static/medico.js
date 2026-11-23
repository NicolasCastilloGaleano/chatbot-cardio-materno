// Apartado del profesional de salud (HU-16, ADR 0022). Todo el texto se pinta con textContent:
// los mensajes de la persona y el borrador nunca se interpretan como HTML.
"use strict";

const KEY_STORAGE = "cardio-materno.clinician-key";
const POLL_MS = 5000;
const REASONS = { "sin información": "La base no tenía información", "cierre de la indagación": "Se cerró la indagación sin respuesta" };
const DOMAINS = { cardiovascular: "Cardiovascular", materno_infantil: "Materno-infantil", ninguno: "Sin dominio" };
const ROLES = { user: "Persona", assistant: "Asistente", clinician: "Profesional de salud" };
const IN_CONTACT = "en_contacto";
const SENT_TEXT = "Respuesta enviada a la persona. El caso quedó cerrado.";
const WINDOW_CLOSED_TEXT = "Ventana cerrada: no se puede escribir por WhatsApp (pasaron 24 horas desde el último mensaje de la persona o no hay dirección guardada). Si la persona vuelve a escribir, se abre de nuevo.";
const CLOSED_TEXT = "Contacto cerrado. El asistente vuelve a responder a la persona.";

const nodes = {
  keyForm: document.getElementById("key-form"),
  keyInput: document.getElementById("key-input"),
  keyError: document.getElementById("key-error"),
  workspace: document.getElementById("clinician-workspace"),
  list: document.getElementById("case-list"),
  detail: document.getElementById("case-detail"),
  logout: document.getElementById("logout"),
};
const state = { key: readKey(), selected: null, timer: null };

function readKey() {
  try { return sessionStorage.getItem(KEY_STORAGE) || ""; } catch { return ""; }
}

function storeKey(key) {
  try { key ? sessionStorage.setItem(KEY_STORAGE, key) : sessionStorage.removeItem(KEY_STORAGE); } catch { /* sin almacenamiento */ }
}

async function api(path, options = {}) {
  const headers = { "X-Clinician-Key": state.key, ...(options.body ? { "Content-Type": "application/json" } : {}) };
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) { showKeyForm("La clave no es válida."); throw new Error("401"); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "No se pudo completar la acción.");
  return data;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function showKeyForm(error) {
  clearInterval(state.timer);
  storeKey("");
  state.key = "";
  nodes.workspace.hidden = true;
  nodes.keyForm.hidden = false;
  nodes.keyError.hidden = !error;
  nodes.keyError.textContent = error || "";
  nodes.keyInput.focus();
}

function start() {
  nodes.keyForm.hidden = true;
  nodes.workspace.hidden = false;
  loadCases();
  state.timer = setInterval(loadCases, POLL_MS);
}

async function loadCases() {
  try {
    const cases = await api("/api/clinician/cases");
    renderCases(cases);
    const selected = cases.find((item) => item.id === state.selected);
    if (selected && selected.status === IN_CONTACT) refreshConversation(selected.id);
  } catch (error) {
    if (error.message !== "401") nodes.list.replaceChildren(element("p", error.message, "notice error"));
  }
}

function renderCases(cases) {
  if (!cases.length) {
    nodes.list.replaceChildren(element("p", "No hay casos pendientes.", "muted"));
    return;
  }
  nodes.list.replaceChildren(...cases.map(caseItem));
}

function caseItem(item) {
  const button = element("button", null, `case-item${item.id === state.selected ? " selected" : ""}`);
  button.type = "button";
  const title = item.snapshot.query || item.snapshot.summary || "Consulta sin detalle";
  button.append(
    element("strong", title),
    element("span", `${DOMAINS[item.snapshot.domain] || item.snapshot.domain} · ${item.channel_label}${item.status === IN_CONTACT ? " · en contacto" : ""}`),
    element("span", `Abierto ${formatDate(item.created_at)} · vence ${formatDate(item.expires_at)}`),
  );
  button.addEventListener("click", () => openCase(item.id));
  return button;
}

async function openCase(caseId) {
  state.selected = caseId;
  nodes.detail.replaceChildren(element("p", "Cargando el caso…", "muted"));
  try {
    renderDetail(await api(`/api/clinician/cases/${encodeURIComponent(caseId)}`));
    loadCases();
  } catch (error) {
    if (error.message !== "401") nodes.detail.replaceChildren(element("p", error.message, "notice error"));
  }
}

function renderDetail(item) {
  const snapshot = item.snapshot;
  nodes.detail.replaceChildren(
    element("p", `CASO ${item.id.slice(0, 8)} · ${item.channel_label}`, "eyebrow"),
    element("h2", snapshot.query || "Consulta sin detalle"),
    summarySection(item),
    conversationSection(item.messages || []),
    item.status === IN_CONTACT ? contactSection(item) : draftSection(item),
  );
}

// En contacto directo solo se cambia la conversación: lo que el profesional escribe se mantiene.
async function refreshConversation(caseId) {
  try {
    const item = await api(`/api/clinician/cases/${encodeURIComponent(caseId)}`);
    const current = nodes.detail.querySelector(".conversation-section");
    if (state.selected !== caseId || !current) return;
    if (item.status !== IN_CONTACT) { renderDetail(item); return; }
    const scroller = current.querySelector(".conversation");
    const atBottom = !scroller || scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 8;
    const fresh = conversationSection(item.messages || []);
    current.replaceWith(fresh);
    const list = fresh.querySelector(".conversation");
    if (list && atBottom) list.scrollTop = list.scrollHeight;
  } catch { /* el siguiente sondeo lo intenta de nuevo */ }
}

function summarySection(item) {
  const snapshot = item.snapshot;
  const facts = element("dl", null, "facts");
  const rows = [
    ["Motivo", REASONS[snapshot.reason] || snapshot.reason],
    ["Dominio", DOMAINS[snapshot.domain] || snapshot.domain],
    ["Resumen", snapshot.summary || "—"],
    ["Síntomas", snapshot.symptoms.join(", ") || "—"],
    ["Signos", snapshot.signs.join(", ") || "—"],
    ["Turnos sin respuesta", String(item.gap_count)],
    ["Vence", formatDate(item.expires_at)],
  ];
  for (const [label, value] of rows) facts.append(element("dt", label), element("dd", value));
  const section = element("div", null, "case-section");
  section.append(element("h3", "Resumen clínico (sin datos de identificación)"), facts);
  return section;
}

function conversationSection(messages) {
  const list = element("div", null, "conversation");
  for (const message of messages) {
    const row = element("div", null, `bubble-row ${message.role}`);
    row.append(element("div", message.content, "bubble"), element("span", `${ROLES[message.role] || message.role} · ${formatDate(message.created_at)}`, "bubble-meta"));
    list.append(row);
  }
  const section = element("div", null, "case-section conversation-section");
  section.append(element("h3", "Conversación"), messages.length ? list : element("p", "Sin mensajes.", "muted"));
  requestAnimationFrame(() => { list.scrollTop = list.scrollHeight; });
  return section;
}

function draftSection(item) {
  const section = element("div", null, "case-section");
  const box = element("div", null, "draft-box");
  const text = element("textarea");
  text.value = item.draft || "";
  text.placeholder = "Escribe aquí la respuesta, o genera un borrador.";
  text.setAttribute("aria-label", "Respuesta para la persona");
  box.append(element("p", "BORRADOR SIN RESPALDO DE LA BASE · REVÍSALO ANTES DE ENVIAR", "draft-label"), text);
  const notice = element("p", draftNotice(item), "notice");
  notice.hidden = !draftNotice(item);
  section.append(element("h3", "Respuesta"), box, actions(item, text, notice), notice);
  if (item.draft_note) section.prepend(noteBox(item.draft_note));
  return section;
}

// Nota del modelo para el profesional: solo se lee aquí y nunca se envía a la persona.
function noteBox(note) {
  const box = element("div", null, "note-box");
  box.append(element("p", "NOTA PARA EL PROFESIONAL · SIN RESPALDO DE LA BASE · NO SE ENVÍA", "draft-label"), element("p", note, "note-text"));
  return box;
}

function draftNotice(item) {
  if (!item.deliverable) return item.channel === "whatsapp" ? WINDOW_CLOSED_TEXT : "No se puede responder por el canal de esta persona.";
  if (item.draft_status === "fallido") return "No se pudo generar el borrador. Puedes escribir la respuesta y enviarla con Modificar.";
  if (item.channel === "whatsapp") return "La respuesta saldrá por el número del proyecto en unos segundos, con la etiqueta «Profesional de salud». Tu número nunca se muestra.";
  return "";
}

function actions(item, text, notice) {
  const row = element("div", null, "actions");
  const ready = item.draft_status === "listo";
  const draft = ready
    ? actionButton("Regenerar borrador", () => run(`/api/clinician/cases/${item.id}/redraft`, null, notice, true))
    : actionButton("Generar borrador", () => run(`/api/clinician/cases/${item.id}/draft`, null, notice, true));
  if (ready) draft.title = "Reemplaza el borrador y la nota por unos nuevos. Si lo editaste, tu texto se pierde.";
  const approve = actionButton("Aprobar borrador", () => run(`/api/clinician/cases/${item.id}/approve`, null, notice, false));
  approve.disabled = !ready || !item.deliverable || text.value.trim() !== (item.draft || "").trim();
  const modify = actionButton("Enviar mi versión", () => run(`/api/clinician/cases/${item.id}/modify`, { text: text.value }, notice, false));
  modify.disabled = !item.deliverable;
  text.addEventListener("input", () => { approve.disabled = !ready || !item.deliverable || text.value.trim() !== (item.draft || "").trim(); });
  const contact = actionButton("Contacto directo", () => run(`/api/clinician/cases/${item.id}/contact`, null, notice, true));
  contact.disabled = !item.deliverable;
  contact.title = "Escribirle a la persona en su mismo chat; el asistente deja de responder mientras dure.";
  row.append(draft, approve, modify, contact);
  return row;
}

function contactSection(item) {
  const section = element("div", null, "case-section");
  const text = element("textarea", null, "contact-input");
  text.placeholder = "Escribe tu mensaje para la persona.";
  text.setAttribute("aria-label", "Mensaje para la persona");
  const notice = element("p", null, "notice");
  notice.hidden = true;
  const send = actionButton("Enviar", () => sendContactMessage(item.id, text, notice));
  send.disabled = !item.deliverable;
  text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) send.click();
  });
  const close = actionButton("Cerrar contacto", () => run(`/api/clinician/cases/${item.id}/close`, null, notice, false, CLOSED_TEXT));
  const row = element("div", null, "actions");
  row.append(send, close);
  section.append(
    element("h3", "Contacto directo"),
    item.deliverable ? "" : element("p", WINDOW_CLOSED_TEXT, "notice error"),
    element("p", "La persona lee tus mensajes como «Profesional de salud» en su mismo chat. Mientras dure el contacto el asistente no le responde, pero sus avisos de alarma siguen saliendo de inmediato. Ctrl+Enter envía.", "muted"),
    text, row, notice,
  );
  return section;
}

async function sendContactMessage(caseId, text, notice) {
  const message = text.value.trim();
  if (!message) return;
  notice.hidden = true;
  try {
    await api(`/api/clinician/cases/${caseId}/messages`, { method: "POST", body: JSON.stringify({ text: message }) });
    text.value = "";
    refreshConversation(caseId);
  } catch (error) {
    if (error.message === "401") return;
    notice.hidden = false;
    notice.className = "notice error";
    notice.textContent = error.message;
  }
}

function actionButton(label, handler) {
  const button = element("button", label, "quiet-button");
  button.type = "button";
  button.addEventListener("click", handler);
  return button;
}

async function run(path, body, notice, reopen, doneText = SENT_TEXT) {
  notice.hidden = false;
  notice.className = "notice";
  notice.textContent = "Procesando…";
  try {
    const item = await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
    if (reopen) { openCase(item.id); return; }
    state.selected = null;
    nodes.detail.replaceChildren(element("p", doneText, "notice"));
    loadCases();
  } catch (error) {
    if (error.message === "401") return;
    notice.className = "notice error";
    notice.textContent = error.message;
  }
}

nodes.keyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.key = nodes.keyInput.value.trim();
  storeKey(state.key);
  nodes.keyInput.value = "";
  start();
});
nodes.logout.addEventListener("click", () => showKeyForm(""));

if (state.key) start(); else showKeyForm("");
