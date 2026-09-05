const stages = [
  ["resolve_metric", "Resolve metric"],
  ["compile_query", "Compile query"],
  ["validate_sql", "Validate SQL"],
  ["execute_sql", "Execute SQL"],
  ["verify_evidence", "Verify evidence"],
];

const byId = (id) => document.getElementById(id);
const pretty = (value, fallback) => value === undefined || value === null
  ? fallback
  : JSON.stringify(value, null, 2);

function renderTrace(result) {
  const actual = Array.isArray(result.trace) ? result.trace : [];
  const lastActual = actual.at(-1);
  byId("trace").replaceChildren(...stages.map(([key, label]) => {
    const item = document.createElement("li");
    const ran = actual.includes(key);
    const isTerminalFailure = ran && key === lastActual && result.status !== "OK";
    item.className = isTerminalFailure
      ? (result.status === "ERROR" || result.status === "BLOCKED" ? "failed" : "stopped")
      : (ran ? "passed" : "not-executed");

    const marker = document.createElement("span");
    marker.className = "trace-marker";
    const name = document.createElement("span");
    name.textContent = label;
    const state = document.createElement("span");
    state.className = "trace-state";
    state.textContent = isTerminalFailure ? result.status : (ran ? "executed" : "not executed");
    item.append(marker, name, state);
    return item;
  }));
}

function renderResult(result) {
  const status = result.status || "ERROR";
  const statusNode = byId("result-status");
  statusNode.textContent = status;
  statusNode.className = `status ${status}`;
  byId("metric").textContent = result.metric ?? result.semantic_plan?.metric ?? "—";
  byId("verified").textContent = result.verified === undefined ? "not reached" : String(result.verified);
  byId("executor").textContent = result.executor ?? "not reached";
  byId("policy").textContent = result.policy_allowed === undefined ? "not reached" : (result.policy_allowed ? "allowed" : "blocked");
  byId("evidence").textContent = pretty(result.evidence, "No verified evidence returned.");
  byId("reason").textContent = result.reason ?? "No reason field returned by DataAgent.";
  byId("semantic-plan").textContent = pretty(result.semantic_plan, "Not produced.");
  byId("sql").textContent = result.sql ?? "Not compiled.";
  byId("params").textContent = pretty(result.params, "Not compiled.");
  byId("raw-response").textContent = JSON.stringify(result, null, 2);
  renderTrace(result);
}

async function runQuery(question) {
  const button = byId("run-button");
  button.disabled = true;
  button.textContent = "Running…";
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const result = await response.json();
    renderResult(result);
  } catch (_error) {
    renderResult({ status: "ERROR", reason: "Could not reach the local API.", trace: [] });
  } finally {
    button.disabled = false;
    button.textContent = "Run Query";
  }
}

function renderMeta(meta) {
  const cases = meta.demo_cases.map((demoCase) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${demoCase.label} · ${demoCase.expected_status}`;
    button.title = demoCase.question;
    button.addEventListener("click", () => {
      byId("question").value = demoCase.question;
      runQuery(demoCase.question);
    });
    return button;
  });
  byId("quick-cases").replaceChildren(...cases);

  const benchmark = meta.benchmark;
  byId("benchmark-score").textContent = `${benchmark.passed} / ${benchmark.total}`;
  byId("benchmark-note").textContent = benchmark.note;
  const safetyKeys = ["SAFE_FAILURE", "FALSE_SUCCESS", "UNSAFE_ALLOW", "OVER_BLOCK"];
  byId("benchmark-grid").replaceChildren(...safetyKeys.map((key) => {
    const cell = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = key;
    const value = document.createElement("strong");
    value.textContent = benchmark[key];
    cell.append(label, value);
    return cell;
  }));

  byId("limitations").replaceChildren(...meta.limitations.map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  }));

  byId("architecture").replaceChildren(...meta.architecture.map((name) => {
    const item = document.createElement("div");
    item.className = "architecture-step";
    const label = document.createElement("span");
    label.textContent = name;
    item.append(label);
    return item;
  }));
}

async function initialize() {
  renderTrace({ status: "READY", trace: [] });
  try {
    const [healthResponse, metaResponse] = await Promise.all([
      fetch("/api/health"),
      fetch("/api/demo-meta"),
    ]);
    const health = await healthResponse.json();
    const meta = await metaResponse.json();
    byId("health-text").textContent = health.demo_ready ? "Local demo ready" : "Local demo needs initialization";
    byId("health-dot").className = `pulse ${health.demo_ready ? "ready" : "error"}`;
    byId("executor-mode").textContent = `executor · ${health.executor}`;
    renderMeta(meta);
  } catch (_error) {
    byId("health-text").textContent = "Local service unavailable";
    byId("health-dot").className = "pulse error";
  }
}

byId("query-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = byId("question").value.trim();
  if (question) runQuery(question);
});

initialize();
