const state = {
  data: null,
  quiz: null,
  username: "",
  hintMode: "with_hint",
  assignment: null,
  current: 0,
  answers: {},
  savedRecord: null,
};

const $ = (id) => document.getElementById(id);

function imageUrl(path) {
  return `images/${encodeURI(path).replaceAll("%2F", "/")}`;
}

function storageKey(username, quizId) {
  return `calligraphy-human-quiz:${username}:${quizId}`;
}

function displayLabel(label) {
  return String(label || "").split("-").pop();
}

function hintModeLabel(mode) {
  return mode === "image_only" ? "仅图片" : "有提示";
}

function loadHistory() {
  const items = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith("calligraphy-human-result:")) continue;
    try {
      items.push(JSON.parse(localStorage.getItem(key)));
    } catch {
      continue;
    }
  }
  items.sort((a, b) => String(b.saved_at).localeCompare(String(a.saved_at)));
  const panel = $("historyPanel");
  if (!items.length) {
    panel.textContent = "暂无本机历史记录";
    return;
  }
  panel.innerHTML = "<strong>本机历史记录</strong><ul></ul>";
  const list = panel.querySelector("ul");
  for (const item of items.slice(0, 8)) {
    const li = document.createElement("li");
    li.textContent = `${item.username} / ${item.quiz_name || item.quiz_id} / ${item.hint_mode_label || hintModeLabel(item.hint_mode)}：${item.total} 题`;
    list.appendChild(li);
  }
}

function selectedHintMode() {
  return document.querySelector("input[name='hintMode']:checked")?.value || "with_hint";
}

async function fetchAssignment(username, hintMode) {
  const response = await fetch("/api/assignment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, hint_mode: hintMode }),
  });
  if (!response.ok) throw new Error("题库分配失败");
  const data = await response.json();
  return data.assignment;
}

function getAnsweredList() {
  return state.quiz.questions.map((question, index) => {
    const selected = state.answers[question.id] || "";
    return {
      index: index + 1,
      question_id: question.id,
      source_type: question.source_type || question.meta?.source_type || "",
      target_image: question.target_image,
      selected_label: selected,
      answer: question.answer,
      is_correct: selected === question.answer,
    };
  });
}

function updateProgress() {
  const answered = Object.keys(state.answers).length;
  $("progressText").textContent = `${state.current + 1}/${state.quiz.questions.length}  已答 ${answered}`;
  $("modeText").textContent = hintModeLabel(state.hintMode);
  $("prevBtn").disabled = state.current === 0;
  $("nextBtn").disabled = state.current === state.quiz.questions.length - 1;
}

function renderQuestion() {
  const question = state.quiz.questions[state.current];
  const imageOnly = state.hintMode === "image_only";
  $("quizView").classList.toggle("image-only", imageOnly);
  $("quizTitle").textContent = "书法 8 选 1";
  $("userBadge").textContent = state.username;
  $("targetImage").src = imageUrl(question.target_image);

  const grid = $("optionsGrid");
  grid.innerHTML = "";
  const selected = state.answers[question.id];
  for (const option of question.options) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "option-card";
    if (selected === option.label) card.classList.add("selected");
    const visibleLabel = displayLabel(option.label);
    card.innerHTML = imageOnly
      ? `<div class="image-frame"><img alt="候选参照图" src="${imageUrl(option.ref_image)}"></div>`
      : `
        <div class="image-frame"><img alt="${visibleLabel} 参照图" src="${imageUrl(option.ref_image)}"></div>
        <div class="option-label"><span>${option.id}</span><strong>${visibleLabel}</strong><em>${option.source_type || ""}</em></div>
        <div class="option-desc">${option.description || ""}</div>
      `;
    card.addEventListener("click", () => {
      state.answers[question.id] = option.label;
      localStorage.setItem(storageKey(state.username, `${state.quiz.id}:${state.hintMode}`), JSON.stringify(state.answers));
      renderQuestion();
    });
    grid.appendChild(card);
  }
  updateProgress();
}

