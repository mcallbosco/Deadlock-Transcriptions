"use strict";

const CDN_ROOT = "https://cdn.vlviewer.com/deadlock/audio/sha256";
const state = { queue: [], decisions: new Map(), filtered: [], currentId: null, speed: 1, preferredHash: null };
const el = Object.fromEntries([...document.querySelectorAll("[id]")].map(node => [node.id, node]));

function filenameOf(row) { return row.items?.[0]?.filename || row.recordingId; }
function duration(ms) { return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`; }
function cdnUrl(hash) { return `${CDN_ROOT}/${hash.slice(0, 2)}/${hash}.mp3`; }
function decisionFor(id) { return state.decisions.get(id); }

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { message = (await response.json()).error || message; } catch (_) { /* keep HTTP error */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function toast(message) {
  el.toast.textContent = message;
  el.toast.classList.add("visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => el.toast.classList.remove("visible"), 2800);
}

function updateProgress() {
  const total = state.queue.length;
  const reviewed = state.decisions.size;
  const counts = { transcript: 0, nonspeech: 0, hold: 0 };
  state.decisions.forEach(d => counts[d.status]++);
  el["progress-text"].textContent = `${reviewed} / ${total} reviewed · ${counts.transcript} transcripts · ${counts.nonspeech} nonspeech · ${counts.hold} held`;
  el["progress-bar"].style.width = `${total ? reviewed / total * 100 : 0}%`;
}

function applyFilters() {
  const query = el.search.value.trim().toLowerCase();
  const filter = el["status-filter"].value;
  state.filtered = state.queue.filter(row => {
    const decision = decisionFor(row.recordingId);
    const status = decision?.status || "unreviewed";
    const searchable = [filenameOf(row), row.recordingId, decision?.text, ...candidateTexts(row)].join(" ").toLowerCase();
    return (filter === "all" || status === filter) && (!query || searchable.includes(query));
  });
  const sort = el["sort-order"].value;
  if (sort === "longest") state.filtered.sort((a, b) => b.durationMs - a.durationMs);
  if (sort === "shortest") state.filtered.sort((a, b) => a.durationMs - b.durationMs);
  if (sort === "filename") state.filtered.sort((a, b) => filenameOf(a).localeCompare(filenameOf(b)));
  renderQueue();
  if (!state.filtered.some(row => row.recordingId === state.currentId)) {
    selectRecording(state.filtered[0]?.recordingId || null);
  }
}

function renderQueue() {
  el.queue.replaceChildren();
  if (!state.filtered.length) {
    const empty = document.createElement("div");
    empty.className = "queue-empty";
    empty.textContent = "No recordings match these filters.";
    el.queue.append(empty);
    return;
  }
  const fragment = document.createDocumentFragment();
  state.filtered.forEach(row => {
    const decision = decisionFor(row.recordingId);
    const button = document.createElement("button");
    button.className = `queue-item${row.recordingId === state.currentId ? " active" : ""}`;
    button.dataset.status = decision?.status || "unreviewed";
    button.dataset.id = row.recordingId;
    const dot = document.createElement("span"); dot.className = "dot";
    const name = document.createElement("span"); name.className = "queue-name"; name.textContent = filenameOf(row);
    const time = document.createElement("span"); time.className = "queue-duration"; time.textContent = duration(row.durationMs);
    button.append(dot, name, time);
    button.addEventListener("click", () => selectRecording(row.recordingId));
    fragment.append(button);
  });
  el.queue.append(fragment);
}

function candidateTexts(row) {
  const seen = new Set();
  const texts = [];
  for (const item of row.items || []) {
    for (const option of item.options || []) {
      const text = (option.text || "").trim();
      if (text && !seen.has(text)) { seen.add(text); texts.push(text); }
    }
  }
  return texts;
}

function selectRecording(id) {
  stopAudio();
  state.currentId = id;
  renderQueue();
  const row = state.queue.find(item => item.recordingId === id);
  el["empty-state"].hidden = Boolean(row);
  el["review-card"].hidden = !row;
  if (!row) return;
  const decision = decisionFor(id);
  state.preferredHash = decision?.preferredHash || row.firstPassRepresentativeSha256;
  el.filename.textContent = filenameOf(row);
  el.metadata.textContent = `${duration(row.durationMs)} · ${row.items.length} transcript file${row.items.length === 1 ? "" : "s"} · recording ${row.recordingId.slice(0, 12)}…`;
  el.reason.textContent = row.reason || "No review rationale supplied.";
  el.transcript.value = decision?.text || "";
  el.notes.value = decision?.notes || "";
  setBadge(decision?.status || "unreviewed");
  renderAudio(row);
  renderCandidates(row);
  el.technical.textContent = JSON.stringify(row, null, 2);
  const index = state.filtered.findIndex(item => item.recordingId === id);
  el.previous.disabled = index <= 0;
  el.next.disabled = index < 0 || index >= state.filtered.length - 1;
  document.querySelector(`.queue-item[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
}

function setBadge(status) {
  el["decision-badge"].className = `decision-badge ${status}`;
  el["decision-badge"].textContent = status === "unreviewed" ? "Unreviewed" : status === "nonspeech" ? "Nonspeech" : status === "transcript" ? "Transcript accepted" : "Held / uncertain";
}

function renderAudio(row) {
  el["audio-list"].replaceChildren();
  const hashes = [...new Set([row.firstPassRepresentativeSha256, row.secondPassRepresentativeSha256])];
  hashes.forEach((hash, index) => {
    const card = document.createElement("div");
    card.className = `audio-card${hash === state.preferredHash ? " preferred" : ""}`;
    card.dataset.hash = hash;
    const header = document.createElement("div"); header.className = "audio-card-header";
    const label = document.createElement("div");
    const title = document.createElement("div"); title.className = "audio-label"; title.textContent = `Encode ${index ? "B" : "A"}`;
    const digest = document.createElement("div"); digest.className = "hash"; digest.textContent = `${hash.slice(0, 16)}…`;
    label.append(title, digest);
    const prefer = document.createElement("button"); prefer.className = "prefer secondary"; prefer.textContent = hash === state.preferredHash ? "Preferred" : "Prefer this";
    prefer.addEventListener("click", () => { state.preferredHash = hash; renderAudio(row); });
    header.append(label, prefer);
    const audio = document.createElement("audio");
    audio.controls = true; audio.preload = "none"; audio.src = cdnUrl(hash); audio.dataset.key = index ? "b" : "a"; audio.playbackRate = state.speed;
    audio.addEventListener("play", () => document.querySelectorAll("audio").forEach(other => { if (other !== audio) other.pause(); }));
    card.append(header, audio);
    el["audio-list"].append(card);
  });
}

function renderCandidates(row) {
  el.candidates.replaceChildren();
  const candidates = candidateTexts(row);
  if (!candidates.length) {
    const none = document.createElement("p"); none.className = "no-candidates"; none.textContent = "No nonblank earlier candidates."; el.candidates.append(none); return;
  }
  candidates.forEach((text, index) => {
    const button = document.createElement("button"); button.className = "candidate";
    const content = document.createElement("span"); content.textContent = text;
    const hint = document.createElement("small"); hint.textContent = `Use candidate ${index + 1}`;
    button.append(content, hint);
    button.addEventListener("click", () => { el.transcript.value = text; el.transcript.focus(); });
    el.candidates.append(button);
  });
}

async function save(status) {
  const row = state.queue.find(item => item.recordingId === state.currentId);
  if (!row) return;
  const payload = { status, text: el.transcript.value, notes: el.notes.value, preferredHash: state.preferredHash };
  el["save-state"].textContent = "Saving…";
  try {
    const decision = await request(`/api/decisions/${encodeURIComponent(row.recordingId)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.decisions.set(row.recordingId, decision);
    el["save-state"].textContent = "Saved locally";
    updateProgress();
    applyFilters();
    if (state.currentId === row.recordingId) selectRecording(row.recordingId);
    move(1, true);
  } catch (error) { el["save-state"].textContent = "Save failed"; toast(error.message); }
}

async function clearDecision() {
  if (!state.currentId || !decisionFor(state.currentId)) return;
  try {
    await request(`/api/decisions/${encodeURIComponent(state.currentId)}`, { method: "DELETE" });
    state.decisions.delete(state.currentId);
    updateProgress(); applyFilters(); selectRecording(state.currentId);
  } catch (error) { toast(error.message); }
}

function move(delta, afterSave = false) {
  const index = state.filtered.findIndex(row => row.recordingId === state.currentId);
  if (index < 0) return;
  let next = index + delta;
  if (afterSave && el["status-filter"].value !== "all") next = Math.max(0, index);
  const row = state.filtered[next];
  if (row) selectRecording(row.recordingId);
}

function stopAudio() { document.querySelectorAll("audio").forEach(audio => { audio.pause(); audio.currentTime = 0; }); }
function toggleAudio(key) {
  const playing = [...document.querySelectorAll("audio")].find(candidate => !candidate.paused);
  const audio = key ? document.querySelector(`audio[data-key="${key}"]`) : playing || document.querySelector("audio");
  if (!audio) return;
  if (audio.paused) audio.play().catch(error => toast(error.message)); else audio.pause();
}

el.search.addEventListener("input", applyFilters);
el["status-filter"].addEventListener("change", applyFilters);
el["sort-order"].addEventListener("change", applyFilters);
el.previous.addEventListener("click", () => move(-1));
el.next.addEventListener("click", () => move(1));
el.accept.addEventListener("click", () => save("transcript"));
el.nonspeech.addEventListener("click", () => save("nonspeech"));
el.hold.addEventListener("click", () => save("hold"));
el.clear.addEventListener("click", clearDecision);
document.querySelectorAll("[data-speed]").forEach(button => button.addEventListener("click", () => {
  state.speed = Number(button.dataset.speed);
  document.querySelectorAll("[data-speed]").forEach(node => node.classList.toggle("active", node === button));
  document.querySelectorAll("audio").forEach(audio => audio.playbackRate = state.speed);
}));
document.addEventListener("keydown", event => {
  const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if (editing || event.ctrlKey || event.metaKey || event.altKey) return;
  const key = event.key.toLowerCase();
  if ([" ", "a", "b", "j", "k", "t", "n", "h"].includes(key)) event.preventDefault();
  if (key === " ") toggleAudio();
  if (key === "a" || key === "b") toggleAudio(key);
  if (key === "j") move(1);
  if (key === "k") move(-1);
  if (key === "t") save("transcript");
  if (key === "n") save("nonspeech");
  if (key === "h") save("hold");
});

(async function initialize() {
  try {
    const payload = await request("/api/state");
    state.queue = payload.queue;
    state.decisions = new Map((payload.review.decisions || []).map(decision => [decision.recordingId, decision]));
    updateProgress(); applyFilters();
  } catch (error) { el["empty-state"].textContent = `Could not load review queue: ${error.message}`; toast(error.message); }
})();
