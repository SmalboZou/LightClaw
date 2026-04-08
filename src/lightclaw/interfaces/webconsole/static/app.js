const state = {
  auth: { authenticated: false, user: null },
  setup: null,
  config: null,
  runtime: null,
  providerCapabilities: null,
  skills: [],
  tools: [],
  sessions: [],
  jobs: [],
  jobRuns: [],
  logs: [],
  system: null,
  users: [],
};

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigation();
  bindActions();
  await initializeConsole();
});

async function initializeConsole() {
  setStatus("Checking console state...");
  state.setup = await api("/console/api/setup/status");
  if (state.setup.setup_required) {
    showOverlay("setup-overlay");
    setStatus("Complete the first-time setup.");
    return;
  }
  const auth = await api("/console/api/auth/me");
  if (!auth.authenticated) {
    showOverlay("login-overlay");
    setStatus("Login required.");
    return;
  }
  state.auth = auth;
  await unlockConsole();
}

async function unlockConsole() {
  hideOverlay("setup-overlay");
  hideOverlay("login-overlay");
  document.getElementById("auth-user").textContent = state.auth.user
    ? `${state.auth.user.username} (${state.auth.user.role})`
    : "Anonymous";
  await refreshAll();
}

function bindNavigation() {
  const buttons = Array.from(document.querySelectorAll(".nav-item"));
  const panels = Array.from(document.querySelectorAll(".panel"));
  const title = document.getElementById("panel-title");

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.dataset.panel;
      buttons.forEach((item) => item.classList.toggle("active", item === button));
      panels.forEach((item) => item.classList.toggle("active", item.dataset.panel === panel));
      title.textContent = button.textContent;
    });
  });
}

function bindActions() {
  document.getElementById("setup-form").addEventListener("submit", bootstrapConsole);
  document.getElementById("login-form").addEventListener("submit", loginConsole);
  document.getElementById("logout-button").addEventListener("click", logoutConsole);
  document.getElementById("config-form").addEventListener("submit", saveConfig);
  document.getElementById("chat-form").addEventListener("submit", sendChatMessage);
  document.getElementById("job-form").addEventListener("submit", saveJob);
  document.getElementById("user-form").addEventListener("submit", createUser);
  document.getElementById("refresh-sessions").addEventListener("click", refreshSessions);
  document.getElementById("reload-sessions").addEventListener("click", refreshSessions);
  document.getElementById("reload-jobs").addEventListener("click", refreshJobs);
  document.getElementById("reload-logs").addEventListener("click", refreshLogs);
  document.getElementById("reload-users").addEventListener("click", refreshUsers);
  document.getElementById("reload-runtime-status").addEventListener("click", refreshRuntimeStatus);
  document.getElementById("reload-runtime").addEventListener("click", reloadRuntime);
  document.getElementById("scheduler-start").addEventListener("click", () => controlScheduler("start"));
  document.getElementById("scheduler-stop").addEventListener("click", () => controlScheduler("stop"));
  document.getElementById("scheduler-tick").addEventListener("click", () => controlScheduler("tick"));
  document.getElementById("test-provider").addEventListener("click", testProvider);
  document.getElementById("provider-preset").addEventListener("change", applyConfigPreset);
  document.getElementById("setup-provider-preset").addEventListener("change", applySetupPreset);
}

async function refreshAll() {
  setStatus("Loading console data...");
  await Promise.all([
    refreshConfig(),
    refreshSkills(),
    refreshTools(),
    refreshSessions(),
    refreshJobs(),
    refreshJobRuns(),
    refreshLogs(),
    refreshSystem(),
    refreshRuntimeStatus(),
    refreshProviderCapabilities(),
    refreshUsers(),
  ]);
  setStatus("Console ready.");
}

