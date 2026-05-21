if (window.location.protocol === "file:") {
  window.location.href = `http://127.0.0.1:5501/${window.location.pathname.split(/[\\/]/).pop() || "index.html"}`;
}

let API_BASE = localStorage.getItem("curricula_api_base") || "http://127.0.0.1:8010";
const pageName = window.location.pathname.split("/").pop();
const state = {
  token: localStorage.getItem("curricula_token") || "",
  me: null,
  view: initialView(),
  authMode: initialAuthMode(),
  data: {},
  message: "",
  error: "",
  loading: false,
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
    const detail = payload && typeof payload === "object"
      ? payload.detail || payload.message || payload.error
      : payload;
    const message = typeof detail === "string"
      ? detail
      : detail
        ? JSON.stringify(detail)
        : "Request failed";
    throw new Error(message);
  }
  return payload;
}

function setMessage(message, error = "") {
  state.message = message;
  state.error = error;
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
  const output = {};
  for (const [key, value] of new FormData(event.target, event.submitter).entries()) {
    if (output[key] === undefined) {
      output[key] = value;
    } else if (Array.isArray(output[key])) {
      output[key].push(value);
    } else {
      output[key] = [output[key], value];
    }
  }
  return output;
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
          <p>Manage approvals, upload learning material, generate Groq-powered roadmaps, and give students a focused practice workspace.</p>
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
          ${state.loading ? `<div class="loading-bar"><span></span></div>` : ""}
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
        <h3>Generate AI Questions</h3>
        <form class="form" data-action="generate-roadmap">
          <label>PDF selections</label>
          <div class="pdf-selection" data-pdf-selection>
            ${pdfSelectionRow(pdfs)}
          </div>
          <button type="button" class="secondary" data-add-pdf>Add PDF</button>
          <label>Roadmap title<input name="title" required /></label>
          <p class="muted">Tip: Select multiple PDFs to mix sources and question types.</p>
          <button type="submit">Create AI question set</button>
        </form>
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
          <label>Answer sheet<textarea name="answer_key" rows="6" placeholder="One answer per line" required></textarea></label>
          <button type="submit">Upload practice exam</button>
        </form>
        <hr />
        <form class="form" data-action="assign-exam">
          <label>Exam<select name="practice_exam_id" required>${options(exams)}</select></label>
          ${targetControls(classes, groups, students)}
          <button type="submit">Assign exam</button>
        </form>
        <hr />
        <form class="form" data-action="unassign-exam">
          <label>Exam<select name="practice_exam_id" required>${options(exams)}</select></label>
          ${targetControls(classes, groups, students)}
          <button type="submit" class="secondary">Remove access</button>
        </form>
        <div style="margin-top:18px">
          <h4 style="margin:0 0 10px">All practice exams</h4>
          ${exams.length ? table(["Exam", "Questions", "Action"], exams.map((exam) => [
            escapeHtml(exam.title),
            exam.question_count || 0,
            `<button class="danger" data-delete-exam="${exam.id}">Delete</button>`,
          ])) : `<p class="muted">No practice exams yet.</p>`}
        </div>
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
          <div class="choice exam-card">
            <div class="exam-header">
              <div>
                <strong>${escapeHtml(exam.title)}</strong>
                <div class="row" style="margin-top:10px">
                  <button class="secondary" data-download-exam="${exam.id}" data-filename="${escapeHtml(exam.title)}">Download</button>
                </div>
                <p class="muted">${exam.question_count || 0} questions · ${exam.question_count ? "Answer each question below" : "Enter one answer per line"}</p>
              </div>
              <div class="exam-answers">
                ${exam.submitted
                  ? `<div class="pill ok">Submitted</div><p class="muted" style="margin:8px 0 0">Score: ${exam.score ?? "-"}%</p>`
                  : `<div class="pill">Answer sheet</div>`}
              </div>
            </div>
            ${exam.submitted
              ? `<p class="muted">You can submit only once for this exam.</p>`
              : `<form class="form" data-action="submit-exam">
                  <input type="hidden" name="practice_exam_id" value="${exam.id}" />
                  ${examAnswerFields(exam)}
                  <button type="submit">Submit answers</button>
                </form>`}
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
              <strong>Mini roadmap ${item.sequence_index}</strong>
              <p class="muted">${escapeHtml(item.question_type)}</p>
              <button data-mini-roadmap="${item.id}">Open question</button>
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
  const miniId = state.data.activeMiniId;
  if (!payload) return `<p class="muted">Open a saved question from the roadmap.</p>`;
  const question = payload.question || {};
  const choices = Array.isArray(question.choices) ? question.choices : [];
  return `
    <form class="form" data-action="submit-attempt">
      <div class="question">
        <span class="pill">${escapeHtml(question.type || "question")}</span>
        <h3>${escapeHtml(question.text || "")}</h3>
        ${choices.map((choice, index) => {
          const label = choice?.label || choice?.id || String.fromCharCode(65 + index);
          const text = choice?.text || choice;
          return `
            <label class="choice">
              <input type="radio" name="selected_answer" value="${escapeHtml(label)}" required />
              <span>${escapeHtml(label)}. ${escapeHtml(text)}</span>
            </label>
          `;
        }).join("")}
        ${payload.hint ? `<p><strong>Hint:</strong> ${escapeHtml(payload.hint)}</p>` : ""}
        ${payload.explanation ? `<p><strong>Explanation:</strong> ${escapeHtml(payload.explanation)}</p>` : ""}
      </div>
      <input type="hidden" name="mini_roadmap_id" value="${miniId}" />
      <input type="hidden" name="question_id" value="${question.id || 0}" />
      <button type="submit">Submit answer</button>
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

function examAnswerFields(exam) {
  const count = Number(exam.question_count || 0);
  if (!count) {
    return `<textarea name="answers" rows="5" placeholder="A&#10;B&#10;C" required></textarea>`;
  }
  return Array.from({ length: count }, (_, index) => `
    <label>Answer ${index + 1}
      <input name="answers" data-answer-input placeholder="A" maxlength="5" required />
    </label>
  `).join("");
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

function roadmapOptions(items) {
  return (items || []).map((item) => `<option value="${item.roadmap_id}">${escapeHtml(item.title)}</option>`).join("");
}

function pdfSelectionRow(pdfs) {
  return `
    <div class="row pdf-row" data-pdf-row>
      <select name="pdf_id" required>${options(pdfs)}</select>
      <input name="page_start" type="number" min="1" placeholder="Start page" />
      <input name="page_end" type="number" min="1" placeholder="End page" />
      <button type="button" class="secondary" data-remove-pdf>Remove</button>
    </div>
  `;
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
      await loadView();
    } catch (error) {
      setMessage("", error.message);
    }
    return;
  }

  const addPdf = event.target.closest("[data-add-pdf]");
  if (addPdf) {
    const container = addPdf.closest("form")?.querySelector("[data-pdf-selection]");
    if (container) {
      container.insertAdjacentHTML("beforeend", pdfSelectionRow(state.data.pdfs || []));
    }
    return;
  }

  const removePdf = event.target.closest("[data-remove-pdf]");
  if (removePdf) {
    const row = removePdf.closest("[data-pdf-row]");
    if (row) row.remove();
    return;
  }

  const miniRoadmap = event.target.closest("[data-mini-roadmap]");
  if (miniRoadmap) {
    try {
      const miniRoadmapId = Number(miniRoadmap.dataset.miniRoadmap);
      const payload = await api("/roadmaps/next-question", {
        method: "POST",
        body: JSON.stringify({ mini_roadmap_id: miniRoadmapId }),
      });
      state.data.question = payload;
      state.data.activeMiniId = miniRoadmapId;
      render();
    } catch (error) {
      setMessage("", error.message);
    }
    return;
  }

  const progress = event.target.closest("[data-progress]");
  if (progress) {
    try {
      state.data.progressDetails = await api(`/roadmaps/admin/progress?roadmap_id=${progress.dataset.progress}`);
      render();
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

  const deleteExam = event.target.closest("[data-delete-exam]");
  if (deleteExam) {
    try {
      await api(`/practice-exams/admin/${deleteExam.dataset.deleteExam}`, { method: "DELETE" });
      await loadView();
      state.message = "Practice exam deleted.";
      render();
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

    if (action === "create-class") await api("/users/classes", { method: "POST", body: JSON.stringify(data) });
    if (action === "create-group") await api("/users/groups", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["class_id"])) });
    if (action === "assign-student") await api("/users/assign-student", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["student_id", "class_id", "group_id"])) });
    if (action === "generate-roadmap") {
      const payload = { title: data.title };
      const pdfIds = Array.isArray(data.pdf_id) ? data.pdf_id : (data.pdf_id ? [data.pdf_id] : []);
      const pageStarts = Array.isArray(data.page_start) ? data.page_start : [data.page_start];
      const pageEnds = Array.isArray(data.page_end) ? data.page_end : [data.page_end];
      payload.pdf_selections = pdfIds.map((pdfId, index) => ({
        pdf_id: Number(pdfId),
        page_start: pageStarts[index] ? Number(pageStarts[index]) : null,
        page_end: pageEnds[index] ? Number(pageEnds[index]) : null,
      })).filter((selection) => selection.pdf_id);
      if (!payload.pdf_selections.length) {
        throw new Error("Select at least one PDF");
      }
      state.loading = true;
      render();
      try {
        await api("/roadmaps/generate", { method: "POST", body: JSON.stringify(payload) });
      } finally {
        state.loading = false;
      }
    }
    if (action === "assign-roadmap") await api("/roadmaps/assign", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["roadmap_id", "target_id"])) });
    if (action === "assign-exam") await api("/practice-exams/admin/assign", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["practice_exam_id", "target_id"])) });
    if (action === "unassign-exam") await api("/practice-exams/admin/unassign", { method: "POST", body: JSON.stringify(cleanNumbers(data, ["practice_exam_id", "target_id"])) });
    if (action === "submit-exam") {
      const payload = cleanNumbers(data, ["practice_exam_id"]);
      payload.answers = parseExamAnswers(data.answers);
      const result = await api("/practice-exams/student/submit", { method: "POST", body: JSON.stringify(payload) });
      await loadView();
      state.message = `Score: ${result.score}% (${result.correct_count}/${result.total_questions})`;
      render();
      return;
    }

    if (action === "upload-pdf") {
      await upload("/admin/upload-pdf", form);
    }
    if (action === "upload-exam") {
      await upload("/practice-exams/admin/upload", form);
    }
    if (action === "load-roadmap-items") {
      state.data.activeRoadmapId = Number(data.roadmap_id);
      state.data.items = await api(`/roadmaps/${data.roadmap_id}/items`);
      render();
      return;
    }
    if (action === "submit-attempt") {
      if (!data.selected_answer) {
        setMessage("", "Choose an answer first.");
        return;
      }
      const submitResult = await api("/roadmaps/submit", {
        method: "POST",
        body: JSON.stringify({
          mini_roadmap_id: Number(data.mini_roadmap_id),
          question_id: Number(data.question_id || 0),
          selected_answer: data.selected_answer,
        }),
      });
      const miniRoadmapId = Number(data.mini_roadmap_id);
      if (submitResult.is_correct) {
        const minis = state.data.items || [];
        const currentIndex = minis.findIndex((item) => item.id === miniRoadmapId);
        const nextMini = currentIndex >= 0 && currentIndex + 1 < minis.length ? minis[currentIndex + 1] : null;
        if (nextMini) {
          state.data.question = await api("/roadmaps/next-question", {
            method: "POST",
            body: JSON.stringify({ mini_roadmap_id: nextMini.id }),
          });
          state.data.activeMiniId = nextMini.id;
        } else {
          state.data.question = null;
          setMessage("Mini roadmaps completed.");
        }
      } else {
        state.data.question = await api("/roadmaps/next-question", {
          method: "POST",
          body: JSON.stringify({ mini_roadmap_id: miniRoadmapId }),
        });
        state.data.activeMiniId = miniRoadmapId;
      }
    }

    await loadView();
    state.message = "Done.";
    render();
  } catch (error) {
    setMessage("", error.message);
  }
});

async function upload(path, form) {
  const payload = new FormData(form);
  await api(path, { method: "POST", body: payload });
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
    throw new Error(payload.detail || "Download failed");
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
    if (Array.isArray(output[key])) {
      output[key] = output[key]
        .map((value) => (value === "" || value == null ? null : Number(value)))
        .filter((value) => value != null);
    } else {
      output[key] = output[key] === "" || output[key] == null ? null : Number(output[key]);
    }
  });
  return output;
}

function parseAnswerList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseExamAnswers(value) {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeLetterAnswer(item)).filter(Boolean);
  }
  return parseAnswerList(value).map((item) => normalizeLetterAnswer(item)).filter(Boolean);
}

function normalizeLetterAnswer(value) {
  return String(value || "").replace(/[^a-zA-Z]/g, "").toUpperCase();
}

document.addEventListener("input", (event) => {
  const input = event.target.closest("[data-answer-input]");
  if (!input) return;
  const normalized = normalizeLetterAnswer(input.value);
  if (input.value !== normalized) input.value = normalized;
});

boot();
