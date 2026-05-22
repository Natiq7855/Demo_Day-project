if (window.location.protocol === "file:") {
  window.location.href = `http://127.0.0.1:5501/${window.location.pathname.split(/[\\/]/).pop() || "index.html"}`;
}

const DEFAULT_API_BASE =
  (window.CURRICULA_CONFIG && window.CURRICULA_CONFIG.apiBase) || "http://127.0.0.1:8000";
let API_BASE = localStorage.getItem("curricula_api_base") || DEFAULT_API_BASE;
const pageName = window.location.pathname.split("/").pop();
const state = {
  token: localStorage.getItem("curricula_token") || "",
  me: null,
  view: initialView(),
  authMode: initialAuthMode(),
  data: {},
  message: "",
  error: "",
};

const app = document.querySelector("#app");

function headers(json = true) {
  const output = {};
  if (json) output["Content-Type"] = "application/json";
  if (state.token) output.Authorization = `Bearer ${state.token}`;
  return output;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...headers(!(options.body instanceof FormData)), ...(options.headers || {}) },
    });
  } catch (error) {
    throw new Error(
      `Cannot reach backend at ${API_BASE}. Start FastAPI first, then try again.`,
    );
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(formatApiError(payload));
  }
  return payload;
}

function formatApiError(payload) {
  const detail = payload?.detail ?? payload?.message;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item).join(", ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }
  return detail || "Request failed";
}

function setMessage(message, error = "") {
  state.message = message;
  state.error = error;
  render();
}

function renderInPlace() {
  if (!state.token || !state.me) {
    renderAuth();
    return;
  }
  render();
}

function initialAuthMode() {
  if (pageName === "teacher-login.html" || pageName === "admin.html") return "teacher";
  if (pageName === "register.html") return "register";
  return "login";
}