async function bootstrapConsole(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    admin_username: form.admin_username.value.trim(),
    admin_password: form.admin_password.value,
    provider_backend: form.provider_backend.value,
    provider_model: form.provider_model.value.trim(),
    provider_base_url: form.provider_base_url.value.trim() || null,
    provider_extra_headers_json: form.provider_extra_headers_json.value.trim(),
    provider_api_key: form.provider_api_key.value.trim() || null,
    storage_backend: "sqlite",
    tool_policy: "workspace_write",
    allow_process_exec: false,
    allow_network_access: false,
  };
  state.auth = await api("/console/api/setup/bootstrap", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setStatus("Setup completed. Provider changes are now active.");
  await unlockConsole();
}

async function loginConsole(event) {
  event.preventDefault();
  const form = event.currentTarget;
  state.auth = await api("/console/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      username: form.username.value.trim(),
      password: form.password.value,
    }),
  });
  setStatus("Login successful.");
  await unlockConsole();
}

async function logoutConsole() {
  await api("/console/api/auth/logout", { method: "POST" });
  state.auth = { authenticated: false, user: null };
  showOverlay("login-overlay");
  setStatus("Logged out.");
}

async function refreshConfig() {
  state.config = await api("/console/api/config");
  const form = document.getElementById("config-form");
  form.provider_backend.value = state.config.provider_backend;
  form.provider_model.value = state.config.provider_model;
  form.provider_base_url.value = state.config.provider_base_url || "";
  form.provider_extra_headers_json.value = state.config.provider_extra_headers_json || "";
  form.provider_api_key.value = "";
  form.storage_backend.value = state.config.storage_backend;
  form.tool_policy.value = state.config.tool_policy;
  form.allow_process_exec.checked = state.config.allow_process_exec;
  form.allow_network_access.checked = state.config.allow_network_access;
  document.getElementById("api-key-hint").textContent = state.config.has_provider_api_key
    ? `Current key: ${state.config.provider_api_key_masked}`
    : "No provider key stored.";
  document.getElementById("workspace-root").textContent = state.config.workspace_root;
  document.getElementById("skills-root").textContent = state.config.skills_root;
  document.getElementById("mcp-root").textContent = state.config.mcp_servers_root;
}

async function refreshSkills() {
  state.skills = await api("/skills");
  renderSkillOptions("chat-skills");
  renderSkillOptions("job-skills");
  renderList(
    document.getElementById("skills-list"),
    state.skills,
    (skill) => `
      <article class="skill-card">
        <div class="section-title">
          <h4>${escapeHtml(skill.name)}</h4>
          <span class="badge">${escapeHtml(skill.skill_id)}</span>
        </div>
        <p>${escapeHtml(skill.description)}</p>
        <p class="muted">Tools: ${escapeHtml(skill.tools.join(", ") || "none")}</p>
      </article>
    `,
    "No skills available."
  );
}

async function refreshRuntimeStatus() {
  state.runtime = await api("/console/api/runtime/status");
  const syncBadge = document.getElementById("runtime-sync-badge");
  const synchronized = state.runtime.desired_matches_active;
  syncBadge.textContent = synchronized ? "synchronized" : "drift detected";
  syncBadge.classList.toggle("warning", !synchronized);
  syncBadge.classList.toggle("success", synchronized);

  const items = [
    [
      "Provider",
      `${state.runtime.active.provider_backend} / ${state.runtime.active.provider_model}`,
      `${state.runtime.desired.provider_backend} / ${state.runtime.desired.provider_model}`,
    ],
    [
      "Base URL",
      state.runtime.active.provider_base_url || "default",
      state.runtime.desired.provider_base_url || "default",
    ],
    [
      "Storage",
      state.runtime.active.storage_backend,
      state.runtime.desired.storage_backend,
    ],
    [
      "Tool policy",
      state.runtime.active.tool_policy,
      state.runtime.desired.tool_policy,
    ],
    [
      "Process exec",
      String(state.runtime.active.allow_process_exec),
      String(state.runtime.desired.allow_process_exec),
    ],
    [
      "Network access",
      String(state.runtime.active.allow_network_access),
      String(state.runtime.desired.allow_network_access),
    ],
    [
      "Last applied",
      formatTime(state.runtime.last_applied_at),
      state.runtime.last_reload_reason || "unknown",
    ],
  ];
  document.getElementById("runtime-status-grid").innerHTML = items
    .map(
      ([label, active, desired]) => `
        <article class="status-card">
          <p class="meta-label">${escapeHtml(label)}</p>
          <p><strong>Active:</strong> ${escapeHtml(active)}</p>
          <p><strong>Desired:</strong> ${escapeHtml(desired)}</p>
        </article>
      `
    )
    .join("");
}

