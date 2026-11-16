// Vista ciudadana (HU-16, ADR 0022): la conversación propia de una persona.
// Solo usa /api/me: nunca recibe trazas ni chats de otras personas. Todo texto se inserta
// con textContent; los enlaces de las fuentes solo se abren si son http(s).

const $ = (selector) => document.querySelector(selector);
const nodes = {
  welcome: $("#welcome"),
  declined: $("#declined"),
  chat: $("#chat"),
  accept: $("#accept"),
  decline: $("#decline"),
  reconsider: $("#reconsider"),
  welcomeError: $("#welcome-error"),
  privacyLine: $("#privacy-line"),
  newConversation: $("#new-conversation"),
  messages: $("#messages"),
  composer: $("#composer"),
  input: $("#message-input"),
  send: $("#send-button"),
  researchOption: $("#research-option"),
  researchCheck: $("#research-check"),
  researchText: $("#research-text"),
  emergencyOpen: $("#emergency-open"),
  emergencyDialog: $("#emergency-dialog"),
  emergencyTitle: $("#emergency-title"),
  emergencyLines: $("#emergency-lines"),
  emergencyDisclaimer: $("#emergency-disclaimer"),
  emergencyCall: $("#emergency-call"),
  emergencyClose: $("#emergency-close"),
  privacyOpen: $("#privacy-open"),
  privacyDialog: $("#privacy-dialog"),
  privacyResearch: $("#privacy-research"),
  privacyResearchCheck: $("#privacy-research-check"),
  privacyResearchText: $("#privacy-research-text"),
  privacyError: $("#privacy-error"),
  privacySave: $("#privacy-save"),
  privacyWithdraw: $("#privacy-withdraw"),
  privacyClose: $("#privacy-close"),
};

const SESSION_KEY = "cardio-materno:mi-conversacion";
const STARTED_KEY = "cardio-materno:bienvenida-vista";
const ACCEPTED = "aceptado";
const REJECTED = "rechazado";
const LONG_WAIT_MS = 9000;
const WAIT_TEXT = "Estoy revisando tu mensaje…";
const LONG_WAIT_TEXT = "Sigo buscando en la información del proyecto. Puede tardar cerca de un minuto.";
const SUGGESTIONS = [
  "¿Qué alimentos ayudan a controlar la presión arterial?",
  "Estoy embarazada, ¿cada cuánto debo ir a control?",
  "¿Cómo sé si mi bebé está recibiendo suficiente leche?",
];
const ALERT_TITLES = { urgencia: "Busca atención ahora", prioritaria: "Consulta pronto" };
// Un aviso de acceso es un texto fijo del proyecto: no sale de la base de conocimiento.
const ACCESS_LABELS = { administrativo: "Trámites y acceso · no es una recomendación médica", clinico: "Seguimiento · texto fijo del proyecto" };

const state = { session: null, consentRequired: false, researchOffered: false, research: false, sending: false, empty: true };

