const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("message");
const sendBtn = formEl.querySelector(".send-btn");
const brainSelectEl = document.getElementById("brain-select");

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
        brain: brainSelectEl.value || null,
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
