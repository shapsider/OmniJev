import { TrajectoryScene } from "./trajectory-scene.js";

const params = new URLSearchParams(location.search);
const DATASET = params.get("data") || "transfer-omnijev";
const BASE = params.get("base") || `./data/${DATASET}/`;
const VIEW_W = 940;
const VIEW_H = 720;

const scene = new TrajectoryScene({ width: VIEW_W, height: VIEW_H, pixelRatio: 2 });
document.querySelector("#viewport").appendChild(scene.renderer.domElement);

const [sceneData, frames, meta] = await Promise.all([
  fetch(`${BASE}scene.json`).then((r) => r.json()),
  fetch(`${BASE}frames.json`).then((r) => r.json()),
  fetch(`${BASE}meta.json`).then((r) => r.json()),
]);
scene.load(sceneData);

const $ = (selector) => document.querySelector(selector);
const num = (value, digits = 2) =>
  value === null || value === undefined ? "n/a" : Number(value).toFixed(digits);

/* ---------- static panel ---------- */
$("#task-name").textContent = meta.task_name;
$("#task-sub").innerHTML = `Trajectory replay · seed <code>${meta.seed}</code>`;
$("#cycle-total").textContent = meta.cycles;
$("#note").innerHTML =
  `episode <code>${meta.episode_id}</code> · ${meta.frame_count} saved poses · ` +
  `${meta.sim_seconds} s simulated · reconstructed offline from the released record`;

$("#spec-rows").innerHTML = [
  `observation <b>${meta.observation_mode}</b> · control <b>${meta.control_mode}</b>`,
  `backbone <code>${meta.model}</code> · policy <code>${meta.policy_version}</code>`,
  `model calls <b>${meta.model_calls}</b> · output tokens <b>${meta.output_tokens}</b>`,
  `wall clock <b>${meta.wall_seconds} s</b> · status <b>${meta.status}</b>`,
].join("<br />");
$("#verdict-sub").textContent =
  meta.status === "completed" ? "physical final state verified" : meta.status;

/* Timeline ticks at each decision cycle boundary. */
const cycleStart = new Map();
frames.forEach((frame, index) => {
  const cycle = frame.cycle ?? 0;
  if (!cycleStart.has(cycle)) cycleStart.set(cycle, index);
});
const tickNodes = [];
for (const [cycle, start] of cycleStart) {
  if (cycle === 0) continue;
  const tick = document.createElement("div");
  tick.className = "tick";
  tick.style.left = `${(start / frames.length) * 100}%`;
  $("#ticks").appendChild(tick);
  tickNodes.push({ cycle, tick });
}

/* ---------- per-frame panel ---------- */
function updatePanel(index) {
  const frame = frames[index];
  const last = index === frames.length - 1;
  const cycle = frame.cycle ?? 0;
  const method = meta.methods[cycle];

  $("#cycle-now").textContent = cycle;
  $("#phase-name").textContent = method?.phase ?? frame.phase ?? "initialize";
  $("#progress").style.width = `${((index + 1) / frames.length) * 100}%`;
  for (const { cycle: tickCycle, tick } of tickNodes) {
    tick.classList.toggle("done", tickCycle <= cycle);
  }

  if (method) {
    $("#choice-tag").textContent = method.choice ?? method.skill ?? "n/a";
    $("#prob-line").textContent =
      `p = ${num(method.selected_probability, 3)}` +
      (method.selected_probability === null ? "  (logprobs unavailable)" : "");
    $("#latency-line").innerHTML =
      `decision in <b>${Math.round(method.latency_ms ?? 0)} ms</b> · ` +
      `skill <b>${method.skill ?? "n/a"}</b> · ` +
      (method.model_call ? "live model call" : "no model call");
  } else {
    $("#choice-tag").textContent = "—";
    $("#prob-line").textContent = "";
    $("#latency-line").textContent = "waiting for the first decision";
  }

  $("#frame-label").textContent =
    `${String(index + 1).padStart(4, "0")} / ${frames.length}`;
  $("#time-label").textContent = `t = ${frame.time.toFixed(2)} s`;
  $("#verdict").classList.toggle("on", last && meta.success);
  scene.setFrame(frame);
}

/* ---------- automation hook ---------- */
window.__omnijev = {
  frameCount: frames.length,
  meta,
  render(index, camera = {}) {
    document.body.classList.add("instant");
    scene.setCamera(camera);
    updatePanel(Math.max(0, Math.min(frames.length - 1, index)));
  },
};

window.__ready = true;
updatePanel(0);
document.title = `ready:${frames.length}`;
