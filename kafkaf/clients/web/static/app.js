if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    // Registered from the root (not /static/sw.js) so its scope covers the
    // whole app, not just /static/* requests — see kafkaf/core/api.py.
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

initLanguage();

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = formEl.querySelector(".send-btn");
const brainSelectEl = document.getElementById("brain-select");
const personaSelectEl = document.getElementById("persona-select");
const councilToggleEl = document.getElementById("council-toggle");
const skillsToggleEl = document.getElementById("skills-toggle");

const SESSION_KEY = "kafkaf-session-id";
let sessionId = localStorage.getItem(SESSION_KEY);
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
}

const BRAIN_KEY = "kafkaf-brain";
brainSelectEl.value = localStorage.getItem(BRAIN_KEY) || "";
brainSelectEl.addEventListener("change", () => {
  localStorage.setItem(BRAIN_KEY, brainSelectEl.value);
});

const PERSONA_KEY = "kafkaf-persona";
personaSelectEl.value = localStorage.getItem(PERSONA_KEY) || "default";
personaSelectEl.addEventListener("change", () => {
  localStorage.setItem(PERSONA_KEY, personaSelectEl.value);
  updateSelectionHint();
});

// Always-visible explanation of the current persona/model choice — a
// hover-only tooltip wasn't discoverable enough (real user feedback: "not
// clear what these dropdowns mean").
const selectionHintEl = document.getElementById("selection-hint");
function updateSelectionHint() {
  if (!selectionHintEl) return;
  const personaKey = `persona_${personaSelectEl.value}_desc`;
  const brainKey = brainSelectEl.value === "own" ? "brain_own_desc" : "brain_default_desc";
  selectionHintEl.textContent = `${t(personaKey)} · ${t(brainKey)}`;
}
brainSelectEl.addEventListener("change", updateSelectionHint);
document.addEventListener("kafkaf-lang-changed", updateSelectionHint);
updateSelectionHint();

const COUNCIL_KEY = "kafkaf-council";
councilToggleEl.checked = localStorage.getItem(COUNCIL_KEY) === "1";
councilToggleEl.addEventListener("change", () => {
  localStorage.setItem(COUNCIL_KEY, councilToggleEl.checked ? "1" : "0");
  // Council mode picks its own brains from config, not a single override —
  // but skills combines with it (each council brain gets tool use).
  brainSelectEl.disabled = councilToggleEl.checked;
});
brainSelectEl.disabled = councilToggleEl.checked;

function setToggleAvailability(toggleEl, allowed, titleKey) {
  const label = toggleEl.closest(".council-toggle");
  toggleEl.disabled = !allowed;
  if (!allowed) toggleEl.checked = false;
  if (label) {
    label.classList.toggle("disabled", !allowed);
    if (!allowed) {
      label.setAttribute("data-i18n-title", titleKey);
      label.setAttribute("title", t(titleKey));
    } else {
      label.removeAttribute("data-i18n-title");
      label.removeAttribute("title");
    }
  }
}

// Council needs KAFKAF_COUNCIL_BRAINS configured, and Skills needs an
// autonomy level above "observe" — checking either box without that used
// to just produce a confusing dead-end error on send. Disable upfront
// instead, with an explanatory tooltip, and re-check whenever the
// Control Panel changes the autonomy level so the toggle never lies about
// what will actually happen — no contradictions between what's shown and
// what /chat will actually allow.
async function refreshSkillsAvailability() {
  try {
    const response = await fetch("/status");
    if (!response.ok) return;
    const data = await response.json();
    setToggleAvailability(councilToggleEl, data.council.configured, "council_disabled_title");
    setToggleAvailability(skillsToggleEl, data.autonomy.skills_allowed, "skills_disabled_title");
  } catch {
    /* backend not reachable yet on first paint — leave both enabled,
       the /chat call itself will surface a clear error if it's still down */
  }
}
refreshSkillsAvailability();

