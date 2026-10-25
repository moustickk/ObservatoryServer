/* Interface locale de l'observatoire.
 *
 * Aucune dependance : elle doit fonctionner hors ligne, sur la machine de
 * l'observatoire, sans etape de build.
 *
 * Deux sources :
 *   /api/health          etat du toit, liaison, monture, alarme, agent
 *   /api/safety/status   valeurs meteo detaillees
 *
 * La configuration est construite a partir de /api/config/schema : ajouter
 * un reglage cote serveur suffit a le faire apparaitre ici.
 */

const POLL_MS = 2000;

const STATE_LABELS = {
  OPENED: "Ouvert",
  OPENING: "Ouverture…",
  CLOSED: "Fermé",
  CLOSING: "Fermeture…",
  STOPPED: "Arrêté",
  ERROR: "Défaut",
  UNKNOWN: "Inconnu",
};

const STATE_CLASS = {
  OPENED: "opened",
  OPENING: "moving",
  CLOSED: "closed",
  CLOSING: "moving",
  STOPPED: "stopped",
  ERROR: "error",
  UNKNOWN: "error",
};

const GROUP_LABELS = {
  general: "Général",
  toit: "Toit",
  monture: "Monture",
  meteo: "Météo",
  arduino: "Arduino",
};

// Une couleur par groupe de réglages, pour retrouver la section d'un coup.
const GROUP_COLORS = {
  general: "#8b9bab",
  toit: "#388bfd",
  monture: "#a371f7",
  meteo: "#3fb950",
  arduino: "#39c5cf",
};

const $ = (id) => document.getElementById(id);

let polling = false;
let schema = null;

// -- utilitaires ---------------------------------------------------------

async function api(path, options) {
  const response = await fetch(path, options);

  let data = null;
  const text = await response.text();

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { message: text };
  }

  return { ok: response.ok, status: response.status, data };
}

function show(element, message) {
  element.textContent = message;
  element.classList.remove("hidden");
}

function hide(element) {
  element.classList.add("hidden");
}

function number(value, unit) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return `${value} ${unit}`;
}

// -- etat du toit --------------------------------------------------------

function renderDome(dome, agentEnabled) {
  const state = dome.state || "UNKNOWN";

  const badge = $("state");
  badge.textContent = STATE_LABELS[state] || state;
  badge.className = `badge ${STATE_CLASS[state] || "error"}`;

  const position = typeof dome.position === "number" ? dome.position : -1;
  $("position-fill").style.width = position >= 0 ? `${position}%` : "0%";
  $("position-text").textContent = position >= 0 ? `${position} %` : "?";

  const link = dome.link || {};
  $("dome-link").textContent = link.connected
    ? `${link.description}${link.stale ? " (sans réponse)" : ""}`
    : `hors ligne${link.last_error ? ` — ${link.last_error}` : ""}`;

  const mount = dome.mount || {};
  let mountText = "—";

  if (mount.at_park === true) {
    mountText = `${mount.description} — parquée`;
  } else if (mount.at_park === false) {
    mountText = `${mount.description} — NON parquée`;
  } else {
    mountText = `${mount.description || "?"} — état inconnu`;
  }

  if (mount.stale) {
    mountText += " (mesure périmée)";
  }

  $("mount").textContent = mountText;

  const alarm = dome.alarm;
  if (alarm) {
    show($("alarm"), `${alarm.code} — ${alarm.message} (depuis ${alarm.since})`);
  } else {
    hide($("alarm"));
  }

  const notice = $("notice");
  if (agentEnabled === false) {
    show(notice, "Agent de sauvegarde DÉSACTIVÉ : aucune fermeture automatique.");
  } else if (notice.textContent.startsWith("Agent")) {
    hide(notice);
  }

  $("agent-state").textContent =
    agentEnabled === false
      ? "Agent de sauvegarde désactivé : aucune fermeture automatique."
      : "Agent de sauvegarde actif : ferme le toit si la météo devient UNSAFE.";
}