async function startQuiz(event) {
  event.preventDefault();
  state.username = $("username").value.trim();
  state.hintMode = selectedHintMode();
  state.assignment = await fetchAssignment(state.username, state.hintMode);
  state.quiz = state.data.quizzes.find((quiz) => quiz.id === state.assignment.quiz_id);
  if (!state.quiz) throw new Error("未找到后端分配的题库");
  state.current = 0;
  state.answers = {};
  const saved = localStorage.getItem(storageKey(state.username, `${state.quiz.id}:${state.hintMode}`));
  if (saved) {
    try {
      state.answers = JSON.parse(saved);
    } catch {
      state.answers = {};
    }
  }
  $("startView").classList.add("hidden");
  $("resultView").classList.add("hidden");
  $("quizView").classList.remove("hidden");
  renderQuestion();
}

function finishQuiz() {
  const missing = state.quiz.questions.length - Object.keys(state.answers).length;
  if (missing > 0 && !confirm(`还有 ${missing} 题未作答，确定提交吗？`)) return;

  const answers = getAnsweredList();
  const correct = answers.filter((row) => row.is_correct).length;
  const record = {
    username: state.username,
    quiz_id: state.quiz.id,
    quiz_name: state.quiz.name,
    participant_order: state.assignment?.participant_order,
    hint_mode: state.hintMode,
    hint_mode_label: hintModeLabel(state.hintMode),
    total: answers.length,
    correct,
    accuracy: answers.length ? Number((correct / answers.length).toFixed(4)) : 0,
    answers,
  };

  fetch("/api/attempts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("save failed")))
    .then((data) => showResult(data.record))
    .catch(() => {
      const fallback = { ...record, saved_at: new Date().toISOString(), local_only: true };
      showResult(fallback);
    });
}

function showResult(record) {
  state.savedRecord = record;
  localStorage.setItem(`calligraphy-human-result:${record.username}:${record.quiz_id}:${Date.now()}`, JSON.stringify(record));
  $("quizView").classList.add("hidden");
  $("resultView").classList.remove("hidden");
  $("resultSummary").textContent = `${record.username} 已完成 ${record.total} 题，作答模式：${record.hint_mode_label || hintModeLabel(record.hint_mode)}。`;
}

function downloadCsv() {
  if (!state.savedRecord) return;
  const rows = [
    ["username", "participant_order", "quiz_id", "quiz_name", "hint_mode", "source_type", "index", "question_id", "target_image", "selected_label", "answer", "is_correct"],
    ...state.savedRecord.answers.map((row) => [
      state.savedRecord.username,
      state.savedRecord.participant_order || "",
      state.savedRecord.quiz_id,
      state.savedRecord.quiz_name,
      state.savedRecord.hint_mode || "",
      row.source_type,
      row.index,
      row.question_id,
      row.target_image,
      row.selected_label,
      row.answer,
      row.is_correct,
    ]),
  ];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.savedRecord.username}_${state.savedRecord.quiz_id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function restart() {
  $("resultView").classList.add("hidden");
  $("startView").classList.remove("hidden");
  loadHistory();
}

async function boot() {
  const response = await fetch("data/quizzes.json");
  state.data = await response.json();
  loadHistory();
  $("startForm").addEventListener("submit", (event) => {
    startQuiz(event).catch((error) => {
      alert(error.message);
    });
  });
  $("prevBtn").addEventListener("click", () => {
    state.current = Math.max(0, state.current - 1);
    renderQuestion();
  });
  $("nextBtn").addEventListener("click", () => {
    state.current = Math.min(state.quiz.questions.length - 1, state.current + 1);
    renderQuestion();
  });
  $("finishBtn").addEventListener("click", finishQuiz);
  $("downloadBtn").addEventListener("click", downloadCsv);
  $("restartBtn").addEventListener("click", restart);
}

boot().catch((error) => {
  document.body.textContent = `加载题库失败：${error.message}`;
});