const SKILLS_KEY = "kafkaf-skills";
skillsToggleEl.checked = localStorage.getItem(SKILLS_KEY) === "1";
skillsToggleEl.addEventListener("change", () => {
  localStorage.setItem(SKILLS_KEY, skillsToggleEl.checked ? "1" : "0");
});

function addBubble(role, text) {
  removeWelcome();
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function addTypingIndicator() {
  const bubble = document.createElement("div");
  bubble.className = "bubble assistant typing";
  bubble.setAttribute("aria-label", t("typing_indicator"));
  bubble.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function removeWelcome() {
  const welcome = document.getElementById("welcome-card");
  if (welcome) welcome.remove();
}

function showWelcomeIfEmpty() {
  if (chatEl.children.length > 0) return;
  const card = document.createElement("div");
  card.id = "welcome-card";
  card.className = "welcome-card";
  card.innerHTML = `<h2>${t("welcome_title")}</h2><p>${t("welcome_body")}</p>`;
  chatEl.appendChild(card);
}
showWelcomeIfEmpty();

document.addEventListener("kafkaf-lang-changed", () => {
  const welcome = document.getElementById("welcome-card");
  if (welcome) {
    welcome.querySelector("h2").textContent = t("welcome_title");
    welcome.querySelector("p").textContent = t("welcome_body");
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${inputEl.scrollHeight}px`;
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  addBubble("user", message);
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.disabled = true;
  const typingBubble = addTypingIndicator();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        persona: personaSelectEl.value,
        brain: councilToggleEl.checked ? null : brainSelectEl.value || null,
        council: councilToggleEl.checked,
        skills: skillsToggleEl.checked,
      }),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      // The backend always returns JSON, success or failure (see
      // core/api.py) — a response that isn't valid JSON means something
      // below the app itself failed (a proxy, the server process dying
      // mid-request, ...), not a normal error path.
      throw new Error(`Backend returned ${response.status} with a non-JSON body`);
    }
    if (!response.ok) {
      throw new Error(data.detail || `Backend returned ${response.status}`);
    }
    typingBubble.remove();
    addBubble("assistant", data.reply);
  } catch (err) {
    typingBubble.remove();
    addBubble("error", `${t("error_prefix")}: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
});

// ---------------------------------------------------------------------
// Theme: light / dark / auto. Auto tries a real local sunset/sunrise
// calculation (via geolocation) and falls back to the OS's own
// prefers-color-scheme if location isn't available or is denied.
// ---------------------------------------------------------------------

const THEME_KEY = "kafkaf-theme";
const GEO_KEY = "kafkaf-geo";
const THEME_ORDER = ["light", "dark", "auto"];
const themeToggleEl = document.getElementById("theme-toggle");
const themeIconEl = document.getElementById("theme-icon");
let autoRefreshTimer = null;

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// Sunrise/sunset equation (Almanac for Computers, 1990) — a well-known,
// offline-computable approximation (accurate to a few minutes), not a
// precision astronomical result. Good enough for "should the UI look
// like night right now," not for anything else.
function sunEventUtcHours(lat, lon, date, isSunrise) {
  const rad = Math.PI / 180;
  const deg = 180 / Math.PI;
  const start = Date.UTC(date.getFullYear(), 0, 1);
  const today = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const dayOfYear = Math.round((today - start) / 86400000) + 1;
  const lngHour = lon / 15;
  const th = isSunrise ? 6 : 18;
  const tt = dayOfYear + (th - lngHour) / 24;
  const M = 0.9856 * tt - 3.289;
  let L = M + 1.916 * Math.sin(rad * M) + 0.02 * Math.sin(2 * rad * M) + 282.634;
  L = ((L % 360) + 360) % 360;
  let RA = deg * Math.atan(0.91764 * Math.tan(rad * L));
  RA = ((RA % 360) + 360) % 360;
  const Lquadrant = Math.floor(L / 90) * 90;
  const RAquadrant = Math.floor(RA / 90) * 90;
  RA = (RA + (Lquadrant - RAquadrant)) / 15;
  const sinDec = 0.39782 * Math.sin(rad * L);
  const cosDec = Math.cos(Math.asin(sinDec));
  const zenith = 90.833;
  const cosH = (Math.cos(rad * zenith) - sinDec * Math.sin(rad * lat)) / (cosDec * Math.cos(rad * lat));
  if (cosH > 1 || cosH < -1) return null; // sun never rises/sets today at this latitude
  let H = isSunrise ? 360 - deg * Math.acos(cosH) : deg * Math.acos(cosH);
  H = H / 15;
  const T = H + RA - 0.06571 * tt - 6.622;
  return ((T - lngHour) % 24 + 24) % 24;
}

function utcHoursToDate(date, utcHours) {
  const hours = Math.floor(utcHours);
  const minutes = Math.round((utcHours - hours) * 60);
  return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes));
}

function isNightAt(lat, lon, now = new Date()) {
  const sunriseUtc = sunEventUtcHours(lat, lon, now, true);
  const sunsetUtc = sunEventUtcHours(lat, lon, now, false);
  if (sunriseUtc === null || sunsetUtc === null) return systemPrefersDark();
  const sunrise = utcHoursToDate(now, sunriseUtc);
  const sunset = utcHoursToDate(now, sunsetUtc);
  return now < sunrise || now >= sunset;
}

function applyResolvedTheme(isDark) {
  document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
}

function resolveAutoTheme() {
  const cached = JSON.parse(localStorage.getItem(GEO_KEY) || "null");
  applyResolvedTheme(cached ? isNightAt(cached.lat, cached.lon) : systemPrefersDark());

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        localStorage.setItem(GEO_KEY, JSON.stringify({ lat: latitude, lon: longitude }));
        if (currentTheme() === "auto") applyResolvedTheme(isNightAt(latitude, longitude));
      },
      () => {
        /* denied or unavailable — the prefers-color-scheme fallback above already applied */
      },
      { maximumAge: 3600000, timeout: 5000 }
    );
  }
}

