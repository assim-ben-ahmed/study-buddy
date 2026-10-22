// AI Study Buddy front end. Set window.STUDY_BUDDY_API before this script to call a backend on another domain.
const API = window.STUDY_BUDDY_API || "";
const $ = (id) => document.getElementById(id);
const state = { mode: "explain", history: [], busy: false };

const SUGGESTIONS = {
  explain: ["Explain photosynthesis", "What is a derivative?", "Explique la loi d'Ohm"],
  homework: ["Solve 2x + 5 = 17 with me", "Help me structure an essay plan", "How do I balance CH4 + O2 → CO2 + H2O?"],
  summarize: ["Summarize the French Revolution", "Summarize the water cycle", "Résume la Seconde Guerre mondiale"],
  plan: ["My maths exam is in 2 weeks", "How should I revise for 4 exams?", "Give me a Pomodoro study routine"],
};
const WELCOME = `**Hello! I'm your AI Study Buddy 👋**

Pick a mode above, then ask me anything:
- 💡 **Explain**: a concept in simple words, with an example
- ✍️ **Homework coach**: we solve it step by step together
- 📄 **Summarize**: a topic or your own notes
- 🎯 **Study plan**: organise your revision

You can also generate a 📝 **quiz** or 🃏 **flashcards** from the tabs above.`;

// ── Safe Markdown: escape everything first, then add a small set of formats ──
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function inline(s) {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}
function markdown(src) {
  const blocks = [];
  const text = escapeHtml(src).replace(/```[\w-]*\n?([\s\S]*?)```/g, (_, code) => {
    blocks.push(`<pre><code>${code.trimEnd()}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  const out = [];
  let list = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^\u0000(\d+)\u0000$/))) { close(); out.push(blocks[+m[1]]); }
    else if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { close(); out.push("<hr>"); }
    else if ((m = line.match(/^#{1,6}\s+(.*)/))) { close(); out.push(`<h4>${inline(m[1])}</h4>`); }
    else if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(m[1])}</li>`); }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(m[1])}</li>`); }
    else if (!line.trim()) { close(); }
    else { close(); out.push(`<p>${inline(line)}</p>`); }
  }
  close();
  return out.join("").replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
}

// ── Status ──
fetch(`${API}/api/health`).then((r) => r.json()).then((h) => {
  $("status").classList.add("live");
  $("status-text").textContent = h.demo ? "Demo mode" : "Online";
}).catch(() => { $("status-text").textContent = "Offline"; });

// ── Tabs and modes ──
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
  for (const name of ["chat", "quiz", "cards"]) $(`panel-${name}`).hidden = name !== tab.dataset.tab;
}));
document.querySelectorAll(".mode").forEach((btn) => btn.addEventListener("click", () => {
  state.mode = btn.dataset.mode;
  document.querySelectorAll(".mode").forEach((b) => b.classList.toggle("active", b === btn));
  showSuggestions();
}));
const level = () => $("level").value;

// ── Chat ──
function addMessage(role, html) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  row.innerHTML = `<div class="avatar">${role === "bot" ? "🤖" : "👤"}</div><div class="bubble">${html}</div>`;
  $("messages").appendChild(row);
  $("messages").scrollTop = $("messages").scrollHeight;
  return row.querySelector(".bubble");
}
function showSuggestions() {
  $("suggestions").innerHTML = "";
  if (state.history.length) return;
  for (const s of SUGGESTIONS[state.mode]) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = s;
    b.onclick = () => send(s);
    $("suggestions").appendChild(b);
  }
}
function reset() {
  state.history = [];
  $("messages").innerHTML = "";
  addMessage("bot", markdown(WELCOME));
  showSuggestions();
}

async function send(text) {
  text = text.trim();
  if (!text || state.busy) return;
  setBusy(true);
  $("input").value = "";
  autosize();
  $("suggestions").innerHTML = "";
  addMessage("user", escapeHtml(text));
  state.history.push({ role: "user", content: text });
  const bubble = addMessage("bot", '<span class="typing"><span></span><span></span><span></span></span>');
  let answer = "";
  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: state.history, mode: state.mode, level: level() }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const ev of events) {
        const data = ev.replace(/^data: /, "");
        if (data === "[DONE]") continue;
        const msg = JSON.parse(data);
        if (msg.error) throw new Error(msg.error);
        answer += msg.delta;
        bubble.innerHTML = markdown(answer);
        $("messages").scrollTop = $("messages").scrollHeight;
      }
    }
    state.history.push({ role: "assistant", content: answer });
  } catch (err) {
    bubble.innerHTML = `${markdown(answer)}<p class="error">⚠️ ${escapeHtml(err.message)}</p>`;
    state.history.pop();
  } finally {
    setBusy(false);
  }
}

// While an answer streams in, the send button is disabled (the text stays in the box).
function setBusy(on) {
  state.busy = on;
  document.body.dataset.busy = on ? "1" : "0";
  document.querySelector(".send").disabled = on;
}

function autosize() {
  const t = $("input");
  t.style.height = "auto";
  t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
}
$("input").addEventListener("input", autosize);
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($("input").value); }
});
$("composer").addEventListener("submit", (e) => { e.preventDefault(); send($("input").value); });
$("clear").addEventListener("click", reset);

// ── Quiz and flashcards ──
async function generate(kind, topic, count, difficulty, button) {
  button.disabled = true;
  const label = button.textContent;
  button.textContent = "Generating…";
  try {
    const res = await fetch(`${API}/api/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, count, difficulty, level: level(), language: navigator.language || "en" }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
    return data;
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function renderQuiz(quiz) {
  const area = $("quiz-area");
  let answered = 0;
  let score = 0;
  area.innerHTML = `<div class="quiz-head"><h3>📝 ${escapeHtml(quiz.topic)}</h3><span class="score" id="score">0 / ${quiz.questions.length}</span></div>`;
  quiz.questions.forEach((q, qi) => {
    const box = document.createElement("div");
    box.className = "q";
    box.innerHTML = `<h4>${qi + 1}. ${inline(escapeHtml(q.question))}</h4>`;
    q.options.forEach((opt, oi) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "opt";
      b.textContent = `${"ABCD"[oi]}. ${opt}`;
      b.onclick = () => {
        box.querySelectorAll(".opt").forEach((o, i) => {
          o.disabled = true;
          if (i === q.answer) o.classList.add("correct");
          else if (i === oi) o.classList.add("incorrect");
        });
        answered += 1;
        if (oi === q.answer) score += 1;
        const why = document.createElement("div");
        why.className = "why";
        why.innerHTML = `${oi === q.answer ? "🎉 <strong>Correct!</strong>" : `❌ The answer was <strong>${"ABCD"[q.answer]}</strong>.`} ${inline(escapeHtml(q.explanation))}`;
        box.appendChild(why);
        $("score").textContent = `${score} / ${quiz.questions.length}`;
        if (answered === quiz.questions.length) {
          const pct = Math.round((100 * score) / quiz.questions.length);
          const end = document.createElement("div");
          end.className = "result";
          end.innerHTML = `${pct >= 80 ? "🌟" : pct >= 50 ? "💪" : "📚"} <strong>${score} / ${quiz.questions.length}</strong> (${pct} %): ${pct >= 80 ? "excellent, you master this topic!" : pct >= 50 ? "good work, review the explanations above." : "keep going: ask the tutor to explain the questions you missed."}`;
          area.appendChild(end);
          end.scrollIntoView({ behavior: "smooth" });
        }
      };
      box.appendChild(b);
    });
    area.appendChild(box);
  });
}