function initialView() {
  if (pageName === "admin.html") return "overview";
  if (pageName === "student.html") return "dashboard";
  return "dashboard";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formData(event) {
  return Object.fromEntries(new FormData(event.target, event.submitter).entries());
}

async function boot() {
  if (!state.token) {
    if (pageName === "student.html") state.authMode = "login";
    if (pageName === "admin.html") state.authMode = "teacher";
    renderAuth();
    return;
  }
  try {
    state.me = await api("/users/me");
    if (!["overview", "students", "content", "analytics", "dashboard", "roadmaps", "profile"].includes(state.view)) {
      state.view = state.me.role === "admin" ? "overview" : "dashboard";
    }
    await loadView();
  } catch (error) {
    localStorage.removeItem("curricula_token");
    state.token = "";
    state.me = null;
    state.error = error.message;
    renderAuth();
  }
}

async function loadView() {
  state.error = "";
  state.message = "";
  try {
    if (state.me.role === "admin") await loadAdmin();
    if (state.me.role === "student") await loadStudent();
  } catch (error) {
    state.error = error.message;
  }
  render();
}

async function refreshContentStudio() {
  const [pdfs, summary, classes, groups, students, exams] = await Promise.all([
    api("/admin/pdfs"),
    api("/roadmaps/admin/summary"),
    api("/users/classes"),
    api("/users/groups"),
    api("/admin/students"),
    api("/practice-exams/admin/list"),
  ]);
  state.data = { ...state.data, pdfs, summary, classes, groups, students, exams };
}

async function refreshStudentsView() {
  const [students, pending, classes, groups] = await Promise.all([
    api("/admin/students"),
    api("/admin/pending-users"),
    api("/users/classes"),
    api("/users/groups"),
  ]);
  state.data = { ...state.data, students, pending, classes, groups };
}

async function loadAdmin() {
  if (state.view === "overview") {
    const [students, pending, summary] = await Promise.all([
      api("/admin/students"),
      api("/admin/pending-users"),
      api("/roadmaps/admin/summary"),
    ]);
    state.data = { students, pending, summary };
  }
  if (state.view === "students") {
    const [students, pending, classes, groups] = await Promise.all([
      api("/admin/students"),
      api("/admin/pending-users"),
      api("/users/classes"),
      api("/users/groups"),
    ]);
    state.data = { students, pending, classes, groups };
  }
  if (state.view === "content") {
    const [pdfs, summary, classes, groups, students, exams] = await Promise.all([
      api("/admin/pdfs"),
      api("/roadmaps/admin/summary"),
      api("/users/classes"),
      api("/users/groups"),
      api("/admin/students"),
      api("/practice-exams/admin/list"),
    ]);
    state.data = { pdfs, summary, classes, groups, students, exams };
  }
  if (state.view === "analytics") {
    const summary = await api("/roadmaps/admin/summary");
    state.data = { summary };
  }
}

async function loadStudent() {
  if (state.view === "dashboard") {
    const [roadmaps, exams] = await Promise.all([
      api("/roadmaps/assigned"),
      api("/practice-exams/student/list"),
    ]);
    const progress = await Promise.all(
      roadmaps.map((roadmap) => api(`/roadmaps/progress?roadmap_id=${roadmap.id}`).catch(() => null)),
    );
    state.data = { roadmaps, exams, progress };
  }
  if (state.view === "roadmaps") {
    const roadmaps = await api("/roadmaps/assigned");
    state.data = { roadmaps, items: state.data.items || [], activeRoadmapId: state.data.activeRoadmapId || "" };
  }
  if (state.view === "profile") {
    state.data = {};
  }
}

function renderAuth() {
  app.innerHTML = `
    <div class="auth-wrap">
      <section class="hero">
        <div>
          <div class="brand"><span class="brand-mark">CA</span> Curricula AI</div>
          <h1>Adaptive learning for every classroom.</h1>
          <p>Manage approvals, upload learning material, generate Gemini-powered roadmaps, and give students a focused practice workspace.</p>
        </div>
      </section>
      <section class="auth-panel">
        <div class="tabs">
          <button class="${state.authMode === "login" ? "active" : ""}" data-auth-tab="login">Student</button>
          <button class="${state.authMode === "teacher" ? "active" : ""}" data-auth-tab="teacher">Teacher</button>
          <button class="${state.authMode === "register" ? "active" : ""}" data-auth-tab="register">Register</button>
        </div>
        ${state.error ? `<div class="alert error">${escapeHtml(state.error)}</div>` : ""}
        <div class="alert" id="api-status">API: ${escapeHtml(API_BASE)}</div>
        ${state.message ? `<div class="alert success">${escapeHtml(state.message)}</div>` : ""}
        ${authForm()}
      </section>
    </div>
  `;
}

function authForm() {
  if (state.authMode === "teacher") return teacherLoginForm();
  if (state.authMode === "register") return registerForm();
  return loginForm();
}

function loginForm() {
  return `
    <form class="form" data-action="login">
      <h2>Student Login</h2>
      <label>Email<input name="email" type="email" required /></label>
      <label>Password<input name="password" type="password" required /></label>
      <button type="submit">Sign in</button>
      <label>API URL<input name="apiBase" value="${escapeHtml(API_BASE)}" /></label>
    </form>
  `;
}

function teacherLoginForm() {
  return `
    <form class="form" data-action="teacher-login">
      <h2>Teacher Login</h2>
      <label>Email<input name="email" type="email" value="teacher@curricula.ai" required /></label>
      <label>Password<input name="password" type="password" required /></label>
      <button type="submit">Open admin dashboard</button>
      <p class="muted">Default demo password is <strong>Teacher@12345</strong>. Change it in backend <code>.env</code>.</p>
      <label>API URL<input name="apiBase" value="${escapeHtml(API_BASE)}" /></label>
    </form>
  `;
}

function registerForm() {
  return `
    <form class="form" data-action="register">
      <h2>Student Registration</h2>
      <label>Full name<input name="full_name" required /></label>
      <label>Email<input name="email" type="email" required /></label>
      <label>Password<input name="password" type="password" minlength="6" required /></label>
      <label>University group
        <select name="university_group" required>
          <option value="I">I</option>
          <option value="II">II</option>
          <option value="III">III</option>
          <option value="IV">IV</option>
        </select>
      </label>
      <div class="grid two">
        <label>Class ID<input name="class_id" type="number" min="1" /></label>
        <label>Group ID<input name="group_id" type="number" min="1" /></label>
      </div>
      <button type="submit">Request access</button>
    </form>
  `;
}

function render() {
  if (!state.token || !state.me) {
    renderAuth();
    return;
  }
  const nav = state.me.role === "admin"
    ? [["overview", "Overview"], ["students", "Students"], ["content", "Content"], ["analytics", "Analytics"]]
    : [["dashboard", "Dashboard"], ["roadmaps", "Roadmaps"], ["profile", "Profile"]];

  app.innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div class="brand"><span class="brand-mark">CA</span> Curricula AI</div>
        <div class="row">
          <span class="pill ${state.me.role === "admin" ? "warn" : "ok"}">${escapeHtml(state.me.role)}</span>
          <span class="muted">${escapeHtml(state.me.email)}</span>
          <button class="secondary" data-action="logout">Logout</button>
        </div>
      </header>
      <div class="layout">
        <aside class="sidebar">
          ${nav.map(([id, label]) => `<button class="nav-button ${state.view === id ? "active" : ""}" data-view="${id}">${label}</button>`).join("")}
        </aside>
        <section class="content">
          ${state.error ? `<div class="alert error">${escapeHtml(state.error)}</div>` : ""}
          ${state.message ? `<div class="alert success">${escapeHtml(state.message)}</div>` : ""}
          ${state.me.role === "admin" ? renderAdmin() : renderStudent()}
        </section>
      </div>
    </div>
  `;
}

function renderAdmin() {
  if (state.view === "overview") return adminOverview();
  if (state.view === "students") return adminStudents();
  if (state.view === "content") return adminContent();
  return adminAnalytics();
}

function adminOverview() {
  const students = state.data.students || [];
  const pending = state.data.pending || [];
  const summary = state.data.summary || [];
  const avg = summary.length ? Math.round(summary.reduce((sum, item) => sum + item.progress, 0) / summary.length) : 0;
  return `
    <div class="section-title"><h2>Teacher Overview</h2><button data-refresh>Refresh</button></div>
    <div class="grid three">
      ${statCard("Students", students.length)}
      ${statCard("Pending", pending.length)}
      ${statCard("Avg progress", `${avg}%`)}
    </div>
    <div class="card" style="margin-top:18px">
      <h3>Roadmap Summary</h3>
      ${roadmapSummaryTable(summary)}
    </div>
  `;
}

function adminStudents() {
  const { students = [], pending = [], classes = [], groups = [] } = state.data;
  return `
    <div class="section-title"><h2>Student Management</h2><button data-refresh>Refresh</button></div>
    <div class="grid two">
      <div class="card">
        <h3>Pending Registrations</h3>
        ${pending.length ? table(["ID", "Email", "Action"], pending.map((user) => [
          user.id,
          user.email,
          `<div class="row"><button data-approve="${user.id}" data-status="approved">Approve</button><button class="danger" data-approve="${user.id}" data-status="rejected">Reject</button></div>`,
        ])) : `<p class="muted">No pending students.</p>`}
      </div>
      <div class="card">
        <h3>Create Class or Group</h3>
        <form class="form" data-action="create-class">
          <label>Class name<input name="name" required /></label>
          <button type="submit">Create class</button>
        </form>
        <hr />
        <form class="form" data-action="create-group">
          <label>Class<select name="class_id" required>${options(classes)}</select></label>
          <label>Group name<input name="name" placeholder="A1, B2, Lab Group" required /></label>
          <button type="submit">Create group</button>
        </form>
      </div>
    </div>
    <div class="card" style="margin-top:18px">
      <h3>Students</h3>
      ${table(["ID", "Email", "Status", "Assign"], students.map((user) => [
        user.id,
        user.email,
        `<span class="pill ${user.status === "approved" ? "ok" : "warn"}">${user.status}</span>`,
        `<form class="row" data-action="assign-student">
          <input type="hidden" name="student_id" value="${user.id}" />
          <select name="class_id"><option value="">Class</option>${options(classes)}</select>
          <select name="group_id"><option value="">Group</option>${options(groups)}</select>
          <button type="submit">Save</button>
        </form>`,
      ]))}
    </div>
  `;
}

function adminContent() {
  const { pdfs = [], summary = [], classes = [], groups = [], students = [], exams = [] } = state.data;
  return `
    <div class="section-title"><h2>Content Studio</h2><button data-refresh>Refresh</button></div>
    <div class="grid two">
      <div class="card">
        <h3>Upload PDF</h3>
        <form class="form" data-action="upload-pdf">
          <label>Title<input name="title" required /></label>
          <label>Chapter<input name="chapter" /></label>
          <label>PDF<input name="file" type="file" accept="application/pdf" required /></label>
          <button type="submit">Upload material</button>
        </form>
      </div>
      <div class="card">
        <h3>Generate Questions</h3>
        <form class="form" data-action="generate-roadmap">
          <label>PDF<select name="pdf_id" required>${pdfOptions(pdfs)}</select></label>
          <p class="muted">Leave both page fields empty to use the full PDF. If you set a range, it must match the uploaded PDF page numbers shown in the list below.</p>
          <label>Roadmap title<input name="title" required /></label>
          <div class="grid two">
            <label>Start page<input name="page_start" type="number" min="1" placeholder="e.g. 1" /></label>
            <label>End page<input name="page_end" type="number" min="1" placeholder="e.g. 12" /></label>
          </div>
          <button type="submit">Create question set</button>
        </form>
      </div>
      <div class="card">
        <h3>Uploaded PDFs</h3>
        ${pdfList(pdfs)}
      </div>
      <div class="card">
        <h3>Assign Roadmap</h3>
        <form class="form" data-action="assign-roadmap">
          <label>Roadmap<select name="roadmap_id" required>${roadmapOptions(summary)}</select></label>
          ${targetControls(classes, groups, students)}
          <button type="submit">Assign roadmap</button>
        </form>
      </div>
      <div class="card">
        <h3>Practice Exam</h3>
        <form class="form" data-action="upload-exam">
          <label>Title<input name="title" required /></label>
          <label>File<input name="file" type="file" required /></label>
          <button type="submit">Upload practice exam</button>
        </form>
        <hr />
        <form class="form" data-action="assign-exam">
          <label>Exam<select name="practice_exam_id" required>${options(exams)}</select></label>
          ${targetControls(classes, groups, students)}
          <button type="submit">Assign exam</button>
        </form>
      </div>
    </div>
  `;
}

function adminAnalytics() {
  const summary = state.data.summary || [];
  return `
    <div class="section-title"><h2>Analytics</h2><button data-refresh>Refresh</button></div>
    <div class="card">${roadmapSummaryTable(summary, true)}</div>
  `;
}

function renderStudent() {
  if (state.view === "dashboard") return studentDashboard();
  if (state.view === "roadmaps") return studentRoadmaps();
  return studentProfile();
}

function studentDashboard() {
  const roadmaps = state.data.roadmaps || [];
  const exams = state.data.exams || [];
  const progress = state.data.progress || [];
  return `
    <div class="section-title"><h2>Student Dashboard</h2><button data-refresh>Refresh</button></div>
    <div class="grid two">
      <div class="card">
        <h3>Assigned Roadmaps</h3>
        ${roadmaps.length ? roadmaps.map((roadmap, index) => roadmapCard(roadmap, progress[index]?.progress || 0)).join("") : `<p class="muted">No roadmap assigned yet.</p>`}
      </div>
      <div class="card">
        <h3>Practice Exams</h3>
        ${exams.length ? exams.map((exam) => `
          <div class="choice">
            <strong>${escapeHtml(exam.title)}</strong>
            <div class="row" style="margin-top:10px">
              <button class="secondary" data-download-exam="${exam.id}" data-filename="${escapeHtml(exam.title)}">Download</button>
              <form class="row" data-action="submit-exam">
                <input type="hidden" name="practice_exam_id" value="${exam.id}" />
                <input name="score" type="number" min="0" max="100" placeholder="Private score" required />
                <button type="submit">Save</button>
              </form>
            </div>
          </div>
        `).join("") : `<p class="muted">No practice exam assigned yet.</p>`}
      </div>
    </div>
  `;
}

function studentRoadmaps() {
  const roadmaps = state.data.roadmaps || [];
  const items = state.data.items || [];
  return `
    <div class="section-title"><h2>Roadmap Questions</h2><button data-refresh>Refresh</button></div>
    <div class="grid two">
      <div class="card">
        <h3>Select Roadmap</h3>
        <form class="form" data-action="load-roadmap-items">
          <label>Roadmap<select name="roadmap_id" required>${options(roadmaps)}</select></label>
          <button type="submit">Load items</button>
        </form>
        <div style="margin-top:18px">
          ${items.length ? items.map((item) => `
            <div class="choice">
              <strong>${item.sequence_index}. ${escapeHtml(item.topic)}</strong>
              <p class="muted">${escapeHtml(item.question_type)} · ${escapeHtml(item.difficulty)}</p>
              <button data-question="${item.id}">Open question</button>
            </div>
          `).join("") : `<p class="muted">Choose a roadmap to see its topics.</p>`}
        </div>
      </div>
      <div class="card">
        <h3>Question Workspace</h3>
        ${renderQuestion()}
      </div>
    </div>
  `;
}

function renderQuestion() {
  const payload = state.data.question;
  const itemId = state.data.activeItemId;
  if (!payload) return `<p class="muted">Open a saved question from the roadmap.</p>`;
  const question = payload.question || {};
  const choices = Array.isArray(question.choices) ? question.choices : [];
  return `
    <div class="question">
      <span class="pill">${escapeHtml(question.type || "question")}</span>
      <h3>${escapeHtml(question.text || "")}</h3>
      ${choices.map((choice) => `<div class="choice">${escapeHtml(choice.label || choice.id || "")}. ${escapeHtml(choice.text || choice)}</div>`).join("")}
      ${payload.hint ? `<p><strong>Hint:</strong> ${escapeHtml(payload.hint)}</p>` : ""}
      ${payload.explanation ? `<p><strong>Explanation:</strong> ${escapeHtml(payload.explanation)}</p>` : ""}
    </div>
    <form class="row" data-action="submit-attempt" style="margin-top:16px">
      <input type="hidden" name="roadmap_item_id" value="${itemId}" />
      <input type="hidden" name="question_id" value="${question.id || 0}" />
      <button name="is_correct" value="true">I got it right</button>
      <button class="secondary" name="is_correct" value="false">I need another</button>
    </form>
  `;
}

function studentProfile() {
  return `
    <div class="section-title"><h2>Profile</h2></div>
    <div class="card">
      ${table(["Field", "Value"], [
        ["Name", state.me.full_name || "-"],
        ["Email", state.me.email],
        ["University group", state.me.university_group || "-"],
        ["Class ID", state.me.class_id || "-"],
        ["Group ID", state.me.group_id || "-"],
        ["Status", state.me.status],
      ])}
    </div>
  `;
}

function statCard(label, value) {
  return `<div class="card stat"><span class="muted">${label}</span><strong>${value}</strong></div>`;
}

function roadmapCard(roadmap, progress) {
  return `
    <div class="choice">
      <strong>${escapeHtml(roadmap.title)}</strong>
      <div class="progress" style="margin-top:10px"><span style="width:${progress}%"></span></div>
      <p class="muted">${progress}% complete</p>
    </div>
  `;
}

function roadmapSummaryTable(summary, includeActions = false) {
  if (!summary.length) return `<p class="muted">No generated roadmaps yet.</p>`;
  return table(
    includeActions ? ["Roadmap", "Items", "Completed", "Progress", "Details"] : ["Roadmap", "Items", "Progress"],
    summary.map((item) => includeActions
      ? [
          item.title,
          item.total_items,
          item.completed_items,
          progressCell(item.progress),
          `<button data-progress="${item.roadmap_id}">Student progress</button>`,
        ]
      : [item.title, item.total_items, progressCell(item.progress)]),
  ) + (state.data.progressDetails ? `<div style="margin-top:18px">${progressDetails()}</div>` : "");
}

function progressDetails() {
  const details = state.data.progressDetails;
  return `
    <h3>Roadmap ${details.roadmap_id} students</h3>
    ${details.students.length ? table(["Student", "Progress"], details.students.map((student) => [
      student.email,
      progressCell(student.progress),
    ])) : `<p class="muted">No students assigned.</p>`}
  `;
}

function progressCell(value) {
  return `<div class="progress"><span style="width:${value}%"></span></div><span class="muted">${value}%</span>`;
}

function table(headers, rows) {
  return `
    <table class="table">
      <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
}

function options(items) {
  return (items || []).map((item) => `<option value="${item.id}">${escapeHtml(item.name || item.title || item.email || `#${item.id}`)}</option>`).join("");
}

function pdfOptions(items) {
  return (items || []).map((item) => {
    const range =
      item.page_min && item.page_max ? ` · pages ${item.page_min}-${item.page_max}` : "";
    const chunks = item.chunks ? ` · ${item.chunks} chunks` : "";
    return `<option value="${item.id}">${escapeHtml(item.title)}${range}${chunks}</option>`;
  }).join("");
}

function pdfList(items) {
  if (!items.length) return `<p class="muted">No PDFs uploaded yet.</p>`;
  return table(
    ["Title", "Pages", "Chunks"],
    items.map((item) => [
      escapeHtml(item.title),
      item.page_max ? `${item.page_min || 1}-${item.page_max}` : "-",
      item.chunks || 0,
    ]),
  );
}

function roadmapOptions(items) {
  return (items || []).map((item) => `<option value="${item.roadmap_id}">${escapeHtml(item.title)}</option>`).join("");
}

function targetControls(classes, groups, students) {
  return `
    <label>Target type
      <select name="target_type" required>
        <option value="class">Class</option>
        <option value="group">Group</option>
        <option value="student">Student</option>
      </select>
    </label>
    <label>Target ID
      <select name="target_id" required>
        <optgroup label="Classes">${options(classes)}</optgroup>
        <optgroup label="Groups">${options(groups)}</optgroup>
        <optgroup label="Students">${options(students)}</optgroup>
      </select>
    </label>
  `;
}

document.addEventListener("click", async (event) => {
  const authTab = event.target.closest("[data-auth-tab]");
  if (authTab) {
    state.authMode = authTab.dataset.authTab;
    state.error = "";
    state.message = "";
    renderAuth();
    return;
  }

  const view = event.target.closest("[data-view]");
  if (view) {
    state.view = view.dataset.view;
    await loadView();
    return;
  }

  if (event.target.closest("[data-refresh]")) {
    await loadView();
    return;
  }

  if (event.target.closest("[data-action='logout']")) {
    localStorage.removeItem("curricula_token");
    state.token = "";
    state.me = null;
    renderAuth();
    return;
  }

  const approve = event.target.closest("[data-approve]");
  if (approve) {
    try {
      await api("/auth/approve", {
        method: "POST",
        body: JSON.stringify({ user_id: Number(approve.dataset.approve), status: approve.dataset.status }),
      });
      if (state.view === "students") {
        await refreshStudentsView();
        setMessage("Student status updated.");
      } else {
        await loadView();
      }
    } catch (error) {
      setMessage("", error.message);
    }
    return;
  }

  const question = event.target.closest("[data-question]");
  if (question) {
    const item = (state.data.items || []).find((entry) => entry.id === Number(question.dataset.question));
    state.data.question = {
      question: item?.question || {
        id: 0,
        type: item?.question_type || "question",
        difficulty: item?.difficulty || "medium",
        text: "No saved question found for this roadmap item.",
        choices: [],
      },
      hint: item?.question?.hint,
      explanation: item?.question?.explanation,
    };
    state.data.activeItemId = Number(question.dataset.question);
    renderInPlace();
    return;
  }

  const progress = event.target.closest("[data-progress]");
  if (progress) {
    try {
      state.data.progressDetails = await api(`/roadmaps/admin/progress?roadmap_id=${progress.dataset.progress}`);
      renderInPlace();
    } catch (error) {
      setMessage("", error.message);
    }
    return;
  }

  const examDownload = event.target.closest("[data-download-exam]");
  if (examDownload) {
    try {
      await downloadFile(
        `/practice-exams/student/download/${examDownload.dataset.downloadExam}`,
        `${examDownload.dataset.filename || "practice-exam"}`,
      );
    } catch (error) {
      setMessage("", error.message);
    }
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("form");
  if (!form) return;
  event.preventDefault();
  const action = form.dataset.action;
  const data = formData(event);

  try {
    if (action === "login" || action === "teacher-login") {
      if (data.apiBase && data.apiBase !== API_BASE) {
        API_BASE = data.apiBase.replace(/\/$/, "");
        localStorage.setItem("curricula_api_base", API_BASE);
      }
      const token = action === "teacher-login"
        ? await api("/auth/teacher-login", {
            method: "POST",
            body: JSON.stringify({ email: data.email, password: data.password }),
          })
        : await api("/auth/login", {
            method: "POST",
            body: new URLSearchParams({ username: data.email, password: data.password }),
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
          });
      state.token = token.access_token;
      localStorage.setItem("curricula_token", state.token);
      await boot();
      return;
    }

    if (action === "register") {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify(cleanNumbers(data, ["class_id", "group_id"])),
      });
      state.authMode = "login";
      setMessage("Registration sent. Wait for teacher approval.");
      return;
    }

    if (action === "create-class") {
      await api("/users/classes", { method: "POST", body: JSON.stringify(data) });
      await refreshStudentsView();
      setMessage("Class created.");
      return;
    }
    if (action === "create-group") {
      await api("/users/groups", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["class_id"])) });
      await refreshStudentsView();
      setMessage("Group created.");
      return;
    }
    if (action === "assign-student") {
      await api("/users/assign-student", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["student_id", "class_id", "group_id"])) });
      await refreshStudentsView();
      setMessage("Student assignment saved.");
      return;
    }
    if (action === "generate-roadmap") {
      const result = await api("/roadmaps/generate", {
        method: "POST",
        body: JSON.stringify(cleanNumbers(data, ["pdf_id", "page_start", "page_end"])),
      });
      if (state.view === "content") await refreshContentStudio();
      setMessage(`Roadmap created (id ${result.roadmap_id}).`);
      return;
    }
    if (action === "assign-roadmap") {
      await api("/roadmaps/assign", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["roadmap_id", "target_id"])) });
      setMessage("Roadmap assigned.");
      return;
    }
    if (action === "assign-exam") {
      await api("/practice-exams/admin/assign", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["practice_exam_id", "target_id"])) });
      setMessage("Practice exam assigned.");
      return;
    }
    if (action === "submit-exam") {
      await api("/practice-exams/student/submit", {
        method: "POST",
        body: JSON.stringify(cleanNumbers(data, ["practice_exam_id", "score"])),
      });
      setMessage("Score saved.");
      return;
    }

    if (action === "upload-pdf") {
      const result = await upload("/admin/upload-pdf", form);
      if (state.view === "content") await refreshContentStudio();
      setMessage(
        `PDF indexed: ${result.pages} pages, ${result.chunks} chunks (${result.total_chars} characters).`,
      );
      return;
    }
    if (action === "upload-exam") {
      await upload("/practice-exams/admin/upload", form);
      if (state.view === "content") await refreshContentStudio();
      setMessage("Practice exam uploaded.");
      return;
    }
    if (action === "load-roadmap-items") {
      state.data.activeRoadmapId = Number(data.roadmap_id);
      state.data.items = await api(`/roadmaps/${data.roadmap_id}/items`);
      state.data.question = null;
      setMessage(`Loaded ${state.data.items.length} roadmap items.`);
      return;
    }
    if (action === "submit-attempt") {
      await api("/roadmaps/submit", {
        method: "POST",
        body: JSON.stringify({
          roadmap_item_id: Number(data.roadmap_item_id),
          question_id: Number(data.question_id || 0),
          is_correct: data.is_correct === "true",
        }),
      });
      state.data.question = null;
      setMessage("Answer recorded.");
      return;
    }

    await loadView();
    setMessage("Done.");
  } catch (error) {
    setMessage("", error.message);
  }
});

async function upload(path, form) {
  const payload = new FormData(form);
  return api(path, { method: "POST", body: payload });
}

async function downloadFile(path, fallbackName) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: headers(false) });
  } catch (error) {
    throw new Error(`Cannot reach backend at ${API_BASE}. Start FastAPI first, then try again.`);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(formatApiError(payload) || "Download failed");
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match ? match[1] : fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function cleanNumbers(data, keys) {
  const output = { ...data };
  keys.forEach((key) => {
    output[key] = output[key] === "" || output[key] == null ? null : Number(output[key]);
  });
  return output;
}

boot();
