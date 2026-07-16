// Real language separation, not mixed Hebrew+English in the same view.
// Brand names ("כףכף", "KafKaf") and persona names (Researcher/Coach) are
// left untranslated on purpose — they're names, not UI copy.
const TRANSLATIONS = {
  he: {
    persona_default: "Kaf (ברירת מחדל)",
    brain_default: "מודל ברירת מחדל (Ollama)",
    brain_own: "המודל שלנו (גדל עם הזמן)",
    council_label: "מועצת מוחות",
    skills_label: "סקילים",
    persona_aria: "פרסונה",
    brain_aria: "מודל",
    settings_group: "הגדרות שיחה",
    composer_aria: "שליחת הודעה",
    message_label: "הודעה",
    message_placeholder: "כתבו הודעה...",
    send_aria: "שליחה",
    error_prefix: "שגיאה",
    theme_aria: "ערכת נושא (בהיר/כהה/אוטומטי)",
    theme_light: "☀️ בהיר",
    theme_dark: "🌙 כהה",
    theme_auto: "🌅 אוטומטי (שקיעה)",
    control_aria: "פאנל בקרה",
    control_title: "בקרה ומצב המערכת",
    control_close: "סגירה",
    control_loading: "טוען...",
    control_error: "לא הצלחנו לטעון את הנתונים. השרת רץ?",
    autonomy_heading: "רמת אוטונומיה",
    autonomy_skills_yes: "סקילים מותרים",
    autonomy_skills_no: "סקילים חסומים ברמה הזו",
    autonomy_change_hint: "משתנה דרך KAFKAF_AUTONOMY_LEVEL בקובץ הקונפיגורציה, ודורש הפעלה מחדש. ראו docs/SETUP.md#autonomy-levels.",
    own_model_heading: "המודל הפרטי שלנו",
    corpus_size_label: "כמות ידע שנלמד",
    unused_examples_label: "ממתין לאימון",
    checkpoint_label: "מודל מאומן קיים",
    checkpoint_yes: "כן",
    checkpoint_no: "עדיין לא — עדיין לא בוצע אימון",
    last_run_label: "אימון אחרון",
    last_run_none: "מעולם לא בוצע אימון",
    last_run_steps: "צעדים",
    audit_heading: "פעילות אחרונה",
    audit_empty: "אין עדיין פעילות רשומה.",
  },
  en: {
    persona_default: "Kaf (default)",
    brain_default: "Default model (Ollama)",
    brain_own: "Our own model (grows over time)",
    council_label: "Council",
    skills_label: "Skills",
    persona_aria: "Persona",
    brain_aria: "Model",
    settings_group: "Chat settings",
    composer_aria: "Send a message",
    message_label: "Message",
    message_placeholder: "Type a message...",
    send_aria: "Send",
    error_prefix: "Error",
    theme_aria: "Theme (light/dark/auto)",
    theme_light: "☀️ Light",
    theme_dark: "🌙 Dark",
    theme_auto: "🌅 Auto (sunset)",
    control_aria: "Control panel",
    control_title: "Control & status",
    control_close: "Close",
    control_loading: "Loading...",
    control_error: "Couldn't load status. Is the server running?",
    autonomy_heading: "Autonomy level",
    autonomy_skills_yes: "Skills allowed",
    autonomy_skills_no: "Skills blocked at this level",
    autonomy_change_hint: "Changed via KAFKAF_AUTONOMY_LEVEL in config, and needs a restart. See docs/SETUP.md#autonomy-levels.",
    own_model_heading: "Our own model",
    corpus_size_label: "Facts taught so far",
    unused_examples_label: "Waiting to be trained",
    checkpoint_label: "Trained checkpoint exists",
    checkpoint_yes: "Yes",
    checkpoint_no: "Not yet — no training run has happened",
    last_run_label: "Last training run",
    last_run_none: "No training run yet",
    last_run_steps: "steps",
    audit_heading: "Recent activity",
    audit_empty: "No activity recorded yet.",
  },
};

const LANG_KEY = "kafkaf-lang";

function currentLang() {
  return localStorage.getItem(LANG_KEY) || "he";
}

function t(key) {
  const lang = currentLang();
  return (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]) || TRANSLATIONS.he[key] || key;
}

function applyLanguage(lang) {
  localStorage.setItem(LANG_KEY, lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "he" ? "rtl" : "ltr";

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });

  const langToggleEl = document.getElementById("lang-toggle");
  if (langToggleEl) {
    langToggleEl.textContent = lang === "he" ? "EN" : "עב";
    langToggleEl.setAttribute("aria-label", lang === "he" ? "Switch to English" : "עברית");
  }
}

function initLanguage() {
  applyLanguage(currentLang());
  const langToggleEl = document.getElementById("lang-toggle");
  if (langToggleEl) {
    langToggleEl.addEventListener("click", () => {
      applyLanguage(currentLang() === "he" ? "en" : "he");
    });
  }
}