function renderDeck(deck) {
  const area = $("cards-area");
  area.innerHTML = `<div class="quiz-head"><h3>🃏 ${escapeHtml(deck.title)}</h3><span class="score">${deck.cards.length} cards</span></div>
    <p class="hint">Try to answer, then click a card to flip it.</p><div class="deck" id="deck"></div>`;
  for (const c of deck.cards) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card";
    card.innerHTML = `<div class="inner"><div class="face front">${escapeHtml(c.front)}</div><div class="face back">${escapeHtml(c.back)}</div></div>`;
    card.onclick = () => card.classList.toggle("flipped");
    $("deck").appendChild(card);
  }
}

function showError(area, err) {
  $(area).innerHTML = `<p class="empty">⚠️ ${escapeHtml(err.message)}</p>`;
}
$("quiz-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = $("quiz-topic").value.trim();
  if (topic.length < 2) return;
  try { renderQuiz(await generate("quiz", topic, +$("quiz-count").value, $("quiz-difficulty").value, e.submitter)); }
  catch (err) { showError("quiz-area", err); }
});
$("cards-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = $("cards-topic").value.trim();
  if (topic.length < 2) return;
  try { renderDeck(await generate("flashcards", topic, +$("cards-count").value, "medium", e.submitter)); }
  catch (err) { showError("cards-area", err); }
});
$("quiz-area").innerHTML = '<p class="empty">Type a topic or paste your notes, then generate a quiz.<br>Each answer comes with an explanation.</p>';
$("cards-area").innerHTML = '<p class="empty">Turn any topic or your course notes into flashcards to revise with active recall.</p>';

reset();