// No theme choice saved yet (first visit) resolves from the OS preference
// only — it must NOT silently ask for the visitor's location before
// they've done anything. Geolocation is only ever requested once someone
// explicitly cycles the toggle into "auto" mode themselves.
function currentTheme() {
  return localStorage.getItem(THEME_KEY);
}

function applyTheme(theme) {
  localStorage.setItem(THEME_KEY, theme);
  clearInterval(autoRefreshTimer);
  if (theme === "light") applyResolvedTheme(false);
  else if (theme === "dark") applyResolvedTheme(true);
  else {
    resolveAutoTheme();
    // Re-check periodically so a page left open across an actual sunset
    // still switches, without needing a reload.
    autoRefreshTimer = setInterval(resolveAutoTheme, 5 * 60 * 1000);
  }
  if (themeIconEl) themeIconEl.textContent = { light: "☀️", dark: "🌙", auto: "🌅" }[theme];
  if (themeToggleEl) themeToggleEl.setAttribute("aria-label", `${t("theme_aria")}: ${t("theme_" + theme)}`);
}

if (themeToggleEl) {
  themeToggleEl.addEventListener("click", () => {
    const next = THEME_ORDER[(THEME_ORDER.indexOf(currentTheme()) + 1) % THEME_ORDER.length];
    applyTheme(next);
  });
}
applyTheme(currentTheme() || (systemPrefersDark() ? "dark" : "light"));

// ---------------------------------------------------------------------
// Control panel: real, live view of autonomy level, own-model training
// progress, and recent audit activity — the "what is this thing actually
// allowed to do, and what has it done" answer, in the app itself instead
// of only in docs/CLI commands.
// ---------------------------------------------------------------------

const controlToggleEl = document.getElementById("control-toggle");
const controlOverlayEl = document.getElementById("control-overlay");
const controlCloseEl = document.getElementById("control-close");
const controlBodyEl = document.getElementById("control-body");