async function reloadRuntime() {
  const result = await api("/console/api/runtime/reload", { method: "POST" });
  setStatus(
    `Runtime reloaded: ${result.provider_backend} / ${result.provider_model}`
  );
  await Promise.all([refreshRuntimeStatus(), refreshProviderCapabilities(), refreshSystem()]);
}

async function refreshProviderCapabilities() {
  state.providerCapabilities = await api("/console/api/provider/capabilities");
  const badge = document.getElementById("provider-capability-badge");
  badge.textContent = `${state.providerCapabilities.backend} / ${state.providerCapabilities.model || "default"}`;
  const items = [
    ["Tools", String(state.providerCapabilities.supports_tools)],
    ["Streaming", String(state.providerCapabilities.supports_streaming)],
    ["Usage reporting", String(state.providerCapabilities.supports_usage_reporting)],
  ];
  document.getElementById("provider-capabilities-grid").innerHTML = items
    .map(
      ([label, value]) => `
        <article class="status-card">
          <p class="meta-label">${escapeHtml(label)}</p>
          <p>${escapeHtml(value)}</p>
        </article>
      `
    )
    .join("");
}

async function refreshTools() {
  state.tools = await api("/console/api/tools");
  renderList(
    document.getElementById("tools-list"),
    state.tools,
    (tool) => `
      <article class="tool-card">
        <div class="section-title">
          <h4>${escapeHtml(tool.name)}</h4>
          <span class="badge">${escapeHtml(tool.required_scope)}</span>
        </div>
        <p>${escapeHtml(tool.description)}</p>
        <p class="muted">Timeout: ${tool.timeout_seconds}s</p>
      </article>
    `,
    "No tools registered."
  );
}

async function refreshSessions() {
  state.sessions = await api("/console/api/sessions");
  const container = document.getElementById("sessions-list");
  renderList(
    container,
    state.sessions,
    (session) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(session.session_id)}</strong>
            <p>${escapeHtml(session.preview || "")}</p>
          </div>
          <span class="badge">${session.turn_count} turns</span>
        </header>
        <footer>
          <button type="button" data-session-id="${escapeHtml(session.session_id)}">Open</button>
          <span class="muted">${formatTime(session.updated_at)}</span>
        </footer>
      </article>
    `,
    "No sessions yet."
  );
  container.querySelectorAll("button[data-session-id]").forEach((button) => {
    button.addEventListener("click", () => openSession(button.dataset.sessionId));
  });
}

async function openSession(sessionId) {
  const [payload, diagnostics] = await Promise.all([
    api(`/console/api/sessions/${encodeURIComponent(sessionId)}`),
    api(`/console/api/sessions/${encodeURIComponent(sessionId)}/events`),
  ]);
  document.getElementById("session-detail-title").textContent = sessionId;
  renderList(
    document.getElementById("session-detail"),
    payload.turns,
    (turn) => `
      <article class="turn">
        <strong>${escapeHtml(turn.role)}</strong>
        <p>${escapeHtml(turn.content)}</p>
        <p class="muted">${formatTime(turn.created_at)}</p>
      </article>
    `,
    "This session has no turns."
  );
  renderSessionEvents(diagnostics.events || []);
}

function renderSessionEvents(events) {
  const summary = document.getElementById("session-events-summary");
  const counts = summarizeEventTypes(events);
  summary.textContent = events.length
    ? `${events.length} events | tools=${counts.tool} | policy=${counts.policy} | memory=${counts.memory}`
    : "No events loaded";
  renderList(
    document.getElementById("session-events"),
    events,
    (event) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(event.event_type)}</strong>
            <p>${escapeHtml(event.message)}</p>
          </div>
          <span class="badge">${escapeHtml(classifyEvent(event.event_type))}</span>
        </header>
        <p class="muted">${formatTime(event.created_at)}</p>
      </article>
    `,
    "No session events yet."
  );
}

