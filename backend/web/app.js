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

    wrapper.append(label, input);
  }

  input.id = `cfg-${item.key}`;
  input.dataset.key = item.key;
  input.dataset.type = item.type;
  input.dataset.initial =
    item.type === "bool" ? String(item.value === true) : String(item.value);

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

function currentValue(input) {
  if (input.type === "checkbox") {
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

loadConfig();
refresh();
setInterval(refresh, POLL_MS);