function renderControlPanel(statusData, auditEvents) {
  const own = statusData.own_model;
  const autonomyRow = statusData.autonomy;

  const lastRun = own.last_training_run;
  const lastRunText = lastRun
    ? `${t("last_run_steps")} ${lastRun.steps}, ${new Date(lastRun.created_at + "Z").toLocaleString()}`
    : t("last_run_none");

  const auditHtml = auditEvents.length
    ? auditEvents
        .slice(0, 8)
        .map(
          (event) => `
        <div class="audit-item">
          <div>${event.event_type} — ${event.actor}</div>
          <div class="audit-meta">${new Date(event.created_at + "Z").toLocaleString()}</div>
        </div>`
        )
        .join("")
    : `<p class="control-hint">${t("audit_empty")}</p>`;

  const autonomyButtons = ["observe", "assisted", "autonomous"]
    .map(
      (level) => `
      <button type="button" class="autonomy-btn${level === autonomyRow.level ? " active" : ""}" data-level="${level}">
        ${t("autonomy_level_" + level)}
      </button>`
    )
    .join("");

  controlBodyEl.innerHTML = `
    <div class="control-section">
      <h3>${t("autonomy_heading")}</h3>
      <div class="autonomy-buttons">${autonomyButtons}</div>
      <div class="control-row"><span>${autonomyRow.level}</span><span class="value">${
    autonomyRow.skills_allowed ? t("autonomy_skills_yes") : t("autonomy_skills_no")
  }</span></div>
      <p class="control-hint">${autonomyRow.description}</p>
      <p class="control-hint">${t("autonomy_change_hint")}</p>
    </div>
    <div class="control-section">
      <h3>${t("own_model_heading")}</h3>
      <div class="control-row"><span>${t("corpus_size_label")}</span><span class="value">${own.corpus_size}</span></div>
      <div class="control-row"><span>${t("unused_examples_label")}</span><span class="value">${own.unused_examples}</span></div>
      <div class="control-row"><span>${t("checkpoint_label")}</span><span class="value">${
    own.checkpoint_exists ? t("checkpoint_yes") : t("checkpoint_no")
  }</span></div>
      <div class="control-row"><span>${t("last_run_label")}</span><span class="value">${lastRunText}</span></div>
    </div>
    <div class="control-section">
      <h3>${t("audit_heading")}</h3>
      ${auditHtml}
    </div>
    <div class="control-section">
      <h3>${t("growth_heading")}</h3>
      <p class="control-hint">${t("growth_intro")}</p>
      <label class="growth-label" for="growth-topic">${t("growth_topic_label")}</label>
      <input id="growth-topic" class="growth-input" type="text" placeholder="${t("growth_topic_placeholder")}" />
      <label class="growth-label" for="growth-fact">${t("growth_fact_label")}</label>
      <textarea id="growth-fact" class="growth-input" rows="2" placeholder="${t("growth_fact_placeholder")}"></textarea>
      <div class="growth-actions">
        <button type="button" id="growth-teach-btn" class="growth-btn">${t("growth_teach_btn")}</button>
        <button type="button" id="growth-distill-btn" class="growth-btn">${t("growth_distill_btn")}</button>
      </div>
      <div class="growth-train-row">
        <label class="growth-label" for="growth-steps">${t("growth_train_label")}</label>
        <input id="growth-steps" class="growth-steps-input" type="number" min="1" value="50" />
        <button type="button" id="growth-train-btn" class="growth-btn">${t("growth_train_btn")}</button>
      </div>
      <p id="growth-status" class="control-hint" aria-live="polite"></p>
    </div>
    <div class="control-section">
      <h3>${t("workspace_heading")}</h3>
      <p class="control-hint">${t("workspace_intro")}</p>
      <label class="growth-label">${t("workspace_current_label")}</label>
      <p class="control-hint" style="word-break: break-all;">${statusData.skills_workspace_dir}</p>
      <input id="workspace-input" class="growth-input" type="text" placeholder="${t("workspace_input_placeholder")}" />
      <div class="growth-actions">
        <button type="button" id="workspace-set-btn" class="growth-btn">${t("workspace_set_btn")}</button>
      </div>
      <p id="workspace-status" class="control-hint" aria-live="polite"></p>
    </div>
  `;
  wireGrowPanel(statusData.default_teacher);
  wireAutonomyButtons();
  wireWorkspacePanel();
}

