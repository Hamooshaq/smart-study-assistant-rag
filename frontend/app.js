const state = {
  user: null,
  documents: [],
  selectedDocument: null,
  authMode: "login",
  settings: { vlmEnabled: false },
  currentQuiz: [],
  studyProgress: null,
  outputMode: "progress",
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "include",
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  let data = {};
  try {
    data = await res.json();
  } catch {}
  if (!res.ok) throw new Error(data.detail || "Request gagal.");
  return data;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function nl2br(value) {
  return esc(value).replace(/\n/g, "<br>");
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatDay(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "short" }).format(date);
}

function setAuthMode(mode) {
  state.authMode = mode;
  $("loginTab").classList.toggle("active", mode === "login");
  $("registerTab").classList.toggle("active", mode === "register");
  $("nameField").classList.toggle("hidden", mode === "login");
  $("authSubmit").textContent = mode === "login" ? "Login" : "Register";
  $("authMessage").textContent = "";
}

function showApp() {
  $("authView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  $("logoutBtn").classList.remove("hidden");
  $("userLabel").textContent = state.user?.name || "";
}

function showAuth() {
  $("authView").classList.remove("hidden");
  $("appView").classList.add("hidden");
  $("logoutBtn").classList.add("hidden");
}

function renderSettings() {
  const toggle = $("vlmToggle");
  toggle.checked = Boolean(state.settings.vlmEnabled);
  toggle.closest(".toggle-row").classList.toggle("active", toggle.checked);
}

async function loadMe() {
  try {
    const data = await api("/api/me");
    state.user = data.user;
    state.settings.vlmEnabled = Boolean(data.user.vlm_enabled);
    showApp();
    await loadSettings();
    await refreshAll();
  } catch {
    showAuth();
  }
}

async function loadSettings() {
  const data = await api("/api/settings");
  state.settings.vlmEnabled = Boolean(data.vlm_enabled);
  renderSettings();
}

async function refreshAll() {
  await Promise.all([loadDocuments(), loadActivity()]);
  if (state.selectedDocument) {
    await loadDocumentWorkspace({ renderProgress: state.outputMode === "progress" });
  }
}

async function loadDocuments() {
  const data = await api("/api/documents");
  state.documents = data.documents;
  if (state.selectedDocument) {
    state.selectedDocument = state.documents.find((doc) => doc.id === state.selectedDocument.id) || null;
  }
  renderDocuments();
  renderSelectedDocument();
  if (!state.selectedDocument) {
    renderEmptyWorkspace();
  }
}

async function loadActivity() {
  const data = await api("/api/activity");
  const labels = {
    register: "Akun dibuat",
    login: "Login",
    logout: "Logout",
    upload_document: "Upload dokumen",
    process_document: "Dokumen diproses",
    delete_document: "Dokumen dihapus",
    chat: "Chat dokumen",
    generate_summary: "Ringkasan",
    generate_flashcards: "Flashcard",
    generate_quiz: "Quiz",
    submit_quiz: "Nilai quiz",
    update_settings: "Pengaturan",
  };
  const list = $("activityList");
  list.innerHTML = data.items.length ? "" : '<p class="muted">Belum ada aktivitas.</p>';
  for (const item of data.items) {
    const div = document.createElement("div");
    div.className = "activity-item";
    div.innerHTML = `
      <strong>${esc(labels[item.action] || item.action)}</strong>
      <span>${esc(item.detail)}</span>
      <small>${esc(formatDate(item.created_at))}</small>
    `;
    list.appendChild(div);
  }
}

function renderDocuments() {
  const list = $("documentsList");
  list.innerHTML = "";
  if (!state.documents.length) {
    list.innerHTML = '<p class="muted">Belum ada dokumen.</p>';
    return;
  }

  for (const doc of state.documents) {
    const active = state.selectedDocument?.id === doc.id;
    const visionText = doc.vision_enabled ? "gambar aktif" : "teks saja";
    const item = document.createElement("div");
    item.className = `doc-item ${active ? "active" : ""}`;
    item.innerHTML = `
      <strong>${esc(doc.original_filename)}</strong>
      <span class="status-${esc(doc.status)}">${esc(doc.status)} - ${doc.chunk_count || 0} chunk - ${doc.visual_chunk_count || 0} visual</span>
      <small>${esc(visionText)}</small>
      ${doc.error ? `<span class="message">${esc(doc.error)}</span>` : ""}
      <div class="doc-actions">
        <button type="button" data-action="select" data-id="${doc.id}">Pilih</button>
        <button type="button" data-action="delete" data-id="${doc.id}">Hapus</button>
      </div>
    `;
    list.appendChild(item);
  }
}

function renderSelectedDocument() {
  const doc = state.selectedDocument;
  const disabled = !doc || doc.status !== "ready";
  $("selectedTitle").textContent = doc ? doc.original_filename : "Pilih dokumen";
  $("selectedMeta").textContent = doc
    ? `${doc.status} - ${doc.file_type.toUpperCase()} - ${doc.chunk_count || 0} chunk - ${doc.visual_chunk_count || 0} visual`
    : "Upload dokumen dulu untuk mulai chat.";
  $("progressBtn").disabled = disabled;
  $("summaryBtn").disabled = disabled;
  $("flashcardBtn").disabled = disabled;
  $("quizBtn").disabled = disabled;
  $("chatSubmit").disabled = disabled;
}

function renderEmptyWorkspace() {
  $("chatLog").innerHTML = '<p class="muted empty-state">Pilih dokumen untuk melihat riwayat chat.</p>';
  $("chatHint").textContent = "Riwayat tanya jawab akan tampil setelah dokumen dipilih.";
  renderOutput(
    "Hasil Belajar",
    "Pilih dokumen untuk melihat progress belajar.",
    '<p class="muted">Ringkasan, flashcard, quiz, dan progress belajar akan tampil di sini.</p>',
    "progress",
  );
}

function renderOutput(title, subtitle, content, mode) {
  $("outputSubtitle").textContent = subtitle || title;
  $("outputContent").innerHTML = content;
  state.outputMode = mode || state.outputMode;
}

function renderLoading(title, message, mode) {
  renderOutput(title, message, `<p class="muted">${esc(message)}</p>`, mode);
}

function addChat(role, content, sources = []) {
  const empty = $("chatLog").querySelector(".empty-state");
  if (empty) empty.remove();

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role === "user" ? "user" : ""}`;
  const label = role === "user" ? "Pengguna" : "Asisten Belajar";
  const sourceHtml = sources.length
    ? `<div class="sources">Sumber: ${sources.map((source) => esc(source.source_label)).join(", ")}</div>`
    : "";
  bubble.innerHTML = `<strong>${label}</strong><p>${nl2br(content)}</p>${sourceHtml}`;
  $("chatLog").appendChild(bubble);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

function renderChatHistory(items) {
  $("chatLog").innerHTML = "";
  if (!items.length) {
    $("chatLog").innerHTML = '<p class="muted empty-state">Belum ada chat untuk dokumen ini.</p>';
    $("chatHint").textContent = "Ajukan pertanyaan berdasarkan isi dokumen.";
    return;
  }
  $("chatHint").textContent = `${items.length} percakapan tersimpan untuk dokumen ini.`;
  for (const item of [...items].reverse()) {
    addChat("user", item.question);
    addChat("assistant", item.answer, item.sources || []);
  }
}

async function loadDocumentWorkspace({ renderProgress = true } = {}) {
  const doc = state.selectedDocument;
  if (!doc) {
    renderEmptyWorkspace();
    return;
  }
  $("chatLog").innerHTML = '<p class="muted empty-state">Memuat riwayat chat...</p>';
  try {
    const [history, progress] = await Promise.all([
      api(`/api/documents/${doc.id}/history`),
      api(`/api/documents/${doc.id}/study-progress`),
    ]);
    renderChatHistory(history.chat || []);
    state.studyProgress = progress;
    if (renderProgress) renderStudyProgress(progress);
  } catch (err) {
    $("chatLog").innerHTML = `<p class="message">${esc(err.message)}</p>`;
  }
}

async function refreshProgress(render = false) {
  const doc = state.selectedDocument;
  if (!doc) return;
  try {
    state.studyProgress = await api(`/api/documents/${doc.id}/study-progress`);
    if (render || state.outputMode === "progress") renderStudyProgress(state.studyProgress);
  } catch {}
}

function metricCard(label, value, hint) {
  return `
    <div class="metric-card">
      <span>${esc(label)}</span>
      <strong>${esc(value)}</strong>
      <small>${esc(hint || "")}</small>
    </div>
  `;
}

function renderStudyProgress(progress) {
  const metrics = progress.metrics || {};
  const daily = progress.daily_minutes || [];
  const maxMinutes = Math.max(1, ...daily.map((item) => item.minutes));
  const score = metrics.last_quiz_score;
  const scoreText = score === null || score === undefined ? "Belum ada" : `${score}%`;
  const averageText = metrics.average_quiz_score === null || metrics.average_quiz_score === undefined
    ? "Belum ada rata-rata"
    : `Rata-rata ${metrics.average_quiz_score}%`;

  const bars = daily.map((item) => {
    const height = Math.max(8, Math.round((item.minutes / maxMinutes) * 100));
    return `
      <div class="bar-item">
        <div class="bar-track"><span style="height:${height}%"></span></div>
        <small>${esc(formatDay(item.date))}</small>
        <strong>${item.minutes}</strong>
      </div>
    `;
  }).join("");

  const recentChat = (progress.recent_chat || []).length
    ? (progress.recent_chat || []).map((item) => `
        <li>
          <strong>${esc(item.question)}</strong>
          <span>${esc(item.answer_excerpt)}</span>
        </li>
      `).join("")
    : '<li><span>Belum ada riwayat chat pada dokumen ini.</span></li>';

  renderOutput(
    "Hasil Belajar",
    "Progress belajar, skor quiz, dan riwayat dari dokumen terpilih.",
    `
      <div class="study-dashboard">
        <div class="metric-grid">
          ${metricCard("Estimasi belajar", `${metrics.estimated_minutes || 0} menit`, "Dihitung dari aktivitas di dokumen")}
          ${metricCard("Chat dokumen", metrics.chat_count || 0, "Pertanyaan yang sudah dijawab")}
          ${metricCard("Flashcard", metrics.flashcard_count || 0, "Kartu latihan tersimpan")}
          ${metricCard("Skor quiz terakhir", scoreText, averageText)}
        </div>

        <section class="study-section">
          <div class="section-row">
            <h3>Waktu Belajar 7 Hari</h3>
            <span>${metrics.quiz_attempt_count || 0} attempt quiz</span>
          </div>
          <div class="bar-chart">${bars}</div>
        </section>

        <section class="study-section">
          <h3>Arah Belajar Berikutnya</h3>
          <ul class="next-steps">
            ${(progress.next_steps || []).map((step) => `<li>${esc(step)}</li>`).join("")}
          </ul>
        </section>

        <section class="study-section">
          <h3>Riwayat Chat Terbaru</h3>
          <ul class="recent-chat">${recentChat}</ul>
        </section>
      </div>
    `,
    "progress",
  );
}

function renderFlashcards(cards) {
  if (!cards.length) {
    renderOutput("Flashcard", "Tidak ada flashcard yang bisa ditampilkan.", '<p class="muted">Coba buat ulang flashcard dari dokumen yang lebih lengkap.</p>', "flashcards");
    return;
  }

  renderOutput(
    "Flashcard",
    "Klik kartu untuk membuka atau menutup jawaban.",
    `
      <div class="flashcard-toolbar">
        <button type="button" data-action="show-all-flashcards">Tampilkan semua</button>
        <button type="button" data-action="hide-all-flashcards">Tutup semua</button>
      </div>
      <div class="flashcard-grid">
        ${cards.map((card, index) => `
          <button class="flashcard" type="button" data-flashcard-index="${index}">
            <span>Kartu ${index + 1}</span>
            <strong>${esc(card.question || "")}</strong>
            <em>${esc(card.answer || "")}</em>
            <small>${esc(card.source || "Sumber dokumen")}</small>
          </button>
        `).join("")}
      </div>
    `,
    "flashcards",
  );
}

function renderQuizForm(quiz) {
  if (!quiz.length) {
    renderOutput("Quiz", "Tidak ada soal yang bisa ditampilkan.", '<p class="muted">Coba buat ulang quiz dari dokumen yang lebih lengkap.</p>', "quiz");
    return;
  }

  state.currentQuiz = quiz;
  renderOutput(
    "Quiz",
    "Jawab semua soal terlebih dahulu. Nilai dan kunci jawaban muncul setelah submit.",
    `
      <form id="quizForm" class="quiz-form">
        ${quiz.map((question, index) => `
          <fieldset class="quiz-card">
            <legend><span>Soal ${index + 1}</span>${esc(question.question || "")}</legend>
            <div class="quiz-options">
              ${(question.options || []).map((option, optionIndex) => `
                <label>
                  <input type="radio" name="q${index}" value="${esc(option)}" />
                  <span>${esc(option)}</span>
                </label>
              `).join("")}
            </div>
            <small>${esc(question.source || "Sumber dokumen")}</small>
          </fieldset>
        `).join("")}
        <p id="quizMessage" class="message"></p>
        <button id="quizSubmit" class="primary" type="submit">Submit Jawaban</button>
      </form>
    `,
    "quiz",
  );
}

function renderQuizResult(result) {
  const total = result.total || 0;
  const correct = result.correct || 0;
  const percent = result.percent || 0;
  renderOutput(
    "Nilai Quiz",
    "Hasil ditampilkan setelah jawaban dikirim.",
    `
      <div class="quiz-score">
        <div class="score-ring" style="--score:${percent}">
          <strong>${percent}%</strong>
          <span>${correct}/${total} benar</span>
        </div>
        <div>
          <h3>Evaluasi Jawaban</h3>
          <p class="muted">Gunakan sumber pada tiap soal untuk mengulang bagian yang belum kuat.</p>
        </div>
      </div>
      <div class="quiz-review">
        ${(result.results || []).map((item, index) => `
          <article class="review-card ${item.is_correct ? "correct" : "wrong"}">
            <div class="section-row">
              <h3>Soal ${index + 1}</h3>
              <span>${item.is_correct ? "Benar" : "Perlu diulang"}</span>
            </div>
            <p><strong>${esc(item.question)}</strong></p>
            <p>Jawaban Anda: ${esc(item.selected_answer || "Belum dijawab")}</p>
            <p>Kunci jawaban: ${esc(item.correct_answer)}</p>
            <small>${esc(item.source || "Sumber dokumen")}</small>
          </article>
        `).join("")}
      </div>
    `,
    "quiz",
  );
}

async function selectDocument(id) {
  state.selectedDocument = state.documents.find((doc) => doc.id === id) || null;
  state.outputMode = "progress";
  state.currentQuiz = [];
  renderDocuments();
  renderSelectedDocument();
  await loadDocumentWorkspace({ renderProgress: true });
}

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  if (target.id === "loginTab") setAuthMode("login");
  if (target.id === "registerTab") setAuthMode("register");

  const flashcard = target.closest(".flashcard");
  if (flashcard) {
    flashcard.classList.toggle("flipped");
    return;
  }

  const actionTarget = target.closest("[data-action]");
  const action = actionTarget?.dataset.action;
  const id = Number(actionTarget?.dataset.id);

  if (action === "select") {
    await selectDocument(id);
  }

  if (action === "delete") {
    await api(`/api/documents/${id}`, { method: "DELETE" });
    if (state.selectedDocument?.id === id) state.selectedDocument = null;
    await refreshAll();
  }

  if (action === "show-all-flashcards") {
    document.querySelectorAll(".flashcard").forEach((card) => card.classList.add("flipped"));
  }

  if (action === "hide-all-flashcards") {
    document.querySelectorAll(".flashcard").forEach((card) => card.classList.remove("flipped"));
  }
});

$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = {
      name: $("nameInput").value,
      email: $("emailInput").value,
      password: $("passwordInput").value,
    };
    const path = state.authMode === "login" ? "/api/login" : "/api/register";
    const data = await api(path, { method: "POST", body: JSON.stringify(payload) });
    state.user = data.user;
    state.settings.vlmEnabled = Boolean(data.user.vlm_enabled);
    showApp();
    renderSettings();
    await refreshAll();
  } catch (err) {
    $("authMessage").textContent = err.message;
  }
});

$("logoutBtn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: JSON.stringify({}) }).catch(() => {});
  state.user = null;
  state.documents = [];
  state.selectedDocument = null;
  showAuth();
});

$("vlmToggle").addEventListener("change", async (event) => {
  const enabled = event.target.checked;
  state.settings.vlmEnabled = enabled;
  renderSettings();
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ vlm_enabled: enabled }) });
    await loadActivity();
  } catch (err) {
    state.settings.vlmEnabled = !enabled;
    renderSettings();
    alert(err.message);
  }
});

$("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("fileInput").files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  fd.append("use_vision", $("vlmToggle").checked ? "true" : "false");

  const button = $("uploadForm").querySelector("button.primary");
  button.disabled = true;
  button.textContent = "Memproses...";
  try {
    const data = await api("/api/documents", { method: "POST", body: fd });
    $("fileInput").value = "";
    await loadDocuments();
    state.selectedDocument = state.documents.find((doc) => doc.id === data.document.id) || data.document;
    renderDocuments();
    renderSelectedDocument();
    await loadDocumentWorkspace({ renderProgress: true });
    await loadActivity();
  } catch (err) {
    alert(err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Upload & Proses";
  }
});

$("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const doc = state.selectedDocument;
  const question = $("questionInput").value.trim();
  if (!doc || !question) return;

  addChat("user", question);
  $("questionInput").value = "";
  $("chatSubmit").disabled = true;
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ document_id: doc.id, question, top_k: 5 }),
    });
    addChat("assistant", data.answer, data.sources);
    await refreshProgress(false);
    await loadActivity();
  } catch (err) {
    addChat("assistant", err.message);
  } finally {
    $("chatSubmit").disabled = false;
  }
});

$("progressBtn").addEventListener("click", async () => {
  await refreshProgress(true);
});

$("summaryBtn").addEventListener("click", async () => {
  const doc = state.selectedDocument;
  if (!doc) return;
  renderLoading("Ringkasan", "Membuat ringkasan...", "summary");
  try {
    const data = await api(`/api/documents/${doc.id}/summary`, { method: "POST", body: JSON.stringify({}) });
    renderOutput("Ringkasan", "Ringkasan belajar dari dokumen terpilih.", `<div class="summary-block">${nl2br(data.summary)}</div>`, "summary");
    await refreshProgress(false);
    await loadActivity();
  } catch (err) {
    renderOutput("Ringkasan", "Ringkasan gagal dibuat.", `<p class="message">${esc(err.message)}</p>`, "summary");
  }
});

$("flashcardBtn").addEventListener("click", async () => {
  const doc = state.selectedDocument;
  if (!doc) return;
  renderLoading("Flashcard", "Membuat flashcard...", "flashcards");
  try {
    const data = await api(`/api/documents/${doc.id}/flashcards`, {
      method: "POST",
      body: JSON.stringify({ count: 10 }),
    });
    renderFlashcards(data.flashcards || []);
    await refreshProgress(false);
    await loadActivity();
  } catch (err) {
    renderOutput("Flashcard", "Flashcard gagal dibuat.", `<p class="message">${esc(err.message)}</p>`, "flashcards");
  }
});

$("quizBtn").addEventListener("click", async () => {
  const doc = state.selectedDocument;
  if (!doc) return;
  renderLoading("Quiz", "Membuat quiz...", "quiz");
  try {
    const data = await api(`/api/documents/${doc.id}/quiz`, {
      method: "POST",
      body: JSON.stringify({ count: 5 }),
    });
    renderQuizForm(data.quiz || []);
    await refreshProgress(false);
    await loadActivity();
  } catch (err) {
    renderOutput("Quiz", "Quiz gagal dibuat.", `<p class="message">${esc(err.message)}</p>`, "quiz");
  }
});

document.addEventListener("submit", async (event) => {
  if (!(event.target instanceof HTMLFormElement) || event.target.id !== "quizForm") return;
  event.preventDefault();
  const doc = state.selectedDocument;
  if (!doc) return;

  const answers = state.currentQuiz.map((_, index) => {
    const checked = event.target.querySelector(`input[name="q${index}"]:checked`);
    return checked ? checked.value : "";
  });
  if (answers.some((answer) => !answer)) {
    $("quizMessage").textContent = "Semua soal perlu dijawab sebelum submit.";
    return;
  }

  $("quizSubmit").disabled = true;
  $("quizSubmit").textContent = "Menilai...";
  try {
    const result = await api(`/api/documents/${doc.id}/quiz/attempts`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
    renderQuizResult(result);
    await refreshProgress(false);
    await loadActivity();
  } catch (err) {
    $("quizMessage").textContent = err.message;
  }
});

setAuthMode("login");
loadMe();
