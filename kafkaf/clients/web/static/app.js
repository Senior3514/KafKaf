const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = formEl.querySelector(".send-btn");
const brainSelectEl = document.getElementById("brain-select");
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

const COUNCIL_KEY = "kafkaf-council";
councilToggleEl.checked = localStorage.getItem(COUNCIL_KEY) === "1";
councilToggleEl.addEventListener("change", () => {
  localStorage.setItem(COUNCIL_KEY, councilToggleEl.checked ? "1" : "0");
  brainSelectEl.disabled = councilToggleEl.checked;
  skillsToggleEl.disabled = councilToggleEl.checked; // skills is ignored server-side when council is on
});
brainSelectEl.disabled = councilToggleEl.checked;
skillsToggleEl.disabled = councilToggleEl.checked;

const SKILLS_KEY = "kafkaf-skills";
skillsToggleEl.checked = localStorage.getItem(SKILLS_KEY) === "1";
skillsToggleEl.addEventListener("change", () => {
  localStorage.setItem(SKILLS_KEY, skillsToggleEl.checked ? "1" : "0");
});

function addBubble(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

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

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        brain: councilToggleEl.checked ? null : brainSelectEl.value || null,
        council: councilToggleEl.checked,
        skills: !councilToggleEl.checked && skillsToggleEl.checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Backend returned ${response.status}`);
    }
    addBubble("assistant", data.reply);
  } catch (err) {
    addBubble("error", `שגיאה: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
});