function wireWorkspacePanel() {
  const inputEl = document.getElementById("workspace-input");
  const btnEl = document.getElementById("workspace-set-btn");
  const statusEl = document.getElementById("workspace-status");

  btnEl.addEventListener("click", async () => {
    const path = inputEl.value.trim();
    if (!path) return;
    btnEl.disabled = true;
    statusEl.textContent = t("growth_working");
    try {
      const response = await fetch("/skills/workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `${response.status}`);
      await loadControlPanel();
    } catch (err) {
      statusEl.textContent = `${t("growth_error")}${err.message}`;
      btnEl.disabled = false;
    }
  });
}

function wireAutonomyButtons() {
  controlBodyEl.querySelectorAll(".autonomy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (btn.classList.contains("active")) return;
      controlBodyEl.querySelectorAll(".autonomy-btn").forEach((b) => (b.disabled = true));
      try {
        await fetch("/autonomy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ level: btn.dataset.level }),
        });
      } finally {
        await loadControlPanel();
        await refreshSkillsAvailability();
      }
    });
  });
}

function wireGrowPanel(defaultTeacher) {
  const topicEl = document.getElementById("growth-topic");
  const factEl = document.getElementById("growth-fact");
  const stepsEl = document.getElementById("growth-steps");
  const statusEl = document.getElementById("growth-status");
  const teachBtn = document.getElementById("growth-teach-btn");
  const distillBtn = document.getElementById("growth-distill-btn");
  const trainBtn = document.getElementById("growth-train-btn");

  async function runGrowthAction(action) {
    const buttons = [teachBtn, distillBtn, trainBtn];
    buttons.forEach((btn) => (btn.disabled = true));
    statusEl.textContent = t("growth_working");
    try {
      await action();
      await loadControlPanel();
    } catch (err) {
      statusEl.textContent = `${t("growth_error")}${err.message}`;
      buttons.forEach((btn) => (btn.disabled = false));
    }
  }

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status}`);
    return data;
  }

  teachBtn.addEventListener("click", () =>
    runGrowthAction(async () => {
      if (!topicEl.value.trim() || !factEl.value.trim()) throw new Error(t("growth_missing_fields"));
      await postJson("/enrichment/teach", { topic: topicEl.value.trim(), fact: factEl.value.trim() });
    })
  );

  distillBtn.addEventListener("click", () =>
    runGrowthAction(async () => {
      if (!topicEl.value.trim()) throw new Error(t("growth_missing_fields"));
      await postJson("/enrichment/distill", { topic: topicEl.value.trim(), teacher: defaultTeacher });
    })
  );

  trainBtn.addEventListener("click", () =>
    runGrowthAction(async () => {
      const steps = parseInt(stepsEl.value, 10) || 50;
      await postJson("/enrichment/train", { steps });
    })
  );
}

async function loadControlPanel() {
  controlBodyEl.innerHTML = `<p>${t("control_loading")}</p>`;
  try {
    const [statusResponse, auditResponse] = await Promise.all([
      fetch("/status"),
      fetch("/audit?limit=8"),
    ]);
    if (!statusResponse.ok || !auditResponse.ok) throw new Error("bad response");
    const statusData = await statusResponse.json();
    const auditEvents = await auditResponse.json();
    renderControlPanel(statusData, auditEvents);
  } catch {
    controlBodyEl.innerHTML = `<p class="control-hint">${t("control_error")}</p>`;
  }
}

function openControlPanel() {
  controlOverlayEl.classList.remove("hidden");
  loadControlPanel();
}

function closeControlPanel() {
  controlOverlayEl.classList.add("hidden");
}

if (controlToggleEl) {
  controlToggleEl.addEventListener("click", openControlPanel);
  controlCloseEl.addEventListener("click", closeControlPanel);
  controlOverlayEl.addEventListener("click", (event) => {
    if (event.target === controlOverlayEl) closeControlPanel();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !controlOverlayEl.classList.contains("hidden")) closeControlPanel();
  });
}