function renderHeader(health) {
  const mode = $("mode");
  mode.textContent = health.simulation ? "simulation" : "matériel réel";
  mode.className = `tag ${health.simulation ? "" : "on"}`;

  const link = (health.dome || {}).link || {};
  const tag = $("link");
  tag.textContent = link.connected ? "liaison ok" : "liaison perdue";
  tag.className = `tag ${link.connected ? "on" : "off"}`;

  $("updated").textContent = new Date().toLocaleTimeString("fr-FR");
  $("footer-version").textContent = `v${health.version || "?"}`;
}

// -- meteo ---------------------------------------------------------------

function renderWeather(status) {
  const safe = status.safe === true;

  const badge = $("safe");
  badge.textContent = safe ? "SAFE" : "UNSAFE";
  badge.className = `badge ${safe ? "safe" : "unsafe"}`;

  // La carte entière change de couleur : l'alerte se voit sans lire.
  $("weather-card").classList.toggle("unsafe", !safe);

  $("weather-status").textContent = status.status || "—";

  const weather = status.weather || {};

  $("w-wind").textContent = number(weather.wind, "km/h");
  $("w-gust").textContent = number(weather.wind_gust, "km/h");
  $("w-rain").textContent = number(weather.rain_probability, "%");
  $("w-mm").textContent = number(weather.rain_mm, "mm");
  $("w-clouds").textContent = number(weather.clouds, "%");
  $("w-temp").textContent = number(weather.temperature, "°C");

  const age = status.data_age_minutes;
  $("w-age").textContent =
    age === null || age === undefined || age < 0 ? "—" : `${age} min`;

  $("w-last").textContent = status.last_weather_update || "—";
}

// -- rafraichissement ----------------------------------------------------

async function refresh() {
  if (polling) {
    return;
  }

  polling = true;

  try {
    const health = await api("/api/health");
    if (!health.ok) {
      throw new Error(`/api/health : ${health.status}`);
    }

    renderHeader(health.data);
    renderDome(health.data.dome || {}, (health.data.safety || {}).agent_enabled);

    const safety = await api("/api/safety/status");
    if (safety.ok) {
      renderWeather(safety.data);
    }

  } catch (error) {
    $("updated").textContent = `hors ligne (${error.message})`;
  } finally {
    polling = false;
  }
}

// -- commandes -----------------------------------------------------------

async function command(path, label) {
  hide($("action-error"));

  if (!confirm(`${label} ?`)) {
    return;
  }

  try {
    const result = await api(path, { method: "POST" });

    if (!result.ok) {
      const data = result.data || {};
      show(
        $("action-error"),
        data.message || data.detail || `Commande refusée (${result.status})`,
      );
    }
  } catch (error) {
    show($("action-error"), error.message);
  }

  refresh();
}

// -- configuration -------------------------------------------------------

function fieldElement(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";

  const label = document.createElement("label");
  label.textContent = item.key;
  label.htmlFor = `cfg-${item.key}`;

  let input;

  if (item.type === "bool") {
    wrapper.classList.add("check");
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = item.value === true;
    wrapper.append(input, label);
  } else {
    if (item.choices) {
      input = document.createElement("select");
      for (const choice of item.choices) {
        const option = document.createElement("option");
        option.value = choice;
        option.textContent = choice;
        input.append(option);
      }
      input.value = item.value;
    } else {
      input = document.createElement("input");
      input.type = item.type === "int" || item.type === "float" ? "number" : "text";
      if (item.type === "float") {
        input.step = "any";
      }
      input.value = item.value;
    }

    wrapper.append(label);

    // Le pilote de monture se choisit dans une liste : on evite de taper un
    // ProgID au clavier et de se tromper d'une lettre.
    if (item.key === "telescope_driver") {
      const row = document.createElement("div");
      row.className = "inline";
      row.append(input);

      const scan = document.createElement("button");
      scan.type = "button";
      scan.className = "scan";
      scan.textContent = "Scanner";
      scan.addEventListener("click", () => scanDrivers(input, scan, wrapper));
      row.append(scan);

      wrapper.append(row);
    } else {
      wrapper.append(input);
    }
  }

  input.id = `cfg-${item.key}`;
  input.dataset.key = item.key;
  input.dataset.type = item.type;
  input.dataset.initial =
    item.type === "bool" ? String(item.value === true) : String(item.value);

  // Identifiants Alpaca : visibles et copiables, mais pas modifiables.
  // Les changer ferait apparaitre un second appareil dans NINA.
  if (item.read_only) {
    input.readOnly = true;
    input.classList.add("readonly");
    input.title = "Identifiant stable : non modifiable depuis l'interface";
  }

  const description = document.createElement("span");
  description.className = "desc";
  description.textContent = item.description || "";
  wrapper.append(description);

  return wrapper;
}