async function refreshJobs() {
  state.jobs = await api("/console/api/jobs");
  const container = document.getElementById("jobs-list");
  renderList(
    container,
    state.jobs,
    (job) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(job.name)}</strong>
            <p>${escapeHtml(job.input_prompt)}</p>
          </div>
          <span class="badge">${escapeHtml(job.enabled ? "enabled" : "disabled")}</span>
        </header>
        <p class="muted">ID: ${escapeHtml(job.job_id)} | Cron: ${escapeHtml(job.cron)}</p>
        <p class="muted">Skills: ${escapeHtml((job.skills || []).join(", ") || "none")}</p>
        <p class="muted">Last status: ${escapeHtml(job.last_status || "never run")}</p>
        <footer>
          <button type="button" data-run-job="${escapeHtml(job.job_id)}">Run Now</button>
          <button type="button" data-open-job-runs="${escapeHtml(job.job_id)}">View Runs</button>
        </footer>
      </article>
    `,
    "No jobs configured."
  );
  container.querySelectorAll("button[data-run-job]").forEach((button) => {
    button.addEventListener("click", () => runJob(button.dataset.runJob));
  });
  container.querySelectorAll("button[data-open-job-runs]").forEach((button) => {
    button.addEventListener("click", () => refreshJobRuns(button.dataset.openJobRuns));
  });
}

async function refreshJobRuns(jobId = null) {
  const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  state.jobRuns = await api(`/console/api/job-runs${query}`);
  document.getElementById("job-runs-title").textContent = jobId
    ? `Runs for ${jobId}`
    : "Latest job executions";
  renderList(
    document.getElementById("job-runs-list"),
    state.jobRuns,
    (run) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(run.job_id)}</strong>
            <p>${escapeHtml(run.output_text || run.error_message || run.input_prompt)}</p>
          </div>
          <span class="badge">${escapeHtml(run.status)}</span>
        </header>
        <p class="muted">Trigger: ${escapeHtml(run.trigger)} | Started: ${formatTime(run.started_at)}</p>
        <p class="muted">Completed: ${escapeHtml(formatTime(run.completed_at))}</p>
        <footer>
          <button type="button" data-open-run-id="${escapeHtml(run.run_id)}">Open Detail</button>
        </footer>
      </article>
    `,
    "No job runs yet."
  );
  document.querySelectorAll("button[data-open-run-id]").forEach((button) => {
    button.addEventListener("click", () => openJobRun(button.dataset.openRunId));
  });
}

async function openJobRun(runId) {
  const payload = await api(`/console/api/job-runs/${encodeURIComponent(runId)}`);
  document.getElementById("job-run-detail-title").textContent = `${payload.run.job_id} / ${payload.run.run_id}`;
  const items = [
    ["Status", payload.run.status],
    ["Trigger", payload.run.trigger],
    ["Session", payload.session_id],
    ["Started", formatTime(payload.run.started_at)],
    ["Completed", formatTime(payload.run.completed_at)],
    ["Input", payload.run.input_prompt],
    ["Output", payload.run.output_text || "none"],
    ["Error", payload.run.error_message || "none"],
  ];
  const eventsHtml = (payload.events || [])
    .map(
      (event) => `
        <article class="turn">
          <strong>${escapeHtml(event.event_type)}</strong>
          <p>${escapeHtml(event.message)}</p>
          <p class="muted">${formatTime(event.created_at)}</p>
        </article>
      `
    )
    .join("");
  document.getElementById("job-run-detail").classList.remove("empty");
  document.getElementById("job-run-detail").innerHTML =
    items
      .map(
        ([label, value]) => `
          <article class="turn">
            <strong>${escapeHtml(label)}</strong>
            <p>${escapeHtml(value)}</p>
          </article>
        `
      )
      .join("") + (eventsHtml || '<article class="turn"><strong>Events</strong><p>No events recorded.</p></article>');
}

