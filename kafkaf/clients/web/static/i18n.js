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
    theme_aria: "ערכת נושא (בהיר/כהה/שקיעה/אוטומטי)",
    theme_light: "☀️ בהיר",
    theme_dark: "🌙 כהה",
    theme_sunset: "🌇 שקיעה",
    theme_auto: "🕐 אוטומטי (יום/לילה לפי מיקום)",
    theme_auto_real: "🕐 אוטומטי — לפי שעת שקיעה אמיתית במיקום שלכם",
    theme_auto_fallback: "🕐 אוטומטי — המיקום לא זמין, לפי ערכת המערכת (לחצו לאפשר מיקום)",
    control_aria: "פאנל בקרה",
    control_title: "בקרה ומצב המערכת",
    control_close: "סגירה",
    control_loading: "טוען...",
    control_error: "לא הצלחנו לטעון את הנתונים. השרת רץ?",
    autonomy_heading: "רמת אוטונומיה",
    autonomy_skills_yes: "סקילים מותרים",
    autonomy_skills_no: "סקילים חסומים ברמה הזו",
    autonomy_change_hint: "השינוי כאן חי ומיידי לתהליך הזה — אין סתירות, מה שנבחר זה מה שבאמת פעיל. הוא לא משפיע על מיכל autopilot נפרד (Docker) ולא נשמר אחרי הפעלה מחדש בלי גם לעדכן KAFKAF_AUTONOMY_LEVEL. ראו docs/SETUP.md#autonomy-levels.",
    autonomy_level_observe: "צפייה בלבד",
    autonomy_level_assisted: "מסויע",
    autonomy_level_autonomous: "אוטונומי מלא",
    autopilot_heading: "לולאת הלמידה העצמאית (Autopilot)",
    autopilot_running: "פעילה — הלולאה מלמדת ומאמנת ללא השגחה",
    autopilot_stopped: "עצירת חירום פעילה — הלולאה עצורה עד שתחודש",
    autopilot_stop_btn: "עצירת חירום",
    autopilot_resume_btn: "חידוש הלולאה",
    autopilot_hint: "אותו מנגנון בדיוק כמו kafkaf-autopilot-ctl — רק בכפתור. עצירה נתפסת תוך שניות ונשמרת עד חידוש מפורש.",
    skills_disabled_title: "סקילים חסומים ברמת האוטונומיה הנוכחית",
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
    persona_title: "פרסונה: הטון וההנחיות של התשובה (לא מודל אחר)",
    brain_title: "מודל: איזה מוח עונה — ברירת המחדל, או המודל הפרטי שגדל איתך",
    persona_default_desc: "טון נייטרלי, תשובות ישירות",
    persona_researcher_desc: "טון מעמיק, עונה עם הנמקה",
    persona_coach_desc: "טון מעודד, שואל שאלות ומכוון",
    brain_default_desc: "מודל שרץ מקומית דרך Ollama",
    brain_own_desc: "המודל הפרטי שלכם — מתחיל ריק, לומד ממה שמלמדים אותו (פאנל הבקרה)",
    council_title: "מועצת מוחות: כמה מודלים עונים יחד, ותשובה אחת מסוכמת מהן",
    skills_title: "סקילים: נותן למודל להשתמש בכלים אמיתיים — חיפוש ברשת, מחשבון, קבצים ועוד",
    control_title_tip: "בקרה ומצב המערכת: רמת אוטונומיה, מודל פרטי, פעילות אחרונה",
    welcome_title: "ברוכים הבאים לKafKaf",
    welcome_body: "עוזר פרטי, בבעלותכם, שרץ אצלכם ולומד עם הזמן. בחרו פרסונה וטון תשובה, הפעילו \"מועצת מוחות\" כדי לקבל תשובה מכמה מודלים יחד, או \"סקילים\" כדי לתת למודל להשתמש בכלים אמיתיים כמו חיפוש ומחשבון. פשוט תתחילו לכתוב למטה.",
    typing_indicator: "כותב...",
    council_disabled_title: "מועצת מוחות דורשת קונפיגורציה (KAFKAF_COUNCIL_BRAINS) — ראו docs/SETUP.md",
    growth_heading: "ללמד ולהעשיר את המודל שלנו",
    growth_intro: "המודל הפרטי שלנו מתחיל בלי לדעת כלום — הוא לומד רק ממה שמלמדים אותו כאן, ומשתפר עם אימון.",
    growth_topic_label: "נושא",
    growth_topic_placeholder: "למשל: פוטוסינתזה",
    growth_fact_label: "עובדה (ללימוד ישיר)",
    growth_fact_placeholder: "כתבו כאן את מה שהמודל צריך לדעת...",
    growth_teach_btn: "למד עובדה זו",
    growth_distill_btn: "בקש מהמודל הראשי להסביר וללמד",
    growth_train_label: "צעדי אימון",
    growth_train_btn: "אמן עכשיו",
    growth_working: "עובד...",
    growth_taught_ok: "נלמד ונשמר.",
    growth_train_ok: "אימון הושלם.",
    growth_error: "משהו נכשל: ",
    growth_missing_fields: "נא למלא נושא (ועובדה, אם מלמדים ישירות)",
    workspace_heading: "תיקיית עבודה לסקילים",
    workspace_intro: "הסקילים files, document_search ו-journal יכולים לגעת רק בתיקייה הזו — בדיוק כמו תיקיית עבודה ב-Claude Code. שינוי כאן חי ומיידי.",
    workspace_current_label: "תיקייה נוכחית",
    workspace_input_placeholder: "לדוגמה: C:\\Users\\name\\Desktop",
    workspace_set_btn: "הגדר תיקייה",
    workspace_set_ok: "התיקייה עודכנה.",
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
    theme_aria: "Theme (light/dark/sunset/auto)",
    theme_light: "☀️ Light",
    theme_dark: "🌙 Dark",
    theme_sunset: "🌇 Sunset",
    theme_auto: "🕐 Auto (day/night by location)",
    theme_auto_real: "🕐 Auto — using real sunset time at your location",
    theme_auto_fallback: "🕐 Auto — location unavailable, following system theme (click to allow location)",
    control_aria: "Control panel",
    control_title: "Control & status",
    control_close: "Close",
    control_loading: "Loading...",
    control_error: "Couldn't load status. Is the server running?",
    autonomy_heading: "Autonomy level",
    autonomy_skills_yes: "Skills allowed",
    autonomy_skills_no: "Skills blocked at this level",
    autonomy_change_hint: "Changing this here is live and immediate for this process — no contradictions, what's picked is what's really active. It doesn't reach a separately-running autopilot container (Docker), and won't survive a restart unless KAFKAF_AUTONOMY_LEVEL is also updated. See docs/SETUP.md#autonomy-levels.",
    autonomy_level_observe: "Observe only",
    autonomy_level_assisted: "Assisted",
    autonomy_level_autonomous: "Fully autonomous",
    autopilot_heading: "Self-learning loop (Autopilot)",
    autopilot_running: "Active — the loop teaches and trains unattended",
    autopilot_stopped: "Emergency stop in effect — the loop stays halted until resumed",
    autopilot_stop_btn: "Emergency stop",
    autopilot_resume_btn: "Resume loop",
    autopilot_hint: "The exact same mechanism as kafkaf-autopilot-ctl — just as a button. A stop takes effect within seconds and persists until explicitly resumed.",
    skills_disabled_title: "Skills are blocked at the current autonomy level",
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
    persona_title: "Persona: the reply's tone and instructions (not a different model)",
    brain_title: "Model: which brain answers — the default, or your own model that grows over time",
    persona_default_desc: "Neutral tone, direct answers",
    persona_researcher_desc: "In-depth tone, answers with reasoning",
    persona_coach_desc: "Encouraging tone, asks questions and guides you",
    brain_default_desc: "A model running locally via Ollama",
    brain_own_desc: "Your private model — starts empty, learns from what you teach it (Control Panel)",
    council_title: "Council: several models answer in parallel, synthesized into one reply",
    skills_title: "Skills: lets the model use real tools — web search, calculator, files, and more",
    control_title_tip: "Control & status: autonomy level, own model, recent activity",
    welcome_title: "Welcome to KafKaf",
    welcome_body: "A private assistant that runs on your own machine and grows over time. Pick a persona and tone, turn on \"Council\" to get one answer synthesized from several models, or \"Skills\" to let it use real tools like web search and a calculator. Just start typing below.",
    typing_indicator: "Typing...",
    council_disabled_title: "Council needs configuration (KAFKAF_COUNCIL_BRAINS) — see docs/SETUP.md",
    growth_heading: "Teach & grow our own model",
    growth_intro: "Our private model starts knowing nothing — it only learns from what's taught here, and improves with training.",
    growth_topic_label: "Topic",
    growth_topic_placeholder: "e.g. photosynthesis",
    growth_fact_label: "Fact (for direct teaching)",
    growth_fact_placeholder: "Write what the model should know...",
    growth_teach_btn: "Teach this fact",
    growth_distill_btn: "Ask the main model to explain & teach it",
    growth_train_label: "Training steps",
    growth_train_btn: "Train now",
    growth_working: "Working...",
    growth_taught_ok: "Learned and saved.",
    growth_train_ok: "Training complete.",
    growth_error: "Something failed: ",
    growth_missing_fields: "Please fill in a topic (and a fact, for direct teaching)",
    workspace_heading: "Skills workspace directory",
    workspace_intro: "The files, document_search, and journal skills can only touch this directory — exactly like a working directory in Claude Code. Changing it here is live and immediate.",
    workspace_current_label: "Current directory",
    workspace_input_placeholder: "e.g. C:\\Users\\name\\Desktop",
    workspace_set_btn: "Set directory",
    workspace_set_ok: "Directory updated.",
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
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
  });

  const langToggleEl = document.getElementById("lang-toggle");
  if (langToggleEl) {
    langToggleEl.textContent = lang === "he" ? "EN" : "עב";
    langToggleEl.setAttribute("aria-label", lang === "he" ? "Switch to English" : "עברית");
  }

  document.dispatchEvent(new CustomEvent("kafkaf-lang-changed"));
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