function renderConfig(data) {
  schema = data;

  const form = $("config-form");
  form.replaceChildren();

  const byGroup = new Map();
  for (const item of data.settings) {
    if (!byGroup.has(item.group)) {
      byGroup.set(item.group, []);
    }
    byGroup.get(item.group).push(item);
  }

  const ordered = (data.groups || []).filter((group) => byGroup.has(group));

  for (const group of ordered) {
    const fieldset = document.createElement("fieldset");
    fieldset.style.setProperty("--group-color", GROUP_COLORS[group] || "#8b9bab");

    const legend = document.createElement("legend");
    legend.textContent = GROUP_LABELS[group] || group;
    fieldset.append(legend);

    const fields = document.createElement("div");
    fields.className = "fields";

    for (const item of byGroup.get(group)) {
      fields.append(fieldElement(item));
    }

    fieldset.append(fields);
    form.append(fieldset);
  }
}

async function loadConfig() {
  const result = await api("/api/config/schema");

  if (!result.ok) {
    show($("config-error"), `Configuration indisponible (${result.status})`);
    return;
  }

  hide($("config-error"));
  hide($("config-restart"));
  renderConfig(result.data);
}

async function scanDrivers(input, button, wrapper) {
  button.disabled = true;
  button.textContent = "…";

  try {
    const result = await api("/api/mount/drivers");

    if (!result.ok) {
      show($("config-error"), `Scan des pilotes impossible (${result.status})`);
      return;
    }

    const drivers = (result.data || {}).drivers || [];

    if (!drivers.length) {
      show(
        $("config-error"),
        "Aucun pilote ASCOM de monture trouvé. Vérifier l'installation du pilote et de la plateforme ASCOM.",
      );
      return;
    }

    hide($("config-error"));

    let select = wrapper.querySelector("select.driver-list");

    if (!select) {
      select = document.createElement("select");
      select.className = "driver-list";
      select.addEventListener("change", () => {
        if (select.value) {
          input.value = select.value;
        }
      });
      wrapper.append(select);
    }

    select.replaceChildren();
    select.append(new Option("— choisir un pilote —", ""));

    for (const driver of drivers) {
      select.append(new Option(`${driver.name} — ${driver.prog_id}`, driver.prog_id));
    }

    const known = drivers.some((driver) => driver.prog_id === input.value);
    select.value = known ? input.value : "";
  } finally {
    button.disabled = false;
    button.textContent = "Scanner";
  }
}

function currentValue(input) {  if (input.type === "checkbox") {
    return input.checked ? "true" : "false";
  }
  return input.value;
}

async function saveConfig() {
  hide($("config-error"));
  hide($("config-restart"));

  const inputs = $("config-form").querySelectorAll("input, select");
  const errors = [];
  let changed = 0;

  for (const input of inputs) {
    const value = currentValue(input);

    if (value === input.dataset.initial) {
      continue;
    }

    const path = `/api/config/${encodeURIComponent(input.dataset.key)}/${encodeURIComponent(value)}`;
    const result = await api(path, { method: "POST" });

    if (result.ok) {
      changed += 1;
    } else {
      const data = result.data || {};
      errors.push(`${input.dataset.key} : ${data.detail || result.status}`);
    }
  }

  // On recharge d'abord (cela remet les valeurs de reference et efface les
  // messages), puis on affiche le bilan : sinon le message de redemarrage
  // serait efface dans la foulee.
  await loadConfig();

  if (errors.length) {
    show($("config-error"), errors.join(" — "));
  }

  if (changed) {
    show(
      $("config-restart"),
      `${changed} réglage(s) enregistré(s). Redémarrage nécessaire pour les appliquer.`,
    );
  }
}