// --- Utilidades -----------------------------------------------------------------------------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function stored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Sin almacenamiento local la página funciona igual; solo no recuerda la conversación.
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  } catch {
    throw new Error("No hay conexión con el servicio. Revisa tu conexión e intenta de nuevo.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "No se pudo completar la solicitud.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function show(view) {
  for (const name of ["welcome", "declined", "chat"]) nodes[name].hidden = name !== view;
  nodes.newConversation.hidden = view !== "chat";
}

function formatTime(iso) {
  const date = iso ? new Date(iso) : new Date();
  return date.toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" });
}

function scrollToEnd() {
  nodes.messages.scrollTop = nodes.messages.scrollHeight;
}

// --- Mensajes -------------------------------------------------------------------------------

function safeLink(source) {
  const label = `${source.title}${source.version ? ` (${source.version})` : ""}`;
  if (!/^https?:\/\//i.test(source.url || "")) return el("span", "", label);
  const link = el("a", "", label);
  link.href = source.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function sourcesBlock(message) {
  if (message.sources?.length) {
    const details = el("details", "sources");
    const count = message.sources.length;
    details.append(el("summary", "", count === 1 ? "Ver la fuente" : `Ver las ${count} fuentes`));
    const list = el("ol");
    for (const source of message.sources) {
      const item = el("li");
      item.append(el("span", "entity", source.entity), safeLink(source));
      list.append(item);
    }
    details.append(list);
    return details;
  }
  if (message.grounded) return el("p", "basis", "Basado en la base de conocimiento del proyecto.");
  return null;
}

function alertCard(message) {
  const urgent = message.kind === "urgencia";
  const card = el("div", `alert-card ${urgent ? "urgent" : "priority"}`);
  card.setAttribute("role", urgent ? "alert" : "status");
  card.append(el("div", "alert-head", `${urgent ? "⚠" : "●"} ${ALERT_TITLES[message.kind]}`), el("div", "alert-body", message.content));
  if (urgent) {
    const call = el("a", "button danger small", "Llamar al 123");
    call.href = "tel:123";
    card.append(call);
  }
  return card;
}

// Separa el aviso de acceso del resto de la respuesta para mostrarlo como una tarjeta
// distinta de la orientación respaldada por la base.
function splitAccessNotice(message) {
  const notice = message.access_notice;
  const at = notice?.text ? message.content.indexOf(notice.text) : -1;
  if (at < 0) return { content: message.content, notice: null };
  const before = message.content.slice(0, at).replace(/[^\n]*\(no es una recomendación médica\):\s*$/, "");
  const after = message.content.slice(at + notice.text.length);
  return { content: [before.trim(), after.trim()].filter(Boolean).join("\n\n"), notice };
}

function accessCard(notice) {
  const card = el("div", "access-card");
  card.append(el("span", "access-label", ACCESS_LABELS[notice.kind] || ACCESS_LABELS.administrativo), el("p", "", notice.text));
  if (notice.basis?.length) card.append(el("p", "access-basis", `Sustento: ${notice.basis.join("; ")}`));
  return card;
}

function messageRow(message) {
  const row = el("div", `row ${message.role}${message.saved === false ? " unsaved" : ""}`);
  const isAlert = message.role === "assistant" && ALERT_TITLES[message.kind];
  const parts = splitAccessNotice(message);
  const shown = { ...message, content: parts.content };
  if (parts.content) row.append(isAlert ? alertCard(shown) : el("div", "bubble", parts.content));
  // Las fuentes van pegadas a la respuesta que respaldan, antes del aviso de acceso.
  if (message.role === "assistant") {
    const sources = sourcesBlock(message);
    if (sources) row.append(sources);
  }
  if (parts.notice) row.append(accessCard(parts.notice));
  row.append(el("span", "stamp", formatTime(message.created_at)));
  return row;
}

function addMessage(message) {
  if (state.empty) {
    nodes.messages.replaceChildren();
    state.empty = false;
  }
  nodes.messages.append(messageRow(message));
  scrollToEnd();
}

function renderStarter() {
  state.empty = true;
  const starter = el("div", "starter");
  starter.append(el("h2", "", "¿En qué te puedo orientar hoy?"), el("p", "", "Cuéntame tu duda o lo que sientes. También puedes empezar con una de estas preguntas:"));
  const list = el("div", "suggestions");
  for (const text of SUGGESTIONS) {
    const chip = el("button", "suggestion", text);
    chip.type = "button";
    chip.addEventListener("click", () => sendMessage(text));
    list.append(chip);
  }
  starter.append(list);
  nodes.messages.replaceChildren(starter);
}

function typingRow() {
  const row = el("div", "row assistant typing");
  row.setAttribute("role", "status");
  const bubble = el("div", "bubble");
  const dots = el("span", "dots");
  dots.append(el("i"), el("i"), el("i"));
  bubble.append(dots);
  const label = el("span", "stamp", WAIT_TEXT);
  row.append(bubble, label);
  const timer = setTimeout(() => { label.textContent = LONG_WAIT_TEXT; }, LONG_WAIT_MS);
  return { row, stop: () => { clearTimeout(timer); row.remove(); } };
}

function errorNotice(message, retryText) {
  const notice = el("div", "notice error");
  notice.setAttribute("role", "alert");
  notice.append(el("span", "", message));
  if (retryText) {
    const retry = el("button", "button ghost small", "Reintentar");
    retry.type = "button";
    retry.addEventListener("click", () => { notice.remove(); sendMessage(retryText, true); });
    notice.append(retry);
  }
  nodes.messages.append(notice);
  scrollToEnd();
}

// --- Enviar ---------------------------------------------------------------------------------

function setSending(sending) {
  state.sending = sending;
  nodes.send.disabled = sending || !nodes.input.value.trim();
  nodes.input.disabled = sending;
}

async function sendMessage(text, isRetry = false) {
  if (state.sending) return;
  if (!isRetry) addMessage({ role: "user", content: text });
  setSending(true);
  const typing = typingRow();
  nodes.messages.append(typing.row);
  scrollToEnd();
  try {
    const turn = await request(`/api/me/sessions/${encodeURIComponent(state.session)}/messages`, { method: "POST", body: JSON.stringify({ text }) });
    typing.stop();
    addMessage({ role: "assistant", content: turn.reply, kind: turn.kind, grounded: turn.grounded, sources: turn.sources, access_notice: turn.access_notice, saved: turn.saved });
  } catch (error) {
    typing.stop();
    if (error.status === 404) return restart();
    if (error.status === 403) return showWelcome(true);
    errorNotice(error.message, text);
  } finally {
    setSending(false);
    nodes.input.focus();
  }
}

// --- Sesión y consentimiento ----------------------------------------------------------------

async function ensureSession() {
  const saved = stored(SESSION_KEY);
  if (saved) {
    try {
      return await request(`/api/me/sessions/${encodeURIComponent(saved)}`);
    } catch (error) {
      if (error.status !== 404) throw error;
    }
  }
  const created = await request("/api/me/sessions", { method: "POST" });
  store(SESSION_KEY, created.session);
  return created;
}

function showWelcome(required) {
  nodes.decline.hidden = !required;
  nodes.researchOption.hidden = !state.researchOffered;
  nodes.accept.textContent = required ? "Acepto y quiero empezar" : "Empezar";
  show("welcome");
  nodes.accept.focus();
}

async function openChat() {
  show("chat");
  const page = await request(`/api/me/sessions/${encodeURIComponent(state.session)}/messages`);
  if (page.messages.length) {
    state.empty = false;
    nodes.messages.replaceChildren(...page.messages.map(messageRow));
    scrollToEnd();
  } else {
    renderStarter();
  }
  nodes.input.focus();
}

async function decide(accepted) {
  nodes.welcomeError.hidden = true;
  nodes.accept.disabled = nodes.decline.disabled = true;
  try {
    if (state.consentRequired) {
      await request(`/api/me/sessions/${encodeURIComponent(state.session)}/consent`, { method: "POST", body: JSON.stringify({ accepted }) });
    }
    // La autorización para informes es aparte y opcional: sin marcarla, la atención es la misma.
    if (state.researchOffered) {
      const research = accepted && nodes.researchCheck.checked;
      await request(`/api/me/sessions/${encodeURIComponent(state.session)}/research`, { method: "POST", body: JSON.stringify({ accepted: research }) });
      state.research = research;
    }
    store(STARTED_KEY, "1");
    if (accepted) await openChat();
    else show("declined");
  } catch (error) {
    nodes.welcomeError.textContent = error.message;
    nodes.welcomeError.hidden = false;
  } finally {
    nodes.accept.disabled = nodes.decline.disabled = false;
  }
}

async function restart() {
  store(SESSION_KEY, null);
  await init();
}

async function init() {
  try {
    const session = await ensureSession();
    state.session = session.session;
    state.consentRequired = session.consent_required;
    state.researchOffered = Boolean(session.research_text);
    state.research = session.research === ACCEPTED;
    nodes.researchText.textContent = session.research_text || "";
    nodes.privacyResearchText.textContent = session.research_text || "";
    nodes.privacyOpen.hidden = !(state.researchOffered || state.consentRequired);
    if (session.consent === REJECTED && session.consent_required) return show("declined");
    const ready = session.consent_required ? session.consent === ACCEPTED : stored(STARTED_KEY) === "1";
    if (ready) await openChat();
    else showWelcome(session.consent_required);
  } catch (error) {
    showWelcome(false);
    nodes.accept.disabled = true;
    nodes.welcomeError.textContent = error.message;
    nodes.welcomeError.hidden = false;
  }
}

// --- Emergencias: información pública, sin consentimiento y sin enviar nada -------------------

// La hoja ya trae el contenido en la página: funciona aunque el servicio no responda.
async function loadEmergencyInfo() {
  try {
    const info = await request("/api/public/emergency");
    nodes.emergencyTitle.textContent = info.title;
    nodes.emergencyLines.replaceChildren(...info.lines.map((line) => el("li", "", line)));
    nodes.emergencyDisclaimer.textContent = info.disclaimer;
    nodes.emergencyCall.href = `tel:${info.phone}`;
    nodes.emergencyCall.textContent = `Llamar al ${info.phone}`;
  } catch {
    // Se conserva el contenido fijo de la página.
  }
}

nodes.emergencyOpen.addEventListener("click", (event) => {
  if (typeof nodes.emergencyDialog.showModal !== "function") return;
  event.preventDefault();
  nodes.emergencyDialog.showModal();
});
nodes.emergencyClose.addEventListener("click", () => nodes.emergencyDialog.close());

// --- Mis datos: cambiar la autorización para informes o retirar la aceptación ------------------

function openPrivacy() {
  if (typeof nodes.privacyDialog.showModal !== "function") return;
  nodes.privacyError.hidden = true;
  nodes.privacyResearch.hidden = nodes.privacySave.hidden = !state.researchOffered;
  nodes.privacyResearchCheck.checked = state.research;
  nodes.privacyWithdraw.hidden = !state.consentRequired;
  nodes.privacyDialog.showModal();
}

async function changePrivacy(path, accepted) {
  nodes.privacyError.hidden = true;
  try {
    await request(`/api/me/sessions/${encodeURIComponent(state.session)}/${path}`, { method: "POST", body: JSON.stringify({ accepted }) });
    return true;
  } catch (error) {
    nodes.privacyError.textContent = error.message;
    nodes.privacyError.hidden = false;
    return false;
  }
}

nodes.privacyOpen.addEventListener("click", openPrivacy);
nodes.privacyClose.addEventListener("click", () => nodes.privacyDialog.close());
nodes.privacySave.addEventListener("click", async () => {
  const accepted = nodes.privacyResearchCheck.checked;
  if (!(await changePrivacy("research", accepted))) return;
  state.research = accepted;
  nodes.privacyDialog.close();
});
// Retirar la aceptación retira también la autorización para informes (lo hace el servidor).
nodes.privacyWithdraw.addEventListener("click", async () => {
  if (!(await changePrivacy("consent", false))) return;
  state.research = false;
  nodes.privacyDialog.close();
  show("declined");
});

// --- Eventos --------------------------------------------------------------------------------

nodes.accept.addEventListener("click", () => decide(true));
nodes.decline.addEventListener("click", () => decide(false));
nodes.reconsider.addEventListener("click", () => showWelcome(true));
nodes.newConversation.addEventListener("click", () => {
  if (!state.sending) restart();
});

nodes.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = nodes.input.value.trim();
  if (!text || state.sending) return;
  nodes.input.value = "";
  nodes.input.style.height = "auto";
  sendMessage(text);
});

nodes.input.addEventListener("input", () => {
  nodes.input.style.height = "auto";
  nodes.input.style.height = `${Math.min(nodes.input.scrollHeight, 140)}px`;
  nodes.send.disabled = state.sending || !nodes.input.value.trim();
});

nodes.input.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  nodes.composer.requestSubmit();
});

nodes.send.disabled = true;
loadEmergencyInfo();
init();