async function refreshLogs() {
  state.logs = await api("/console/api/logs");
  renderList(
    document.getElementById("logs-list"),
    state.logs.slice(-50).reverse(),
    (event) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(event.event_type)}</strong>
            <p>${escapeHtml(event.message)}</p>
          </div>
          <span class="badge">${escapeHtml(event.session_id || "global")}</span>
        </header>
        <p class="muted">${formatTime(event.created_at)}</p>
      </article>
    `,
    "No execution logs yet."
  );
}

async function refreshSystem() {
  state.system = await api("/console/api/system");
  const items = [
    ["App", state.system.app_name],
    ["Environment", state.system.env],
    ["Storage", state.system.storage_backend],
    ["Provider", `${state.system.provider_backend} / ${state.system.provider_model}`],
    ["Scheduler", state.system.scheduler_running ? "running" : "stopped"],
    ["Poll seconds", String(state.system.scheduler_poll_seconds)],
    ["Schema current", state.system.current_schema_version || "none"],
    ["Schema latest", state.system.latest_schema_version || "none"],
    [
      "Pending migrations",
      state.system.pending_schema_versions.length ? state.system.pending_schema_versions.join(", ") : "none",
    ],
  ];
  document.getElementById("system-grid").innerHTML = items
    .map(
      ([label, value]) => `
        <article class="status-card">
          <p class="meta-label">${escapeHtml(label)}</p>
          <p>${escapeHtml(value)}</p>
        </article>
      `
    )
    .join("");
  document.getElementById("scheduler-inline-status").textContent = state.system.scheduler_running ? "running" : "stopped";
}

async function refreshUsers() {
  try {
    state.users = await api("/console/api/users");
  } catch (error) {
    state.users = [];
  }
  renderList(
    document.getElementById("users-list"),
    state.users,
    (user) => `
      <article class="list-item">
        <header>
          <div>
            <strong>${escapeHtml(user.username)}</strong>
            <p>${escapeHtml(user.role)}</p>
          </div>
        </header>
        <p class="muted">${formatTime(user.created_at)}</p>
      </article>
    `,
    "No users loaded."
  );
}

async function saveConfig(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    provider_backend: form.provider_backend.value,
    provider_model: form.provider_model.value,
    provider_base_url: form.provider_base_url.value,
    provider_extra_headers_json: form.provider_extra_headers_json.value,
    provider_api_key: form.provider_api_key.value,
    storage_backend: form.storage_backend.value,
    tool_policy: form.tool_policy.value,
    allow_process_exec: form.allow_process_exec.checked,
    allow_network_access: form.allow_network_access.checked,
  };
  const result = await api("/console/api/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setStatus(
    result.requires_restart
      ? "Configuration saved. Restart is required for this change."
      : "Configuration saved and applied."
  );
  await refreshConfig();
  await Promise.all([refreshSystem(), refreshRuntimeStatus()]);
  await refreshProviderCapabilities();
}

async function testProvider() {
  const form = document.getElementById("config-form");
  const payload = {
    provider_backend: form.provider_backend.value,
    provider_model: form.provider_model.value,
    provider_base_url: form.provider_base_url.value || null,
    provider_extra_headers_json: form.provider_extra_headers_json.value || "",
    provider_api_key: form.provider_api_key.value || null,
  };
  const result = await api("/console/api/provider/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setStatus(result.message);
}

async function sendChatMessage(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = form.message.value.trim();
  if (!message) {
    setStatus("Enter a message before sending.", true);
    return;
  }
  const payload = {
    session_id: form.session_id.value,
    message,
    skills: selectedSkills(form, "#chat-skills"),
  };
  const output = document.getElementById("chat-output");
  appendTurn(output, "user", message, new Date().toISOString());
  form.message.value = "";
  setStatus("Streaming response...");
  const response = await fetch("/console/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({ message: "Streaming failed." }));
    setStatus(error.message || "Streaming failed.", true);
    return;
  }
  if (output.classList.contains("empty")) {
    output.classList.remove("empty");
    output.innerHTML = "";
  }
  const assistantId = `assistant-${Date.now()}`;
  output.insertAdjacentHTML(
    "beforeend",
    `<article class="turn" id="${assistantId}"><strong>assistant</strong><p></p><p class="muted">streaming...</p></article>`
  );
  const target = document.querySelector(`#${assistantId} p`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      handleSseChunk(part, target, output);
    }
  }
  setStatus("Reply received.");
  await Promise.all([refreshSessions(), refreshLogs()]);
}