// -- redemarrage ---------------------------------------------------------

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));

    try {
      const result = await api("/api/health");
      if (result.ok) {
        window.location.reload();
        return;
      }
    } catch {
      // serveur encore arrete : on reessaie
    }
  }

  show($("config-error"), "Le serveur ne répond pas après 60 s.");
}

async function restartServer() {
  if (
    !confirm(
      "Redémarrer le serveur ?\n\nLa configuration enregistrée sera appliquée. " +
        "Le toit ne doit pas être en mouvement.",
    )
  ) {
    return;
  }

  hide($("config-error"));

  try {
    const result = await api("/api/server/restart", { method: "POST" });

    if (!result.ok) {
      const data = result.data || {};
      show($("config-error"), data.message || data.detail || `Refus (${result.status})`);
      return;
    }

    show($("config-restart"), "Redémarrage du serveur… la page va se recharger.");
    await waitForServer();
  } catch (error) {
    // Le serveur peut couper la connexion avant de repondre : c'est normal.
    show($("config-restart"), "Redémarrage du serveur…");
    await waitForServer();
  }
}

// -- demarrage automatique -----------------------------------------------

async function loadAutostart() {
  const box = $("autostart");
  const hint = $("autostart-hint");

  const result = await api("/api/system/autostart");

  if (!result.ok) {
    box.disabled = true;
    hint.textContent = "État indisponible.";
    return;
  }

  box.checked = result.data.enabled === true;
  hint.textContent = box.checked
    ? "Raccourci présent dans le dossier Démarrage."
    : "Aucun démarrage automatique.";
}

async function toggleAutostart() {
  const box = $("autostart");
  const hint = $("autostart-hint");
  const wanted = box.checked;

  box.disabled = true;
  hide($("config-error"));

  const result = await api(`/api/system/autostart?enabled=${wanted}`, {
    method: "POST",
  });

  box.disabled = false;

  if (!result.ok || !result.data) {
    box.checked = !wanted;
    show(
      $("config-error"),
      (result.data && result.data.message) || "Modification impossible.",
    );
    return;
  }

  box.checked = result.data.enabled === true;
  hint.textContent = box.checked
    ? "Raccourci présent dans le dossier Démarrage."
    : "Aucun démarrage automatique.";
}

$("autostart").addEventListener("change", toggleAutostart);

// -- icone de la zone de notification ------------------------------------

async function loadTrayIcon() {
  const box = $("tray-promote");
  const hint = $("tray-hint");

  const result = await api("/api/system/tray-icon");

  if (!result.ok) {
    box.disabled = true;
    hint.textContent = "État indisponible.";
    return;
  }

  const data = result.data;

  box.checked = data.promoted === true;
  box.disabled = !data.supported || !data.known;

  if (!data.supported) {
    hint.textContent = data.reason || "Non disponible.";
  } else if (!data.known) {
    hint.textContent =
      data.reason || "Windows n'a pas encore enregistré l'icône.";
  } else if (data.promoted) {
    hint.textContent = "Icône affichée dans la barre.";
  } else {
    hint.textContent = "Icône repliée dans le menu chevron de Windows.";
  }
}

async function toggleTrayIcon() {
  const box = $("tray-promote");
  const hint = $("tray-hint");
  const wanted = box.checked;

  box.disabled = true;

  const result = await api(`/api/system/tray-icon?promoted=${wanted}`, {
    method: "POST",
  });

  box.disabled = false;

  if (!result.ok || !result.data) {
    box.checked = !wanted;
    show($("config-error"), "Modification de l'icône impossible.");
    return;
  }

  box.checked = result.data.promoted === true;
  hint.textContent = box.checked
    ? "Icône affichée. Une reconnexion Windows peut être nécessaire."
    : "Icône repliée. Une reconnexion Windows peut être nécessaire.";
}

$("tray-promote").addEventListener("change", toggleTrayIcon);

// -- atelier Arduino -----------------------------------------------------

const ARDUINO_BOARDS = [
  { value: "arduino:avr:nano", label: "Arduino Nano (bootloader récent)" },
  { value: "arduino:avr:nano:cpu=atmega328old", label: "Arduino Nano (ancien bootloader)" },
  { value: "arduino:avr:uno", label: "Arduino Uno" },
];

let arduinoTimer = null;

function setArduinoState(text, kind) {
  const tag = $("arduino-state");
  tag.textContent = text;
  tag.className = `tag ${kind || ""}`;
}

async function loadArduino() {
  const result = await api("/api/arduino/status");

  if (!result.ok) {
    setArduinoState("indisponible", "off");
    return;
  }

  const data = result.data;

  const fqbn = $("arduino-fqbn");
  if (!fqbn.options.length) {
    for (const board of ARDUINO_BOARDS) {
      fqbn.append(new Option(board.label, board.value));
    }
  }
  if (data.fqbn) {
    fqbn.value = data.fqbn;
  }

  const port = $("arduino-port");
  const previous = port.value;
  port.replaceChildren();

  const known = new Set();
  for (const entry of data.ports || []) {
    const label = `${entry.address} — ${entry.board || entry.protocol || "série"}`;
    port.append(new Option(label, entry.address));
    known.add(entry.address);
  }

  const wanted = data.port || previous;
  if (wanted && !known.has(wanted)) {
    port.append(new Option(wanted, wanted));
  }
  if (wanted) {
    port.value = wanted;
  }

  const cores = (data.cores || [])
    .map((core) => `${core.id} ${core.installed}`)
    .join(", ");

  $("arduino-toolchain").textContent = data.available
    ? `arduino-cli ${data.version || "?"} · ${cores || "aucun noyau installé"} · croquis ${data.sketch ? "présent" : "absent"}`
    : "arduino-cli introuvable : vérifier l'installation de l'IDE Arduino, ou renseigner arduino_cli_path.";

  if (!arduinoTimer) {
    setArduinoState(data.available ? "prêt" : "indisponible", data.available ? "on" : "off");
  }
}

async function startArduino(action) {
  hide($("arduino-error"));

  if (
    action === "upload" &&
    !confirm(
      "Téléverser le firmware ?\n\n" +
        "Le moteur sera coupé et l'Arduino redémarré.\n" +
        "Le toit doit être immobile.",
    )
  ) {
    return;
  }

  const params = new URLSearchParams({
    fqbn: $("arduino-fqbn").value,
    port: $("arduino-port").value,
  });

  const result = await api(`/api/arduino/${action}?${params}`, { method: "POST" });

  if (!result.ok) {
    const data = result.data || {};
    show($("arduino-error"), data.message || data.detail || `Refus (${result.status})`);
    return;
  }

  setArduinoState(action === "upload" ? "téléversement…" : "compilation…", "");
  $("arduino-output").textContent = "Démarrage…";

  pollArduino();
}

function pollArduino() {
  if (arduinoTimer) {
    clearInterval(arduinoTimer);
  }

  arduinoTimer = setInterval(async () => {
    const result = await api("/api/arduino/job");

    if (!result.ok) {
      return;
    }

    const job = result.data;
    const output = $("arduino-output");

    output.textContent = (job.output || []).join("\n") || "…";
    output.scrollTop = output.scrollHeight;

    if (job.state === "running") {
      setArduinoState("en cours…", "");
      return;
    }

    clearInterval(arduinoTimer);
    arduinoTimer = null;

    if (job.state === "done") {
      setArduinoState("terminé", "on");
      await loadArduino();
    } else if (job.state === "error") {
      setArduinoState("échec", "off");
    }
  }, 1000);
}

// -- documentation -------------------------------------------------------

const docsDialog = $("docs-dialog");

async function loadDoc(name) {
  if (!name) {
    return;
  }

  const result = await api(`/api/docs/${encodeURIComponent(name)}`);
  const body = $("docs-content");

  if (!result.ok) {
    body.textContent = "Document indisponible.";
    return;
  }

  body.innerHTML = result.data.html || "";
  body.scrollTop = 0;
}