function handleSseChunk(chunk, target, output) {
  const lines = chunk.split("\n");
  const event = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim();
  const rawData = lines.find((line) => line.startsWith("data:"))?.replace("data:", "").trim();
  if (!event || !rawData) {
    return;
  }
  const data = JSON.parse(rawData);
  if (event === "delta") {
    target.textContent += data.text || "";
  }
  if (event === "tool_result") {
    appendTurn(output, `tool:${data.name}`, data.output, new Date().toISOString());
  }
  if (event === "error") {
    appendTurn(output, "error", data.message || "Streaming request failed.", new Date().toISOString());
    setStatus(data.message || "Streaming request failed.", true);
  }
}

async function saveJob(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = {
    job_id: form.job_id.value.trim(),
    name: form.name.value.trim(),
    cron: form.cron.value.trim(),
    enabled: form.enabled.checked,
    input_prompt: form.input_prompt.value.trim(),
    target_channel: form.target_channel.value.trim() || "scheduler",
    target_destination: form.target_destination.value.trim() || null,
    skills: selectedSkills(form, "#job-skills"),
    policy_mode: form.policy_mode.value,
  };
  if (!payload.job_id || !payload.name || !payload.cron || !payload.input_prompt) {
    setStatus("Job ID, name, cron, and prompt are required.", true);
    return;
  }
  await api("/console/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setStatus(`Job ${payload.job_id} saved.`);
  form.reset();
  form.target_channel.value = "scheduler";
  form.policy_mode.value = "workspace_write";
  form.cron.value = "0 9 * * *";
  form.enabled.checked = true;
  clearSkillSelection("#job-skills");
  await Promise.all([refreshJobs(), refreshJobRuns(payload.job_id), refreshLogs(), refreshSystem()]);
}

async function runJob(jobId) {
  await api(`/console/api/jobs/${encodeURIComponent(jobId)}/run`, { method: "POST" });
  setStatus(`Job ${jobId} executed.`);
  await Promise.all([refreshJobs(), refreshJobRuns(jobId), refreshLogs()]);
}

async function controlScheduler(action) {
  const endpoint = action === "tick" ? "/scheduler/tick" : `/scheduler/${action}`;
  await api(endpoint, { method: "POST" });
  setStatus(`Scheduler ${action} completed.`);
  await Promise.all([refreshJobs(), refreshJobRuns(), refreshLogs(), refreshSystem()]);
}

async function createUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  await api("/console/api/users", {
    method: "POST",
    body: JSON.stringify({
      username: form.username.value.trim(),
      password: form.password.value,
      role: form.role.value,
    }),
  });
  form.reset();
  setStatus("User created.");
  await refreshUsers();
}