async function openDocs() {
  if (!docsDialog.open) {
    docsDialog.showModal();
  }

  const select = $("docs-select");

  if (!select.options.length) {
    const result = await api("/api/docs");

    if (!result.ok) {
      $("docs-content").textContent = "Documentation indisponible.";
      return;
    }

    for (const doc of result.data.documents || []) {
      if (doc.available) {
        select.append(new Option(doc.title, doc.key));
      }
    }

    select.addEventListener("change", () => loadDoc(select.value));
  }

  if (!select.value && select.options.length) {
    select.selectedIndex = 0;
  }

  await loadDoc(select.value);
}

$("btn-docs").addEventListener("click", openDocs);
$("docs-close").addEventListener("click", () => docsDialog.close());

// -- journaux ------------------------------------------------------------

const logsDialog = $("logs-dialog");

let logsTimer = null;

async function loadLogList() {
  const result = await api("/api/logs");
  if (!result.ok) {
    return;
  }

  const select = $("logs-select");
  const current = select.value;

  select.replaceChildren();

  for (const entry of result.data.logs) {
    if (!entry.exists) {
      continue;
    }
    const kilo = Math.max(1, Math.round(entry.size / 1024));
    select.append(new Option(`${entry.name} — ${kilo} Ko`, entry.name));
  }

  if (current && [...select.options].some((option) => option.value === current)) {
    select.value = current;
  } else if (select.options.length) {
    select.selectedIndex = 0;
  }
}

async function refreshLogs() {
  const name = $("logs-select").value;
  if (!name) {
    return;
  }

  const lines = $("logs-lines").value;
  const result = await api(`/api/logs/${encodeURIComponent(name)}?lines=${lines}`);
  const pre = $("logs-content");

  if (!result.ok) {
    pre.textContent = `Lecture impossible (${result.status})`;
    return;
  }

  const data = result.data || {};
  const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 24;

  pre.textContent = (data.lines || []).join("\n") || "(journal vide)";

  if (atBottom || $("logs-auto").checked) {
    pre.scrollTop = pre.scrollHeight;
  }

  $("logs-meta").textContent =
    `${(data.lines || []).length} ligne(s) · ${((data.size || 0) / 1024).toFixed(1)} Ko` +
    (data.truncated ? " · début tronqué" : "");
}

async function openLogs() {
  if (!logsDialog.open) {
    logsDialog.showModal();
  }

  await loadLogList();
  await refreshLogs();

  if (logsTimer) {
    clearInterval(logsTimer);
  }

  logsTimer = setInterval(async () => {
    if (!logsDialog.open) {
      return;
    }
    await loadLogList();
    if ($("logs-auto").checked) {
      await refreshLogs();
    }
  }, 2000);
}

function closeLogs() {
  logsDialog.close();
}

$("btn-logs").addEventListener("click", openLogs);
$("logs-close").addEventListener("click", closeLogs);
$("logs-refresh").addEventListener("click", refreshLogs);
$("logs-select").addEventListener("change", refreshLogs);
$("logs-lines").addEventListener("change", refreshLogs);

logsDialog.addEventListener("close", () => {
  if (logsTimer) {
    clearInterval(logsTimer);
    logsTimer = null;
  }
});

// -- demarrage -----------------------------------------------------------

$("btn-open").addEventListener("click", () => command("/api/dome/open", "Ouvrir le toit"));
$("btn-close").addEventListener("click", () => command("/api/dome/close", "Fermer le toit"));
$("btn-stop").addEventListener("click", () => command("/api/dome/stop", "Arrêter le toit"));
$("btn-park").addEventListener("click", () =>
  command("/api/mount/park", "Parquer la monture"),
);

$("btn-save").addEventListener("click", saveConfig);
$("btn-reload").addEventListener("click", loadConfig);
$("btn-restart").addEventListener("click", restartServer);

$("arduino-compile").addEventListener("click", () => startArduino("compile"));
$("arduino-upload").addEventListener("click", () => startArduino("upload"));

loadConfig();
loadArduino();
loadAutostart();
loadTrayIcon();
refresh();
setInterval(refresh, POLL_MS);

// Lien direct vers les journaux : /ui/#logs (utile au support et aux tests).
if (window.location.hash === "#logs") {
  openLogs();
} else if (window.location.hash === "#docs") {
  openDocs();
}