function renderSkillOptions(targetId) {
  const container = document.getElementById(targetId);
  container.innerHTML = state.skills.length
    ? state.skills
        .map(
          (skill) => `
            <label class="pill-option">
              <input type="checkbox" value="${escapeHtml(skill.skill_id)}" />
              <span>${escapeHtml(skill.name)}</span>
            </label>
          `
        )
        .join("")
    : '<span class="muted">No skills available.</span>';
}

function renderList(container, items, renderer, emptyText) {
  if (!items.length) {
    container.classList.add("empty");
    container.innerHTML = emptyText;
    return;
  }
  container.classList.remove("empty");
  container.innerHTML = items.map(renderer).join("");
}

function appendTurn(container, role, content, createdAt) {
  if (container.classList.contains("empty")) {
    container.classList.remove("empty");
    container.innerHTML = "";
  }
  container.insertAdjacentHTML(
    "beforeend",
    `
      <article class="turn">
        <strong>${escapeHtml(role)}</strong>
        <p>${escapeHtml(content)}</p>
        <p class="muted">${formatTime(createdAt)}</p>
      </article>
    `
  );
}

function selectedSkills(form, containerSelector) {
  return Array.from(form.querySelectorAll(`${containerSelector} input:checked`)).map((input) => input.value);
}

function clearSkillSelection(containerSelector) {
  document.querySelectorAll(`${containerSelector} input`).forEach((input) => {
    input.checked = false;
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "same-origin",
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const error = await response.json();
      message = error.message || error.detail || message;
    } catch (_error) {
      // Ignore response parsing failures and use the HTTP status.
    }
    throw new Error(message);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return response.text();
  }
  return response.json();
}

function showOverlay(id) {
  document.getElementById(id).classList.remove("hidden");
}

function hideOverlay(id) {
  document.getElementById(id).classList.add("hidden");
}

function setStatus(message, isError = false) {
  const el = document.getElementById("global-status");
  el.textContent = message;
  el.classList.toggle("danger", isError);
  el.classList.toggle("success", !isError);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTime(value) {
  if (!value) {
    return "unknown time";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function summarizeEventTypes(events) {
  return events.reduce(
    (acc, event) => {
      const category = classifyEvent(event.event_type);
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    },
    { tool: 0, policy: 0, memory: 0, runtime: 0 }
  );
}

function classifyEvent(eventType) {
  if (eventType.startsWith("tool_")) {
    return "tool";
  }
  if (eventType.startsWith("memory_")) {
    return "memory";
  }
  if (eventType.includes("policy")) {
    return "policy";
  }
  return "runtime";
}

function applyConfigPreset(event) {
  applyPresetToForm(document.getElementById("config-form"), event.currentTarget.value);
}

function applySetupPreset(event) {
  applyPresetToForm(document.getElementById("setup-form"), event.currentTarget.value);
}

function applyPresetToForm(form, preset) {
  const presets = {
    openai: {
      provider_backend: "openai_compatible",
      provider_base_url: "https://api.openai.com/v1",
      provider_model: "gpt-4o-mini",
      provider_extra_headers_json: "",
    },
    openrouter: {
      provider_backend: "openai_compatible",
      provider_base_url: "https://openrouter.ai/api/v1",
      provider_model: "openai/gpt-4o-mini",
      provider_extra_headers_json:
        '{\n  "HTTP-Referer": "https://your-app.example",\n  "X-Title": "LightClaw"\n}',
    },
    anthropic: {
      provider_backend: "anthropic",
      provider_base_url: "https://api.anthropic.com",
      provider_model: "claude-3-5-sonnet-latest",
      provider_extra_headers_json: "",
    },
  };
  const config = presets[preset];
  if (!config) {
    return;
  }
  form.provider_backend.value = config.provider_backend;
  form.provider_base_url.value = config.provider_base_url;
  form.provider_model.value = config.provider_model;
  if (form.provider_extra_headers_json) {
    form.provider_extra_headers_json.value = config.provider_extra_headers_json;
  }
}
