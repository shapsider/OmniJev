import { RobotScene } from "./robot-scene.js";
import {
  selectionOptions,
  selectionConfig,
  storageLabel,
  storageDescription,
} from "./model-options.js";
import {
  createIcons,
  ScanLine,
  SlidersHorizontal,
  Download,
  X,
  MoveUpRight,
  Layers2,
  Route,
  ChevronDown,
  Box,
  Braces,
  Scan,
  Focus,
  CircleCheck,
  Play,
  Pause,
  StepForward,
  Square,
  RotateCcw,
  GitBranch,
  PlugZap,
} from "lucide";
import "./style.css";

const icon = (name) => `<i data-lucide="${name}"></i>`;
const $ = (s) => document.querySelector(s);
const escape = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const phaseNames = {
  approach: "Move above object",
  descend: "Lower to align",
  grasp: "Close the gripper",
  lift: "Lift object",
  carry: "Move toward target",
  lower: "Lower to place",
  release: "Release the gripper",
  withdraw: "Withdraw upward",
  recover: "Open and retry",
  finish: "Complete",
  incremental: "Incremental XYZ Decision",
};
const stateNames = {
  idle: "Standby",
  running: "Running",
  paused: "Paused",
  uncertain: "Waiting for manual processing",
  completed: "Verification passed",
  stopped: "Stopped",
  error: "Execution error",
  exhausted: "Budget exhausted",
  stalled: "Decision stalled",
};
const stageNames = {
  ready: "Ready",
  deciding: "Deciding",
  previewing: "Action preview",
  executing: "Executing",
  observing: "Reading feedback",
  verified: "Verified",
};
const cameraSelections = {
  none: [],
  external: ["external"],
  wrist: ["wrist"],
  both: ["external", "wrist"],
};
function enabledCameras(snapshot) {
  if (snapshot.camera_views?.length) return snapshot.camera_views;
  if (["vision", "rgbd"].includes(snapshot.observation_mode))
    return snapshot.perception?.camera_views?.length
      ? snapshot.perception.camera_views
      : cameraSelections.both;
  return [];
}
function cameraSelection(views) {
  return views.length === 2 ? "both" : views[0] || "none";
}
function cameraNames(views) {
  return views.map((view) => (view === "wrist" ? "Wrist" : "External")).join("With");
}
let config,
  profileValues = [],
  configuredScene = {},
  configuredContext = {},
  state,
  currentTask = "transfer",
  activeId = null,
  replayMode = false,
  replayTimer = null,
  replayIndex = 0,
  historySignature = "",
  candidateSignature = "",
  resetting = false,
  controlPending = false,
  connectionPending = false,
  selectedCycle = null,
  lastCompletedDecision = null;
$("#app").innerHTML = `
<div class="app-shell">
 <header class="header">
  <div class="brand"><div class="brand-mark">${icon("scan-line")}</div><div><strong>OmniJev</strong><span>Embodied Lab</span></div></div>
  <div class="header-divider"></div><div class="header-context">Local embodied decision · <span id="omni-health">Detecting model...</span></div>
  <nav class="view-switch" aria-label="Work mode"><button class="active" id="workbench-view" type="button">Lab</button><button id="comparison-open" type="button">Compare</button><button id="extensions-open" type="button">Extensions</button></nav>
  <div class="header-right"><span class="engine-label"><span class="dot"></span>MUJOCO / PANDA</span><a class="version" href="/benchmarks">Benchmark ↗</a><button class="icon-button mobile-settings" id="settings-open" title="Experiment parameters" aria-label="Experiment parameters">${icon("sliders-horizontal")}</button><button class="icon-button" id="export" title="Export experiment records" aria-label="Export experiment records">${icon("download")}</button></div>
 </header>
 <div class="body-grid">
 <div class="scrim" id="scrim"></div>
 <aside class="sidebar" id="sidebar">
  <section><div class="section-topline"><h2>Experiment tasks</h2><button class="icon-button close-settings" id="settings-close" aria-label="Close parameters">${icon("x")}</button></div>
   <div class="task-options"><button class="task-option active" data-task="transfer">${icon("move-up-right")}<span>Transfer to tray</span><span class="task-number">01</span></button><button class="task-option" data-task="stack">${icon("layers-2")}<span>Block stacking</span><span class="task-number">02</span></button><button class="task-option" data-task="barrier">${icon("route")}<span>Transfer over barrier</span><span class="task-number">03</span></button></div>
   <p class="task-goal" id="task-goal"></p></section>
  <div class="divider"></div>
  <section><div class="section-topline"><h2>Decision model</h2><button class="icon-button connection-button" id="model-connect" title="Model connection" aria-label="Model connection">${icon("plug-zap")}</button></div><div class="select-wrap"><select id="provider" aria-label="Decision model"></select>${icon("chevron-down")}</div><div class="provider-status"><span class="dot"></span><span id="provider-note">Offline · Deterministic policy</span></div></section>
  <section class="observation-setting"><label class="field-label" for="control-mode">Action decision method</label><div class="select-wrap"><select id="control-mode" aria-describedby="control-help"><option value="skills">Preset skill selection</option><option value="incremental">Incremental XYZ · Closed-loop planning</option></select>${icon("chevron-down")}</div><p id="control-help">Select preset skill, skill internal trajectory executed by program.</p></section>
  <section class="observation-setting"><label class="field-label" for="observation-mode">Observation source</label><div class="select-wrap"><select id="observation-mode" aria-describedby="observation-help"><option value="privileged">Simulation ground truth · Default</option><option value="rgbd">RGB-D Visual · Experiment</option><option value="vision">Direct image · Multimodal model</option></select>${icon("chevron-down")}</div><p id="observation-help">Directly read object positions in simulation.</p></section>
  <section class="observation-setting"><label class="field-label" for="camera-mode">Enable camera</label><div class="select-wrap"><select id="camera-mode" aria-describedby="camera-help"><option value="none">No camera</option><option value="external">Only external camera</option><option value="wrist">Only wrist camera</option><option value="both">Dual camera</option></select>${icon("chevron-down")}</div><p id="camera-help">No camera · The model uses simulated ground truth, Non-visual input.</p></section>
  <div class="divider"></div>
  <section class="input-section" id="input-section"><div class="section-topline"><h2>Input state</h2><span class="eyebrow">m</span></div><p class="input-context" id="input-context">Real-time observation</p><table class="input-table"><thead><tr><th>Position</th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody id="input-positions"></tbody></table><div class="input-contacts" id="input-contacts">Waiting for observation</div></section>
  <details class="advanced-settings" id="advanced-settings"><summary>Execution settings <span>Preview / Speed / Budget</span></summary><section>
   <div class="settings-row"><label for="seed">Random seed</label><input class="number-input" id="seed" type="number" min="0" max="99999" value="0"></div>
   <div class="settings-row"><label for="budget">Action budget</label><input class="number-input" id="budget" type="number" min="1" max="200" value="30"></div>
   <div class="settings-row"><span>Action preview</span><label class="switch"><input id="preview" type="checkbox" checked aria-label="Action preview"><span></span></label></div>
   <div class="settings-row"><label for="threshold">Decision threshold</label><span class="range-label" id="threshold-value">0.55</span></div><input class="range" id="threshold" type="range" min="0" max="1" step="0.05" value="0.55"><div class="range-ticks"><span>0.00</span><span>1.00</span></div>
   <div class="settings-row"><label for="speed">Execution speed</label><span class="range-label" id="speed-value">1.5×</span></div><input class="range" id="speed" type="range" min="0.5" max="4" step="0.5" value="1.5"><div class="range-ticks"><span>0.5×</span><span>4×</span></div>
   <div class="evaluation-settings"><label class="field-label" for="intervention-kind">External evaluation perturbation</label><div class="select-wrap"><select id="intervention-kind" aria-describedby="intervention-help"><option value="none">No perturbation applied</option><option value="object_shift">Move block</option><option value="target_shift">Move target</option></select>${icon("chevron-down")}</div><p id="intervention-help">Inject external displacement after specified action to observe subsequent adjustments. It is not a model action; set at reset or start of experiment.</p><div id="intervention-fields" hidden><div class="settings-row"><label for="intervention-cycle">After step</label><input class="number-input" id="intervention-cycle" type="number" min="1" max="199" step="1" value="5" required></div><div class="settings-row"><label for="intervention-x">X Displacement / m</label><input class="number-input" id="intervention-x" type="number" min="-0.06" max="0.06" step="0.01" value="0.04" required></div><div class="settings-row"><label for="intervention-y">Y Displacement / m</label><input class="number-input" id="intervention-y" type="number" min="-0.06" max="0.06" step="0.01" value="0" required></div></div><p id="intervention-status" role="status" hidden></p><label class="evaluation-checkbox"><input id="shuffle-candidates" type="checkbox">Shuffle candidate order</label><p>Incremental XYZ Reorder action menu by seed to check if selection depends on position.</p></div>
  </section></details><div class="sidebar-bottom"><span>FRANKA PANDA</span><span>7 Degrees of freedom · Two-finger gripper</span></div>
 </aside>
 <main class="workspace">
  <div class="scene-toolbar"><nav class="tabs" aria-label="Experiment view"><button class="tab active" data-tab="scene">${icon("box")} Scene</button><button class="tab" data-tab="vision">${icon("scan-line")} Visual</button><button class="tab" data-tab="data">${icon("braces")} Observation</button><button class="tab decision-tab" id="decision-open">${icon("git-branch")} Decision</button></nav><div class="scene-tools"><button class="icon-button" id="camera-top" title="Top-down view" aria-label="Top-down view">${icon("scan")}</button><button class="icon-button" id="camera-home" title="Reset view" aria-label="Reset view">${icon("focus")}</button></div></div>
  <div class="viewport" id="viewport"><div class="viewport-label"><h1>Franka Panda</h1><p>MANIPULATION / <span id="scene-task">TRANSFER</span></p></div><div class="scene-status" id="scene-status"><span class="dot"></span><span id="status-text">Standby</span></div><div class="scene-axis"><span class="axis-x">X</span><span class="axis-y">Y</span><span class="axis-z">Z</span><span>WORLD / m</span></div><span class="scene-bottom-right" id="scene-time">t = 0.00 s</span><div class="success-stamp" id="success-stamp">${icon("circle-check")} Object stable · Gripper retracted</div><div class="loading" id="loading">Loading robot scene...</div><pre class="raw-state" id="raw-state"></pre></div>
  <div class="telemetry"><div class="metric"><div class="metric-label">End effector X</div><div class="metric-value"><span id="tcp-x">—</span><small>m</small></div></div><div class="metric"><div class="metric-label">End effector Y</div><div class="metric-value"><span id="tcp-y">—</span><small>m</small></div></div><div class="metric"><div class="metric-label">End effector Z</div><div class="metric-value"><span id="tcp-z">—</span><small>m</small></div></div><div class="metric"><div class="metric-label">Object lifted</div><div class="metric-value"><span id="lift">0</span><small>mm</small></div></div></div>
  <div class="timeline"><button class="icon-button" id="replay-play" aria-label="Play trajectory" title="Play trajectory">${icon("play")}</button><div class="timeline-track"><div class="timeline-caption"><span id="timeline-label">EPISODE TIMELINE</span><span id="frame-label">0000 / 0000</span></div><input id="timeline" type="range" min="0" max="0" value="0" aria-label="Trajectory timeline"></div><button class="live-link" id="live">LIVE</button></div>
  <div class="controls"><button class="primary" id="run">${icon("play")}<span id="run-label">Run experiment</span></button><button class="icon-button" id="step" title="Step execution" aria-label="Step execution">${icon("step-forward")}</button><button class="icon-button stop" id="stop" title="Stop experiment" aria-label="Stop experiment">${icon("square")}</button><button class="icon-button" id="reset" title="Reset experiment" aria-label="Reset experiment">${icon("rotate-ccw")}</button><span class="run-budget" id="run-budget">00 / 30 ACTIONS</span></div>
 </main>
 <aside class="inspector" id="inspector" aria-label="Decision and execution log">
  <section class="inspector-section decision-section" id="decision-section" tabindex="-1"><div class="section-topline"><h2 id="decision-heading">Current decision</h2><span class="eyebrow" id="stage">READY</span></div><div class="decision-context"><span id="decision-context" role="status">Real-time · Waiting to start</span><button type="button" class="text-button" id="decision-live" hidden>Return to real-time</button></div><div class="decision-title">${icon("git-branch")}<span id="decision-title">Waiting to start</span></div><div class="decision-meta"><span id="decision-provider">RULE BASELINE</span><span id="latency">— ms</span></div><div id="intent-panel" hidden><div class="decision-meta"><span>01 · Operation phase</span><span id="intent-latency"></span></div><div class="probabilities" id="intent-probabilities"></div><div class="decision-meta"><span>02 · Execute action</span></div></div><div class="probabilities" id="probabilities"><div class="empty">No candidate actions</div></div><p class="decision-note" id="decision-note"></p><div class="history-observations" id="history-observations" hidden><details><summary>Pre-execution · Structured observation</summary><pre id="history-before"></pre></details><details><summary>Post-execution · Structured observation</summary><pre id="history-after"></pre></details><details><summary>Candidate and model response</summary><pre id="history-payload"></pre></details><details id="history-inputs-detail" hidden><summary>Current model input</summary><pre id="history-inputs"></pre></details></div></section>
  <section class="inspector-section"><div class="section-topline"><h2 id="feedback-heading">Physical feedback</h2><span class="eyebrow">FEEDBACK</span></div><div class="sensors"><span class="name">Gripper status</span><span class="sensor-value" id="gripper">OPEN</span><span class="name">Bilateral contact</span><div class="contacts"><span class="contact" id="contact-l">L</span><span class="contact" id="contact-r">R</span></div><span class="name">Target support contact</span><span class="sensor-value" id="support">NO</span><span class="name">Stable duration</span><span class="sensor-value" id="stable">0.00 s</span><span class="name">Action preview</span><span class="sensor-value" id="preview-state">ON</span></div></section>
  <div class="event-heading"><div class="section-topline"><h2>Execution record</h2><span class="eyebrow" id="event-count">0 Step</span></div></div><ol class="events" id="events"><li class="empty">No execution record</li></ol><details class="runtime-log" id="runtime-log"><summary>Run log <span id="log-count">0 Item</span></summary><ol id="log-entries"></ol><p>Show only latest 12 Item, full log can be exported with the experiment.</p></details><div class="inspector-footer"><span id="model-calls">Call 0 Times</span><span id="tokens">Input 0 tokens</span></div>
 </aside></div><footer class="bottom-bar"><div class="bottom-left"><span id="connection">Connecting</span><span>Physical simulation 500 Hz</span><span id="observation-source">Simulation ground truth · Geometry and contact</span></div><span class="bottom-right" id="episode-id">Experiment / —</span></footer>
</div><div class="toast" id="toast" role="status"></div>
<dialog id="connection-dialog" class="connection-dialog" aria-labelledby="connection-title">
 <form id="connection-form">
  <div class="dialog-heading"><div><span class="eyebrow">MODEL CONNECTION</span><h2 id="connection-title">Model connection</h2></div><button type="button" class="icon-button" id="connection-close" aria-label="Close model connection">${icon("x")}</button></div>
  <label class="field-label" for="api-provider">Interface type</label><select id="api-provider"><option value="chat">OpenAI Compatible API</option><option value="claude">Claude Native API</option><option value="jev">TypeSafe Jev</option><option value="local">Jev / Structured decision API</option></select>
  <label class="field-label" for="profile-name">Configuration name <span>Fill in when saving named configuration</span></label><input id="profile-name" maxlength="80" placeholder="For example: OpenAI · GPT6" autocomplete="off">
  <label class="field-label" for="api-url">Base URL / Interface address</label><input id="api-url" type="url" required placeholder="https://your-provider.example/v1" autocomplete="off">
  <label class="field-label" for="api-model">Model ID</label><input id="api-model" required placeholder="Model name provided by platform" autocomplete="off">
  <label class="field-label" for="api-key">API Key <span id="key-state">Not configured</span></label><input id="api-key" type="password" placeholder="API Key" autocomplete="off" spellcheck="false">
  <label class="json-mode" id="json-mode-row"><input id="api-json" type="checkbox" checked>JSON Mode</label>
  <p class="connection-retention" id="provider-help"></p>
  <button type="button" class="text-button api-preset" id="api-official-preset">Fill in OpenAI Official example</button>
  <p class="connection-retention" id="typesafe-links" hidden><a href="https://console.typesafe.ai" target="_blank" rel="noopener noreferrer">Manage TypeSafe Key ↗</a> · <a href="https://typesafe.ai" target="_blank" rel="noopener noreferrer">Request access ↗</a> · <a href="https://docs.typesafe.ai/api" target="_blank" rel="noopener noreferrer">Interface description ↗</a></p>
  <p class="connection-retention" id="connection-storage">Reading local storage state...</p>
  <div id="connection-verification" class="connection-verification"><span class="dot"></span><span id="verification-label">Not yet verified</span></div>
  <div id="connection-result" class="connection-result" role="status"></div>
  <p class="connection-retention" id="profile-help">When saving as a named configuration, please fill in again Key; Cannot copy the default connection key.</p><div class="dialog-actions"><button type="button" class="secondary" id="connection-profile">Save model configuration</button><button type="button" class="secondary" id="connection-test">${icon("plug-zap")} Test call</button><button type="submit" class="primary" id="connection-save">Save connection</button></div>
 </form>
</dialog>`;
const visionPanel = document.createElement("section");
visionPanel.id = "vision-panel";
visionPanel.className = "vision-panel";
visionPanel.hidden = true;
visionPanel.setAttribute("aria-label", "Camera vision observation");
visionPanel.innerHTML = `
  <div class="vision-heading"><div><span class="eyebrow" id="vision-source-heading">PERCEPTION / RGB-D</span><h2>Camera recent observation</h2></div><div class="vision-switch" aria-label="Camera channel"><button type="button" data-vision-channel="rgb" aria-pressed="true" disabled>RGB</button><button type="button" data-vision-channel="depth" aria-pressed="false" disabled>Depth</button></div></div>
  <div class="vision-view-row"><div class="vision-switch" aria-label="Camera view"><button type="button" data-vision-view="external" aria-pressed="true" disabled>External camera</button><button type="button" data-vision-view="wrist" aria-pressed="false" disabled>Wrist camera</button></div><span id="vision-view-help">External camera · Fixed position</span></div>
  <p class="vision-explanation">Known objects are detected by color, and their positions are estimated using depth; gripper state and contacts come from sensors. Action previews still use simulation-based safety filtering.</p>
  <div class="vision-image-wrap"><div id="vision-image-container"></div><p id="vision-empty" role="status">Select “ RGB-D Vision” and reset the experiment to display the actual camera images.</p><span id="vision-image-label" hidden>Recent perception frame</span></div>
  <div class="vision-meta" id="vision-meta" hidden><div><span>Observation source</span><strong id="vision-source-label">RGB-D · Color detection</strong></div><div><span>Perception time</span><strong id="vision-latency">—</strong></div><div><span>Capture moment</span><strong id="vision-time">—</strong></div><div><span id="vision-visibility-label">Visible object</span><strong id="vision-visibility">—</strong></div></div>
  <p class="vision-status" id="vision-status" role="status"></p><div class="vision-download-row"><button type="button" class="text-button" id="vision-retry" hidden>Retry reading</button><button type="button" class="text-button" id="vision-export" disabled>Download observation frame</button><span>All RGB Viewpoint + SHA-256 List · ZIP</span></div><p class="vision-note" id="vision-note">Here displays the most recent perception image; scene page shows current simulation. This mode supports objects with known colors, but lacks general visual recognition capability.</p>`;
$("#viewport").append(visionPanel);
const comparisonContainer = document.createElement("main");
comparisonContainer.id = "comparison-view";
comparisonContainer.hidden = true;
$(".bottom-bar").before(comparisonContainer);
const extensionsContainer = document.createElement("main");
extensionsContainer.id = "extensions-view";
extensionsContainer.hidden = true;
$(".bottom-bar").before(extensionsContainer);
let comparisonView,
  comparisonVisible = false,
  openingComparison = false,
  extensionsView,
  extensionsVisible = false,
  comparisonLoading,
  extensionsLoading;
function moduleFailure(container) {
  container.innerHTML =
    '<div class="view-load-state" role="status"><h1>Page updated or module load failed</h1><p>After refresh, interface can be reloaded. Unsaved configurations need to be filled again; current simulation experiment will not be reset by refresh.</p><button class="secondary module-reload" type="button">Refresh page retry</button></div>';
  container.querySelector(".module-reload").onclick = () =>
    window.location.reload();
}
async function ensureComparison() {
  if (comparisonView) return comparisonView;
  if (!comparisonLoading) {
    comparisonContainer.innerHTML =
      '<div class="view-load-state" role="status">Loading model comparison...</div>';
    comparisonLoading = import("./comparison.js")
      .then(({ createComparison }) =>
        createComparison(comparisonContainer, { api, toast }),
      )
      .then((view) => (comparisonView = view))
      .catch(() => {
        comparisonLoading = null;
        moduleFailure(comparisonContainer);
        throw new Error("Model comparison load failed, can click to refresh page and retry.");
      });
  }
  return comparisonLoading;
}
async function ensureExtensions() {
  if (extensionsView) return extensionsView;
  if (!extensionsLoading) {
    extensionsContainer.innerHTML =
      '<div class="view-load-state" role="status">Loading extension...</div>';
    extensionsLoading = import("./extensions.js")
      .then(({ createExtensions }) =>
        createExtensions(extensionsContainer, {
          api,
          openConnection: (profileId) => openConnection(profileId, true),
          applyPreset: applyExtensionPreset,
          applyModel: applyExtensionModel,
        }),
      )
      .then((view) => (extensionsView = view))
      .catch(() => {
        extensionsLoading = null;
        moduleFailure(extensionsContainer);
        throw new Error("Extension page load failed, can click to refresh page and retry.");
      });
  }
  return extensionsLoading;
}
async function switchView(compare) {
  if (compare && openingComparison) return;
  comparisonVisible = compare;
  extensionsVisible = false;
  extensionsContainer.hidden = true;
  $("#extensions-open").classList.remove("active");
  $(".body-grid").hidden = compare;
  $(".bottom-bar").hidden = compare;
  comparisonContainer.hidden = !compare;
  $(".app-shell").classList.toggle("comparing", compare);
  $(".app-shell").classList.remove("extending");
  $("#workbench-view").classList.toggle("active", !compare);
  $("#comparison-open").classList.toggle("active", compare);
  if (compare && !comparisonView) {
    openingComparison = true;
    try {
      await ensureComparison();
    } catch (error) {
      toast(error.message);
    } finally {
      openingComparison = false;
    }
  }
  comparisonView?.setActive(comparisonVisible);
  if (!compare && state) {
    renderState(state);
    sceneView.requestRender();
  }
}
$("#workbench-view").onclick = () => switchView(false);
$("#comparison-open").onclick = () => switchView(true);
$("#extensions-open").onclick = async () => {
  const target = comparisonVisible ? "comparison" : "workbench";
  comparisonVisible = false;
  extensionsVisible = true;
  comparisonView?.setActive(false);
  $(".body-grid").hidden =
    $(".bottom-bar").hidden =
    comparisonContainer.hidden =
      true;
  extensionsContainer.hidden = false;
  $(".app-shell").classList.remove("comparing");
  $(".app-shell").classList.add("extending");
  $("#workbench-view").classList.remove("active");
  $("#comparison-open").classList.remove("active");
  $("#extensions-open").classList.add("active");
  try {
    await ensureExtensions();
    await extensionsView.refresh(target);
  } catch (error) {
    toast(error.message);
  }
};
async function applyExtensionPreset(preset, target) {
  if (target === "comparison")
    return (await ensureComparison()).applyPreset(preset);
  if (
    ["running", "paused"].includes(state.status) ||
    resetting ||
    controlPending
  )
    throw new Error("Please stop current experiment first, then apply preset.");
  const previous = {
    task: currentTask,
    scene: configuredScene,
    context: configuredContext,
  };
  currentTask = preset.task;
  configuredScene = preset.scene_config;
  configuredContext = preset.user_context;
  if (!(await reset())) {
    currentTask = previous.task;
    configuredScene = previous.scene;
    configuredContext = previous.context;
    throw new Error("Preset not applied, original experiment retained. Please check scene validation prompt.");
  }
}
async function applyExtensionModel(profileId, target) {
  if (target === "comparison")
    return (await ensureComparison()).applyModel(profileId);
  if (
    ["running", "paused"].includes(state.status) ||
    resetting ||
    controlPending
  )
    throw new Error("Please stop current experiment first, then switch model configuration.");
  await refreshProviders();
  $("#provider").value = "profile:" + profileId;
  if (!(await reset())) throw new Error("Model configuration not applied, please check service prompt.");
}
const intentPanel = $("#intent-panel");
intentPanel.lastElementChild.remove();
intentPanel.firstElementChild.firstElementChild.id = "intent-heading";
$("#input-section").append(intentPanel);
const liveInputs = document.createElement("details");
liveInputs.id = "live-inputs-detail";
liveInputs.className = "live-inputs";
liveInputs.hidden = true;
liveInputs.innerHTML =
  '<summary>Current round model input</summary><pre id="live-inputs"></pre>';
$("#history-observations").before(liveInputs);
const planningOutput = document.createElement("div");
planningOutput.id = "planning-output";
planningOutput.className = "planning-output";
planningOutput.hidden = true;
planningOutput.innerHTML =
  '<p class="planning-caption">Current step model description · Used to check decision basis</p><dl><dt>Action intention</dt><dd id="planning-intent"></dd><dt>Visual basis</dt><dd id="planning-evidence"></dd><dt>Selected action</dt><dd id="planning-action"></dd><dt>Input image</dt><dd id="planning-image"></dd></dl>';
$("#probabilities").before(planningOutput);
const historyList = document.createElement("details");
historyList.className = "history-list";
historyList.id = "history-list";
historyList.innerHTML =
  '<summary>Execution record <span id="history-count"></span></summary>';
$(".event-heading").before(historyList);
historyList.append($(".event-heading"), $("#events"));
const feedbackDetails = document.createElement("details");
feedbackDetails.className = "feedback-details";
feedbackDetails.innerHTML = "<summary>Physical feedback</summary>";
const feedbackSection = $("#feedback-heading").closest("section");
feedbackSection.before(feedbackDetails);
feedbackDetails.append(feedbackSection);
const narrowLayout = window.matchMedia("(max-width: 820px)");
function placeInputPanel() {
  if (narrowLayout.matches) $("#inspector").prepend($("#input-section"));
  else $("#sidebar").insertBefore($("#input-section"), $("#advanced-settings"));
}
narrowLayout.addEventListener("change", placeInputPanel);
placeInputPanel();
const icons = {
  ScanLine,
  SlidersHorizontal,
  Download,
  X,
  MoveUpRight,
  Layers2,
  Route,
  ChevronDown,
  Box,
  Braces,
  Scan,
  Focus,
  CircleCheck,
  Play,
  Pause,
  StepForward,
  Square,
  RotateCcw,
  GitBranch,
  PlugZap,
};
createIcons({ icons });

let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("visible"), 6000);
}
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(
      typeof error.detail === "string" ? error.detail : "Parameter or service abnormal",
    );
  }
  return response.json();
}
const sceneView = new RobotScene($("#viewport"), { onError: toast });
$(".viewport-label p").firstChild.textContent = "Simulation view / ";
let visionChannel = "rgb",
  visionView = "external",
  cameraExportPending = false,
  visionRequestKey = "",
  visionRequest = 0,
  visionMetadata = null,
  visionImageKey = "";

function clearVisionImage(message) {
  visionImageKey = "";
  $("#vision-image-container").replaceChildren();
  $("#vision-image-label").hidden = true;
  $("#vision-empty").hidden = false;
  $("#vision-empty").textContent = message;
}

function renderVisionImage() {
  if (!visionMetadata?.capture_id || !state?.id) return;
  const key = `${state.id}:${visionMetadata.capture_id}:${visionView}:${visionChannel}`;
  if (key === visionImageKey) return;
  clearVisionImage("Reading collected image...");
  visionImageKey = key;
  const image = new Image();
  image.id = "vision-image";
  image.alt =
    `${visionView === "wrist" ? "Wrist" : "External"} · ` +
    (visionChannel === "rgb"
      ? "MuJoCo Actual camera RGB screen"
      : "MuJoCo Camera actual depth image");
  image.hidden = true;
  image.onload = () => {
    if (visionImageKey !== key) return;
    image.hidden = false;
    $("#vision-empty").hidden = true;
    $("#vision-image-label").hidden = false;
    $("#vision-image-label").textContent =
      `${visionChannel === "rgb" ? "RGB" : "Depth"} · Recent perception frame ${visionView === "wrist" ? " · Wrist camera" : ""}`;
  };
  image.onerror = () => {
    if (visionImageKey !== key) return;
    $("#vision-empty").textContent = "This perception frame has been updated or read failed, please retry.";
    $("#vision-retry").hidden = false;
  };
  const query = new URLSearchParams({
    episode_id: state.id,
    capture_id: visionMetadata.capture_id,
    view: visionView,
  });
  image.src = `/api/perception/${visionChannel}.png?${query}`;
  $("#vision-image-container").replaceChildren(image);
}

function renderVisionMetadata(metadata) {
  const direct = state.observation_mode === "vision";
  const previewOnly = state.observation_mode === "privileged";
  $("#vision-meta").hidden = false;
  for (const button of document.querySelectorAll("[data-vision-channel]"))
    button.disabled = direct && button.dataset.visionChannel === "depth";
  const views = metadata.camera_views || enabledCameras(state);
  if (!views.includes(visionView)) visionView = views[0] || "external";
  for (const button of document.querySelectorAll("[data-vision-view]")) {
    button.hidden = !views.includes(button.dataset.visionView);
    button.disabled = !views.includes(button.dataset.visionView);
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.visionView === visionView),
    );
  }
  $("#vision-view-help").textContent =
    visionView === "wrist" ? "Wrist camera · Moves with the robotic arm" : "External camera · Fixed position";
  if (direct && visionChannel !== "rgb") {
    visionChannel = "rgb";
    for (const button of document.querySelectorAll("[data-vision-channel]"))
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.visionChannel === "rgb"),
      );
  }
  $("#vision-source-label").textContent = direct
    ? "RGB Image → Multimodal model"
    : previewOnly
      ? "RGB Camera preview · Do not send model"
      : "RGB-D · Color detection";
  $("#vision-visibility-label").textContent = direct
    ? "Spatial relationship"
    : previewOnly
      ? "Use"
      : "Visible object";
  $("#vision-latency").textContent = Number.isFinite(metadata.latency_ms)
    ? `${metadata.latency_ms.toFixed(1)} ms`
    : "—";
  $("#vision-time").textContent = Number.isFinite(metadata.sim_time)
    ? `t = ${metadata.sim_time.toFixed(2)} s`
    : "—";
  $("#vision-time").title = metadata.captured_at || "";
  const objects = Array.isArray(metadata.objects)
    ? metadata.objects
    : Object.entries(metadata.objects || {}).map(([id, value]) => ({
        id,
        ...value,
      }));
  const visible = objects.filter((object) => object.visible).length;
  $("#vision-visibility").textContent = direct
    ? "Determine from image"
    : previewOnly
      ? "Preview only"
      : objects.length
        ? `${visible} / ${objects.length}`
        : "—";
  const missing = objects
    .filter((object) => !object.visible)
    .map((object) => object.label || object.id);
  $("#vision-status").textContent =
    (previewOnly
      ? "Camera for viewing only; model uses simulated ground truth, Non-visual input."
      : metadata.message) ||
    (direct
      ? "The model directly receives RGB Image; no object or target coordinates provided."
      : missing.length
        ? `Obstructed or not detected: ${missing.join(", ")}`
        : objects.length
          ? "Currently known objects are visible"
          : "Waiting for detection results");
  $("#vision-status").classList.toggle(
    "has-alert",
    missing.length > 0 ||
      ["partial", "unavailable", "error"].includes(metadata.status),
  );
  renderVisionImage();
}

function renderVision(s) {
  const rgbd = s.observation_mode === "rgbd";
  const direct = s.observation_mode === "vision";
  const cameras = enabledCameras(s);
  const camera = cameras.length > 0;
  const cameraLabel = cameraNames(cameras);
  $("#vision-export").disabled =
    cameraExportPending || !s.id || !s.perception?.capture_id;
  $("#camera-help").textContent = !camera
    ? "No camera · The model uses simulated ground truth, Non-visual input."
    : direct
      ? `Model receives ${cameraLabel} Camera image.`
      : rgbd
        ? `${cameraLabel} Camera used for RGB-D Position estimation, model receives detection coordinates.`
        : `${cameraLabel} Camera for viewing only; model uses simulated ground truth, Non-visual input.`;
  for (const button of document.querySelectorAll("[data-vision-view]"))
    button.hidden = !cameras.includes(button.dataset.visionView);
  $("#control-help").textContent =
    s.control_mode === "incremental"
      ? `${s.provider === "baseline" ? "Rule baseline" : "Model"} Select each step XYZ Displacement and gripper action, re-observe after execution. Planning must be verified by experiment.`
      : "Select preset skill, skill internal trajectory executed by program.";
  $("#observation-help").textContent = direct
    ? `Send ${cameraLabel} RGB images and robot proprioceptive state, without object/Target coordinates. Incremental XYZ and OmniJev or support image Chat / Claude model.`
    : rgbd
      ? "Send object coordinates obtained from color detection and depth estimation; the model does not receive images directly."
      : "Model reads object positions in simulation, does not receive images (non-visual input).";
  $("#observation-source").textContent = direct
    ? `Model input · ${cameraLabel} RGB + Own state`
    : rgbd
      ? "RGB-D Perception + Contact sensor"
      : "Non-visual input · Simulation ground truth and contact";
  if (visionPanel.hidden || comparisonVisible || extensionsVisible) return;
  $("#vision-source-heading").textContent = direct
    ? "MODEL INPUT / RGB"
    : rgbd
      ? "PERCEPTION / RGB-D"
      : "CAMERA PREVIEW";
  $(".vision-explanation").textContent = direct
    ? `${cameraLabel} RGB Images are sent directly to the multimodal model. The model combines end-effector position, gripper state, and contact feedback to infer spatial relationships and select the next action; object and target coordinates are not provided.`
    : rgbd
      ? "Known objects are detected by color and located using depth estimates; the model receives detected coordinates, while gripper state and contacts come from sensors. Action previews still use simulation-based safety filtering."
      : camera
        ? "Camera is for viewing simulation scenes only; this round the model reads simulation ground truth, does not send images."
        : "Camera not enabled; this round the model reads simulation ground truth, belongs to non-visual experiment.";
  $("#vision-note").textContent =
    `${replayMode ? "Replaying trajectory; here is still the most recent perception image." : "Cameras capture at decision and action boundaries. Images pause while waiting for the model response; this is not real-time video."}${rgbd ? "This mode supports known-color objects, but does not yet have general visual recognition capability." : `${cameras.includes("external") ? "External camera position is fixed." : ""}${cameras.includes("wrist") ? "Wrist camera moves with robotic arm." : ""}${direct ? "Each step image and brief visual basis can be exported with the experiment." : "Image is for viewing only, not sent to model."}`}`;
  const capture = s.perception?.capture_id;
  if (!camera || !capture) {
    visionRequest++;
    visionRequestKey = "";
    visionMetadata = null;
    for (const button of document.querySelectorAll("[data-vision-channel]"))
      button.disabled = true;
    for (const button of document.querySelectorAll("[data-vision-view]"))
      button.disabled = true;
    $("#vision-meta").hidden = true;
    $("#vision-status").textContent = camera
      ? s.perception?.message || "Waiting for perception collection"
      : "";
    $("#vision-retry").hidden = true;
    clearVisionImage(
      camera
        ? "No camera view yet. Will display after perception is ready."
        : "Select “ RGB-D Visual or Direct Image will enable camera; preview can also be enabled separately in Enable Camera.",
    );
    return;
  }
  const key = `${s.id}:${capture}`;
  if (key === visionRequestKey) return;
  visionRequestKey = key;
  visionMetadata = null;
  $("#vision-meta").hidden = true;
  $("#vision-retry").hidden = true;
  $("#vision-status").textContent = "";
  clearVisionImage("Reading collected image...");
  const request = ++visionRequest;
  const query = new URLSearchParams({ episode_id: s.id, capture_id: capture });
  api(`/api/perception?${query}`)
    .then((metadata) => {
      if (request !== visionRequest || state?.id !== s.id) return;
      visionMetadata = metadata;
      renderVisionMetadata(metadata);
    })
    .catch((error) => {
      if (request !== visionRequest) return;
      clearVisionImage("Camera view temporarily unavailable");
      $("#vision-status").textContent = error.message;
      $("#vision-retry").hidden = false;
    });
}

for (const button of document.querySelectorAll("[data-vision-channel]"))
  button.onclick = () => {
    visionChannel = button.dataset.visionChannel;
    for (const other of document.querySelectorAll("[data-vision-channel]"))
      other.setAttribute("aria-pressed", String(other === button));
    renderVisionImage();
  };
for (const button of document.querySelectorAll("[data-vision-view]"))
  button.onclick = () => {
    visionView = button.dataset.visionView;
    if (visionMetadata) renderVisionMetadata(visionMetadata);
  };
$("#vision-retry").onclick = () => {
  visionRequestKey = "";
  if (state) renderVision(state);
};
$("#vision-export").onclick = async () => {
  if (cameraExportPending || !state?.id || !state.perception?.capture_id)
    return;
  const episodeId = state.id;
  cameraExportPending = true;
  $("#vision-export").disabled = true;
  $("#vision-export").textContent = "Reading observation frame...";
  try {
    const response = await fetch(
      `/api/export/cameras.zip?${new URLSearchParams({ episode_id: episodeId })}`,
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        typeof error.detail === "string"
          ? error.detail
          : "Observation frame download failed, please retry.",
      );
    }
    const file = await response.blob();
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = `camera-observations-${episodeId}.zip`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    toast(error.message);
  } finally {
    cameraExportPending = false;
    $("#vision-export").textContent = "Download observation frame";
    $("#vision-export").disabled = !state?.id || !state.perception?.capture_id;
  }
};
let lastFrame;
function renderFrame(frame) {
  if (!frame) return;
  sceneView.render(frame);
  lastFrame = frame;
  const o = frame.observation || {};
  ["x", "y", "z"].forEach(
    (k, i) =>
      ($(`#tcp-${k}`).textContent = Number.isFinite(o.tcp?.[i])
        ? o.tcp[i].toFixed(3)
        : "—"),
  );
  $("#lift").textContent = Number.isFinite(o.max_lift_m)
    ? (o.max_lift_m * 1000).toFixed(0)
    : "—";
  $("#gripper").textContent = o.gripper === "closed" ? "CLOSED" : "OPEN";
  $("#contact-l").classList.toggle(
    "on",
    o.finger_contacts?.includes("left") || false,
  );
  $("#contact-r").classList.toggle(
    "on",
    o.finger_contacts?.includes("right") || false,
  );
  $("#support").textContent =
    o.support_contact === undefined ? "—" : o.support_contact ? "YES" : "NO";
  $("#support").classList.toggle("on", o.support_contact);
  $("#stable").textContent = Number.isFinite(o.stable_seconds)
    ? o.stable_seconds.toFixed(2) + " s"
    : "—";
  $("#scene-time").textContent = Number.isFinite(o.sim_seconds)
    ? "t = " + o.sim_seconds.toFixed(2) + " s"
    : "—";
  $("#raw-state").textContent = JSON.stringify(o, null, 2);
}
async function loadScene() {
  $("#loading").classList.remove("hidden");
  const data = await api("/api/scene");
  sceneView.load(data);
  lastFrame = null;
  $("#scene-task").textContent = data.task.toUpperCase();
  $("#loading").classList.add("hidden");
}

function decisionSnapshot(s) {
  return {
    cycle: s.cycles,
    phase: s.phase,
    intent: s.last_intent,
    decision: s.last_decision,
    candidates: s.candidates || [],
    decision_inputs: s.last_decision_inputs,
  };
}

function selectedActionSummary(action, before) {
  if (!action) return "Waiting for selection";
  const delta =
    action.delta_xyz ||
    (action.target?.length === 3 && before?.tcp?.length === 3
      ? action.target.map((value, index) => value - before.tcp[index])
      : null);
  const motion = delta?.every(Number.isFinite)
    ? `ΔXYZ (${delta.map((value) => `${value >= 0 ? "+" : ""}${value.toFixed(3)}`).join(", ")}) m`
    : "ΔXYZ Not recorded";
  return `${motion} · Gripper ${{ open: "Open", close: "Close", closed: "Close" }[action.gripper] || "Keep"}`;
}

function renderDecision(s) {
  const history = s.history.find((h) => h.cycle === selectedCycle);
  if (selectedCycle !== null && !history) selectedCycle = null;
  if (s.last_decision && s.candidates?.length) {
    lastCompletedDecision = decisionSnapshot(s);
  } else if (!lastCompletedDecision && s.history.length) {
    lastCompletedDecision = s.history.at(-1);
  }
  const previous = !s.last_decision && !!lastCompletedDecision;
  const shown =
    history || (previous ? lastCompletedDecision : decisionSnapshot(s));
  const intent = shown.intent;
  const decision = shown.decision;
  const candidates = shown.candidates || (shown.action ? [shown.action] : []);
  const incremental =
    shown.phase === "incremental" || s.control_mode === "incremental";
  const direct = s.observation_mode === "vision";
  const loading =
    s.provider === "minicpm" && s.model_runtime?.status === "loading";
  const pending =
    s.status === "running" && ["deciding", "previewing"].includes(s.stage);
  const observation =
    history?.before ||
    (replayMode ? lastFrame?.observation : s.frame?.observation);
  $("#input-context").textContent = history
    ? `History step ${history.cycle} Step · Pre-execution observation`
    : replayMode
      ? "Playback observation"
      : direct
        ? `Model input · ${cameraNames(enabledCameras(s))} RGB + Own state`
        : s.observation_mode === "rgbd"
          ? "Recently RGB-D Position estimation · Contact sensor"
          : "Simulation ground truth · Position and contact";
  $("#input-positions").innerHTML = [
    ["End effector", "tcp"],
    ["Block", "object"],
    ["Target", "destination"],
  ]
    .map(
      ([label, key]) =>
        `<tr><th>${label}</th>${direct && key !== "tcp" ? '<td colspan="3" class="image-position">Determine from image</td>' : [0, 1, 2].map((index) => `<td>${Number.isFinite(observation?.[key]?.[index]) ? observation[key][index].toFixed(3) : "—"}</td>`).join("")}</tr>`,
    )
    .join("");
  $("#input-contacts").textContent = observation
    ? `Gripper ${observation.gripper === "closed" ? "Close" : "Open"} · ${observation.held ? "Two-sided grip" : observation.finger_contacts?.length ? "Single-sided contact" : "Not contacted object"}`
    : "Waiting for observation";
  $("#intent-heading").textContent = history
    ? "Stage selection · History"
    : previous
      ? "Stage selection · Previous"
      : "Stage selection";
  $("#decision-heading").textContent = history
    ? `History output · Step ${history.cycle} Step`
    : "Action output";
  $("#decision-live").hidden = !history;
  $("#decision-section").classList.toggle("viewing-history", !!history);
  $("#stage").textContent = history
    ? "History"
    : loading
      ? "Loading"
      : stageNames[s.stage] || s.stage;
  $("#decision-context").textContent = history
    ? `History · ${history.after.sim_seconds.toFixed(2)} s`
    : previous
      ? `Previous decision · ${pending ? "Computing new decision" : stateNames[s.status] || s.status}`
      : loading
        ? "Loading MiniCPM5-2B Weight"
        : pending
          ? "Real-time · Computing new decision"
          : `Real-time · ${stateNames[s.status] || s.status}`;
  $("#decision-title").textContent =
    candidates.find((candidate) => candidate.id === decision?.choice)?.label ||
    (loading ? "Loading model for the first time" : "Waiting to start");
  $("#planning-output").hidden = !incremental;
  $("#planning-intent").textContent =
    decision?.intent || (decision ? "Model did not provide action intent" : "Waiting for model decision");
  $("#planning-evidence").textContent =
    decision?.visual_evidence ||
    (direct ? "Model did not provide visual basis" : "Current input is structured observation");
  const chosenAction =
    candidates.find((candidate) => candidate.id === decision?.choice) ||
    shown.action;
  $("#planning-action").textContent = selectedActionSummary(
    chosenAction,
    history?.before || shown.decision_inputs?.action?.state?.observation,
  );
  const imageHash = decision?.image_sha256;
  $("#planning-image").textContent = imageHash
    ? `SHA-256 ${typeof imageHash === "string" ? imageHash : JSON.stringify(imageHash)}`
    : direct
      ? "Waiting for image recording of this step"
      : "Image not sent";
  $("#decision-provider").textContent =
    decision?.model ||
    intent?.model ||
    {
      baseline: "Rule baseline",
      chat: "CHAT / JSON",
      claude: "CLAUDE / TOOL",
    }[s.provider] ||
    s.provider.toUpperCase();
  $("#latency").textContent = decision?.model_call
    ? Number(decision.latency_ms).toFixed(0) + " ms"
    : decision
      ? "No model call"
      : "— ms";
  $("#feedback-heading").textContent = replayMode
    ? "Replay physical feedback"
    : "Real-time physical feedback";
  const failure = ["error", "uncertain", "exhausted", "stalled"].includes(
    s.status,
  );
  $("#decision-note").classList.toggle("failure", !history && failure);
  $("#decision-note").textContent = history
    ? `Viewing this step record, 3D scene remains ${replayMode ? "Trajectory replay" : "Real-time display"}.${history.candidates ? "" : "Older records did not save all candidates; only the selected action is shown."}`
    : failure && s.message
      ? s.message
      : previous
        ? "Keep last complete selection; automatically update after new result returns"
        : decision
          ? incremental
            ? `${s.provider === "baseline" ? "Rule baseline" : "Model"} Incrementally select displacement and gripper actions; physical success does not equal verified planning capability`
            : "Candidate generated by task controller; probability does not represent task success rate"
          : "View action selection after running experiment";
  $("#history-observations").hidden = !history;
  $("#live-inputs-detail").hidden =
    !!history ||
    !(s.last_decision_inputs?.phase || s.last_decision_inputs?.action);
  $("#live-inputs").textContent = s.last_decision_inputs
    ? JSON.stringify(s.last_decision_inputs, null, 2)
    : "";
  $("#history-inputs-detail").hidden = !history?.decision_inputs;
  const signature = JSON.stringify([
    selectedCycle,
    candidates,
    decision,
    intent,
    history?.decision_inputs,
  ]);
  if (signature === candidateSignature) return;
  candidateSignature = signature;
  $("#intent-panel").hidden = incremental || !intent;
  $("#intent-latency").textContent = intent?.model_call
    ? Number(intent.latency_ms).toFixed(0) + " ms"
    : intent?.reason === "only_eligible_action"
      ? "Single feasible stage · No model call"
      : "Rule selection";
  $("#intent-probabilities").innerHTML = intent
    ? (Object.entries(intent.probabilities || {}).length
        ? Object.entries(intent.probabilities)
        : [[intent.choice, null]]
      )
        .map(
          ([choice, probability]) =>
            `<div class="prob-row ${choice === intent.choice ? "selected" : ""}"><div class="prob-top"><span>${escape(phaseNames[choice] || choice)}</span><span>${probability === null ? "Selected" : (probability * 100).toFixed(1) + "%"}</span></div>${probability === null ? "" : `<div class="bar"><div class="bar-fill" style="width:${probability * 100}%"></div></div>`}</div>`,
        )
        .join("")
    : "";
  const probabilities = decision?.probabilities || {};
  $("#probabilities").innerHTML = candidates.length
    ? candidates
        .map((candidate) => {
          const selected = decision?.choice === candidate.id;
          const rejected = candidate.admitted === false;
          const probability = probabilities[candidate.id];
          const label = rejected
            ? "Intercepted"
            : probability !== undefined
              ? (probability * 100).toFixed(1) + "%"
              : selected
                ? "Selected"
                : decision
                  ? "Not selected"
                  : "Waiting for decision";
          const width =
            probability !== undefined ? probability * 100 : selected ? 100 : 0;
          return `<div class="prob-row ${selected ? "selected" : ""} ${rejected ? "rejected" : ""}" title="${escape(candidate.rejection || "")}"><div class="prob-top"><span>${escape(candidate.label || candidate.id)}</span><span>${label}</span></div><div class="bar"><div class="bar-fill" style="width:${width}%"></div></div></div>`;
        })
        .join("")
    : `<div class="empty">${pending ? "Waiting for model to return candidate selection..." : "No candidate actions"}</div>`;
  if (history) {
    $("#history-before").textContent = JSON.stringify(history.before, null, 2);
    $("#history-after").textContent = JSON.stringify(history.after, null, 2);
    $("#history-payload").textContent = JSON.stringify(
      {
        cycle: history.cycle,
        phase: history.phase,
        intent,
        decision,
        candidates,
      },
      null,
      2,
    );
    $("#history-inputs").textContent = history.decision_inputs
      ? JSON.stringify(history.decision_inputs, null, 2)
      : "";
  }
}

function updateControlAvailability() {
  if (!state) return;
  const pending = controlPending || resetting;
  $("#run").disabled =
    pending ||
    ["completed", "stopped", "error", "exhausted", "stalled"].includes(
      state.status,
    );
  $("#step").disabled =
    pending ||
    [
      "running",
      "completed",
      "stopped",
      "error",
      "exhausted",
      "stalled",
    ].includes(state.status);
  $("#stop").disabled =
    pending || ["idle", "completed", "stopped"].includes(state.status);
  $("#reset").disabled = pending;
  $(".controls").setAttribute("aria-busy", String(pending));
  const locked = pending || ["running", "paused"].includes(state.status);
  for (const el of document.querySelectorAll(
    "#model-connect,#provider,#control-mode,#observation-mode,#camera-mode,.task-option,#seed,#budget,#preview,#threshold,#speed,#intervention-kind,#shuffle-candidates",
  ))
    el.disabled = locked;
  const interventionEnabled = $("#intervention-kind").value !== "none";
  $("#intervention-fields").hidden = !interventionEnabled;
  for (const input of $("#intervention-fields").querySelectorAll("input"))
    input.disabled = locked || !interventionEnabled;
  $("#threshold").disabled =
    locked || ["baseline", "chat", "claude", "omni_direct", "omni_reasoning"].includes(state.provider);
}

let logSignature = "";
function renderLogs(s) {
  const events = [...(s.events || [])];
  for (const intervention of s.interventions || []) {
    if (
      !events.some(
        (event) =>
          event.event === "external_intervention" &&
          event.cycle === intervention.after_cycle,
      )
    )
      events.push({
        event: "external_intervention",
        level: "warning",
        time: intervention.sim_time,
        cycle: intervention.after_cycle,
        message: `External evaluation disturbance: ${intervention.kind === "object_shift" ? "Move block" : "Move target"}, Not a model action.`,
      });
  }
  const signature = JSON.stringify(events.slice(-12));
  if (signature === logSignature) return;
  logSignature = signature;
  const errors = events.filter((event) =>
    ["error", "warning"].includes(event.level),
  ).length;
  $("#log-count").textContent =
    `${events.length} Item ${errors ? ` · ${errors} Reminder` : ""}`;
  $("#runtime-log").classList.toggle("has-alert", errors > 0);
  $("#log-entries").innerHTML =
    events
      .slice(-12)
      .reverse()
      .map((event) => {
        const level = ["error", "warning"].includes(event.level)
          ? event.level
          : "info";
        const time =
          typeof event.time === "number"
            ? `${event.time.toFixed(1)} s`
            : String(event.time || "")
                .replace(/^.*T/, "")
                .slice(0, 8);
        return `<li class="log-item ${level}"><span>${escape(time)} · Step ${escape(event.cycle ?? 0)} Step</span><p>${escape(event.message || event.event || "")}</p></li>`;
      })
      .join("") || '<li class="empty">No running logs</li>';
}

function renderState(s) {
  state = s;
  if (activeId !== s.id) {
    activeId = s.id;
    historySignature = "";
    candidateSignature = "";
    selectedCycle = null;
    lastCompletedDecision = null;
    replayMode = false;
    replayRequest++;
    clearInterval(replayTimer);
    replayTimer = null;
    currentTask = s.task;
    configuredScene = s.scene_config || {};
    configuredContext = s.user_context || {};
    for (const button of document.querySelectorAll("[data-task]")) {
      button.classList.toggle("active", button.dataset.task === s.task);
    }
    $("#task-goal").textContent = config.tasks[s.task].goal;
    $("#provider").value = s.profile_id
      ? "profile:" + s.profile_id
      : s.provider;
    $("#observation-mode").value = s.observation_mode || "privileged";
    $("#control-mode").value = s.control_mode || "skills";
    $("#camera-mode").value = cameraSelection(enabledCameras(s));
    $("#intervention-kind").value = s.intervention?.kind || "none";
    $("#intervention-cycle").value = s.intervention?.after_cycle ?? 5;
    $("#intervention-x").value = s.intervention?.delta_xy?.[0] ?? 0.04;
    $("#intervention-y").value = s.intervention?.delta_xy?.[1] ?? 0;
    $("#shuffle-candidates").checked = s.shuffle_candidates === true;
    $("#seed").value = s.seed;
    $("#budget").value = s.max_cycles;
    $("#preview").checked = s.preview;
    $("#threshold").value = s.threshold;
    $("#threshold-value").textContent = s.threshold.toFixed(2);
    $("#speed").value = s.speed;
    $("#speed-value").textContent = s.speed.toFixed(1) + "×";
    $("#timeline-label").textContent = "EPISODE TIMELINE";
    $("#provider-note").textContent =
      providerNote(s.provider);
    $("#episode-id").textContent = "EPISODE / " + s.id.toUpperCase();
  }
  if (!replayMode) renderFrame(s.frame);
  $("#status-text").textContent = replayMode
    ? "Trajectory replay"
    : stateNames[s.status];
  $("#scene-status").classList.toggle(
    "error",
    ["error", "exhausted", "uncertain", "stalled"].includes(s.status),
  );
  $("#success-stamp").classList.toggle(
    "visible",
    s.status === "completed" && !replayMode,
  );
  if (s.provider === "minicpm" && s.model_runtime) {
    const runtime = s.model_runtime;
    const device = (runtime.device || "AUTO").toUpperCase();
    $("#provider-note").textContent = {
      not_loaded: "Local · First decision loads weights",
      loading: `Loading weights · ${device}`,
      ready: `Locally ready · ${device} · Candidate probability`,
      error: `Load failed · ${runtime.error || "Check the service logs"}`,
    }[runtime.status];
  }
  renderDecision(s);
  renderVision(s);
  renderLogs(s);
  $("#intervention-status").hidden = !s.interventions?.length;
  $("#intervention-status").textContent = s.interventions?.length
    ? `Injected ${s.interventions.length} External evaluation disturbance; see run log.`
    : "";
  $("#run-budget").textContent =
    String(s.cycles).padStart(2, "0") + " / " + s.max_cycles + " Step";
  $("#run-label").textContent =
    s.status === "running"
      ? "Pause experiment"
      : ["paused", "uncertain"].includes(s.status)
        ? "Continue experiment"
        : "Run experiment";
  const runIcon = s.status === "running" ? "pause" : "play";
  if ($("#run").dataset.icon !== runIcon) {
    $("#run").dataset.icon = runIcon;
    $("#run svg").outerHTML = icon(runIcon);
    createIcons({ icons });
  }
  updateControlAvailability();
  $("#preview-state").textContent = s.preview ? "ON" : "OFF";
  $("#model-calls").textContent = "Call " + s.model_calls + " Times";
  $("#tokens").textContent =
    "Input " + s.input_tokens.toLocaleString() + " tokens";
  $("#timeline").max = Math.max(0, s.frame_count - 1);
  if (!replayMode) {
    $("#timeline").value = s.frame_count - 1;
    $("#frame-label").textContent =
      String(s.frame_count).padStart(4, "0") +
      " / " +
      String(s.frame_count).padStart(4, "0");
  }
  $("#replay-play").disabled = s.frame_count < 2 || s.status === "running";
  const hsig = s.id + "-" + s.history.length + "-" + selectedCycle;
  if (hsig !== historySignature) {
    historySignature = hsig;
    $("#event-count").textContent = s.history.length + " Step";
    $("#history-count").textContent = s.history.length + " Step";
    $("#events").innerHTML = s.history.length
      ? s.history
          .map(
            (h) =>
              `<li class="event ${h.cycle === selectedCycle ? "active" : ""}"><button type="button" class="event-button" data-cycle="${h.cycle}" aria-pressed="${h.cycle === selectedCycle}" aria-label="View the ${h.cycle} step decision: ${escape(h.label)}"><span class="event-line"><span>${escape(h.label)}</span><small>${h.after.sim_seconds.toFixed(1)} s</small></span><span class="event-detail">Step ${h.cycle} Step · ${h.after.held ? "Bilateral contact" : h.after.support_contact ? "Target support" : "Position updated"}${h.rejected_count ? " · Intercept " + h.rejected_count + " candidate" : ""}</span></button></li>`,
          )
          .join("")
      : '<li class="empty">No execution record</li>';
    if (selectedCycle === null)
      $("#events").scrollTop = $("#events").scrollHeight;
  }
  $("#threshold-value").textContent = ["baseline", "chat", "claude", "omni_direct", "omni_reasoning"].includes(
    s.provider,
  )
    ? "N/A"
    : Number($("#threshold").value).toFixed(2);
  $("#threshold").title = ["omnijev", "omni_adaptive"].includes(s.provider) ? "Candidate token Scores are not calibrated; no additional score threshold is set by default" : "The generative interface does not provide calibrated success probabilities";
  renderProviderStatus();
  if (s.message && s.message !== renderState.lastMessage) {
    toast(s.message);
    renderState.lastMessage = s.message;
  }
  $("#connection").textContent = "● Connected";
}

function configuredIntervention() {
  const kind = $("#intervention-kind").value;
  if (kind === "none") return null;
  const after_cycle = Number($("#intervention-cycle").value);
  const delta_xy = [$("#intervention-x"), $("#intervention-y")].map((input) =>
    input.value.trim() === "" ? NaN : Number(input.value),
  );
  if (!Number.isInteger(after_cycle) || after_cycle < 1 || after_cycle > 199)
    throw new Error("External evaluation disturbance moment must be at the 1–199 After step.");
  if (
    delta_xy.some(
      (value) => !Number.isFinite(value) || Math.abs(value) > 0.06,
    ) ||
    delta_xy.every((value) => value === 0)
  )
    throw new Error(
      "External evaluation disturbance X / Y Displacement must be in ±0.06 meters, and they cannot both be zero.",
    );
  return { kind, after_cycle, delta_xy };
}
function setup() {
  return {
    expected_episode_id: state?.id,
    task: currentTask,
    scene_config: configuredScene,
    user_context: configuredContext,
    observation_mode: $("#observation-mode").value,
    control_mode: $("#control-mode").value,
    camera_views: [...cameraSelections[$("#camera-mode").value]],
    intervention: configuredIntervention(),
    shuffle_candidates: $("#shuffle-candidates").checked,
    seed: Number($("#seed").value),
    ...selectionConfig($("#provider").value, profileValues),
    preview: $("#preview").checked,
    threshold: Number($("#threshold").value),
    max_cycles: Number($("#budget").value),
    speed: Number($("#speed").value),
  };
}
async function reset(fromControl = false) {
  if (resetting || (controlPending && !fromControl)) return false;
  resetting = true;
  updateControlAvailability();
  clearInterval(replayTimer);
  replayTimer = null;
  replayRequest++;
  replayMode = false;
  try {
    if ($("#observation-mode").value === "vision") {
      if ($("#control-mode").value !== "incremental")
        throw new Error(
          "Direct image input requires “Incremental XYZ”Action decision. Please first switch the action decision method.",
        );
      if (
        !["chat", "claude", "omnijev", "omni_direct", "omni_reasoning", "omni_adaptive"].includes(
          selectionConfig($("#provider").value, profileValues).provider,
        )
      )
        throw new Error(
          "Direct image required OmniJev Local policy or support image Chat / Claude model.",
        );
    }
    const s = await api("/api/reset", setup());
    await loadScene();
    renderState(s);
    return true;
  } catch (e) {
    toast(e.message);
    return false;
  } finally {
    resetting = false;
    updateControlAvailability();
  }
}
async function control(action) {
  if (controlPending || resetting) return;
  controlPending = true;
  updateControlAvailability();
  try {
    replayRequest++;
    replayMode = false;
    clearInterval(replayTimer);
    replayTimer = null;
    $("#timeline-label").textContent = "EPISODE TIMELINE";
    if (["start", "step"].includes(action) && state.status === "idle") {
      if (!(await reset(true))) return;
    }
    renderState(
      await api("/api/control/" + action, {
        episode_id: state.id,
        threshold: Number($("#threshold").value),
      }),
    );
  } catch (e) {
    toast(e.message);
  } finally {
    controlPending = false;
    updateControlAvailability();
  }
}
$("#run").onclick = () =>
  control(state.status === "running" ? "pause" : "start");
$("#step").onclick = () => control("step");
$("#stop").onclick = () => control("stop");
$("#reset").onclick = () => reset();
$("#export").onclick = () => {
  const a = document.createElement("a");
  a.href = "/api/export";
  a.download = "episode.json";
  a.click();
};
$("#camera-home").onclick = () => sceneView.cameraHome();
$("#camera-top").onclick = () => sceneView.cameraTop();
for (const button of document.querySelectorAll("[data-task]"))
  button.onclick = async () => {
    if (controlPending || resetting) return;
    currentTask = button.dataset.task;
    configuredScene = {};
    configuredContext = {};
    for (const b of document.querySelectorAll("[data-task]"))
      b.classList.toggle("active", b === button);
    $("#task-goal").textContent = config.tasks[currentTask].goal;
    await reset();
  };
for (const el of document.querySelectorAll("[data-tab]"))
  el.onclick = () => {
    document
      .querySelectorAll("[data-tab]")
      .forEach((b) => b.classList.toggle("active", b === el));
    $("#raw-state").classList.toggle("visible", el.dataset.tab === "data");
    visionPanel.hidden = el.dataset.tab !== "vision";
    $("#viewport").classList.toggle("vision-active", !visionPanel.hidden);
    $(".scene-tools").hidden = el.dataset.tab !== "scene";
    if (state) renderVision(state);
  };
function focusDecision() {
  (narrowLayout.matches
    ? $("#input-section")
    : $("#decision-section")
  ).scrollIntoView({ block: "start", behavior: "auto" });
  $("#decision-section").focus({ preventScroll: true });
}
$("#decision-open").onclick = focusDecision;
$("#events").onclick = (event) => {
  const button = event.target.closest("[data-cycle]");
  if (!button) return;
  selectedCycle = Number(button.dataset.cycle);
  renderState(state);
  focusDecision();
};
$("#decision-live").onclick = () => {
  selectedCycle = null;
  renderState(state);
};
$("#threshold").oninput = () =>
  ($("#threshold-value").textContent = Number($("#threshold").value).toFixed(
    2,
  ));
$("#speed").oninput = () =>
  ($("#speed-value").textContent = Number($("#speed").value).toFixed(1) + "×");
$("#provider").onchange = async () => {
  if (["omnijev", "omni_direct", "omni_reasoning", "omni_adaptive"].includes($("#provider").value)) $("#threshold").value = 0;
  $("#provider-note").textContent =
    providerNote($("#provider").value);
  if (!(await reset()))
    $("#provider").value = state?.profile_id
      ? "profile:" + state.profile_id
      : state?.provider || "baseline";
};
$("#control-mode").onchange = async () => {
  const oldBudget = $("#budget").value;
  if ($("#control-mode").value === "incremental" && Number(oldBudget) === 30)
    $("#budget").value = 100;
  if (!(await reset())) {
    $("#control-mode").value = state?.control_mode || "skills";
    $("#budget").value = oldBudget;
  }
};
$("#observation-mode").onchange = async () => {
  if (
    ["vision", "rgbd"].includes($("#observation-mode").value) &&
    $("#camera-mode").value === "none"
  )
    $("#camera-mode").value = "both";
  if (!(await reset())) {
    $("#observation-mode").value = state?.observation_mode || "privileged";
    $("#camera-mode").value = cameraSelection(enabledCameras(state));
  }
};
$("#camera-mode").onchange = async () => {
  const noCamera = $("#camera-mode").value === "none";
  if (noCamera) $("#observation-mode").value = "privileged";
  if (!(await reset())) {
    $("#camera-mode").value = cameraSelection(enabledCameras(state));
    $("#observation-mode").value = state.observation_mode || "privileged";
  } else if (noCamera) toast("Camera disabled, model uses simulated ground truth (non-visual input).");
};
$("#intervention-kind").onchange = updateControlAvailability;
function drawer(open) {
  $("#sidebar").classList.toggle("open", open);
  $("#scrim").classList.toggle("visible", open);
}
$("#settings-open").onclick = () => drawer(true);
$("#settings-close").onclick = () => drawer(false);
$("#scrim").onclick = () => drawer(false);
let replayRequest = 0;
async function showReplay(index) {
  const request = ++replayRequest;
  replayMode = true;
  replayIndex = index;
  const frame = await api("/api/replay/" + index);
  if (request !== replayRequest) return;
  renderFrame(frame);
  $("#timeline").value = index;
  $("#frame-label").textContent =
    String(index + 1).padStart(4, "0") +
    " / " +
    String(state.frame_count).padStart(4, "0");
  $("#timeline-label").textContent = "RECORDED TRAJECTORY";
  $("#status-text").textContent = "Trajectory replay";
  $("#success-stamp").classList.remove("visible");
  renderVision(state);
}
$("#timeline").oninput = async () => {
  if (state.status === "running") await control("pause");
  try {
    await showReplay(Number($("#timeline").value));
  } catch (e) {
    toast(e.message);
  }
};
$("#live").onclick = () => {
  clearInterval(replayTimer);
  replayTimer = null;
  replayRequest++;
  replayMode = false;
  $("#timeline-label").textContent = "EPISODE TIMELINE";
  renderState(state);
};
$("#replay-play").onclick = () => {
  if (replayTimer) {
    clearInterval(replayTimer);
    replayTimer = null;
    return;
  }
  replayIndex =
    replayMode && replayIndex < state.frame_count - 1 ? replayIndex : 0;
  let busy = false;
  replayTimer = setInterval(async () => {
    if (busy) return;
    if (replayIndex >= state.frame_count - 1) {
      clearInterval(replayTimer);
      replayTimer = null;
      return;
    }
    busy = true;
    try {
      await showReplay(replayIndex + 1);
    } catch (e) {
      clearInterval(replayTimer);
      replayTimer = null;
      toast(e.message);
    } finally {
      busy = false;
    }
  }, 80);
};
async function refreshProviders() {
  const previous = $("#provider").value;
  [config, { profiles: profileValues }] = await Promise.all([
    api("/api/config"),
    api("/api/model-profiles"),
  ]);
  $("#provider").innerHTML = selectionOptions(config, profileValues, escape);
  if ([...$("#provider").options].some((option) => option.value === previous))
    $("#provider").value = previous;
}
let connectionValues = {};
let connectionDraftChanged = false;
let editingProfileId = null;
let profileEditor = false;
function currentConnection() {
  if (editingProfileId)
    return (
      profileValues.find((profile) => profile.id === editingProfileId) || {}
    );
  const saved = connectionValues[$("#api-provider").value] || {};
  return profileEditor
    ? { ...saved, key_configured: false, verification: null }
    : saved;
}
function verificationLabel(saved, provider = $("#api-provider").value) {
  const ready =
    saved?.url &&
    saved?.model &&
    (!["jev", "claude"].includes(provider) || saved.key_configured);
  if (!ready) return "Not configured";
  const verification = saved.verification;
  if (verification?.status === "passed") return "Verified";
  if (verification?.status === "failed") return "Verification failed";
  return "Configured · Not verified";
}
function renderProviderStatus() {
  if (!["chat", "claude", "jev", "local"].includes(state?.provider)) {
    delete $(".provider-status").dataset.verification;
    return;
  }
  const prefix = {
    chat: "Compatible API",
    claude: "Claude API",
    jev: "TypeSafe API",
    local: "Structured API",
  }[state.provider];
  const saved = state.profile_id
    ? profileValues.find((profile) => profile.id === state.profile_id)
    : connectionValues[state.provider];
  $("#provider-note").textContent =
    `${saved?.name || prefix} · ${verificationLabel(saved, state.provider)}`;
  $(".provider-status").dataset.verification =
    saved?.verification?.status || "untested";
}
function renderVerification() {
  const saved = currentConnection();
  $("#connection-storage").textContent = storageDescription(saved.storage);
  const verification = saved.verification;
  if (profileEditor && !editingProfileId) {
    $("#connection-verification").dataset.status = "untested";
    $("#verification-label").textContent = "New configuration draft · Not saved or verified";
    return;
  }
  if (connectionDraftChanged) {
    $("#connection-verification").dataset.status = "untested";
    $("#verification-label").textContent = "Draft modified · Not saved or verified";
    return;
  }
  $("#connection-verification").dataset.status =
    verification?.status || "untested";
  $("#verification-label").textContent =
    verificationLabel(saved) +
    (verification?.status === "passed"
      ? ` · ${verification.model || saved.model}${Number.isFinite(verification.latency_ms) ? ` · ${verification.latency_ms} ms` : ""}`
      : verification?.status === "failed" && verification.message
        ? ` · ${verification.message}`
        : "");
}
function fillConnection() {
  connectionDraftChanged = false;
  const provider = $("#api-provider").value;
  const saved = currentConnection();
  $("#profile-name").value = saved.name || "";
  $("#connection-title").textContent = editingProfileId
    ? "Edit model configuration"
    : profileEditor
      ? "New model configuration"
      : "Model connection";
  $("#connection-save").hidden = $("#connection-test").hidden = profileEditor;
  $("#connection-profile").textContent = editingProfileId
    ? "Update model configuration"
    : profileEditor
      ? "Save model configuration"
      : "Save model configuration";
  $("#profile-help").textContent = editingProfileId
    ? "Empty Key Keep original key when interface address remains unchanged. Updating configuration will not automatically start the experiment."
    : "When saving as a named configuration, please fill in again Key; Cannot copy the default connection key.";
  $("#api-provider").disabled = !!editingProfileId;
  $("#api-url").value =
    provider === "chat"
      ? (saved.url || "").replace(/\/chat\/completions$/, "")
      : provider === "claude"
        ? (saved.url || "https://api.anthropic.com/v1").replace(
            /\/messages$/,
            "",
          )
        : saved.url || "";
  $("#api-url").readOnly = provider === "jev";
  $("#api-model").value = saved.model || "";
  $("#api-key").value = "";
  $("#api-key").placeholder = saved.key_configured
    ? "Empty, keep configured key"
    : "API Key";
  $("#key-state").textContent = saved.key_configured ? "Configured" : "Not configured";
  $("#api-json").checked = saved.json_mode !== false;
  $("#json-mode-row").hidden = provider !== "chat";
  $("#api-official-preset").hidden = provider !== "chat";
  $("#typesafe-links").hidden = provider !== "jev";
  $("#provider-help").textContent = {
    jev: "Official Jev Currently invitation-based: apply for access first, create after approval TypeSafe Key.Address locked; jev-latest Follow official updates; fix version when comparing, e.g. jev-1.13.0.",
    claude:
      "Claude Native Messages API, Use Anthropic Key.During testing, the model name returned by the service is displayed.",
    chat: "Fill in the provided platform Base URL and model ID.A general chat-compatible interface cannot replace Jev Dedicated decision interface.",
    local: "Fill in the complete structured decision interface address; the service needs to return candidate actions and their probabilities.",
  }[provider];
  $("#connection-result").textContent = "";
  renderVerification();
}
async function openConnection(profileId = null, asProfile = false) {
  try {
    [connectionValues, { profiles: profileValues }] = await Promise.all([
      api("/api/connections"),
      api("/api/model-profiles"),
    ]);
    const profile = profileId
      ? profileValues.find((item) => item.id === profileId)
      : null;
    if (profileId && !profile) throw new Error("Model configuration is invalid, please reselect.");
    editingProfileId = profileId;
    profileEditor = asProfile || !!profileId;
    $("#api-provider").value =
      profile?.provider ||
      (["jev", "local", "chat", "claude"].includes(state.provider)
        ? state.provider
        : "chat");
    fillConnection();
    $("#connection-dialog").showModal();
  } catch (error) {
    toast(error.message);
  }
}
$("#model-connect").onclick = () => openConnection(state?.profile_id || null);
$("#api-provider").onchange = fillConnection;
for (const input of document.querySelectorAll(
  "#api-url,#api-model,#api-key,#api-json,#profile-name",
)) {
  input.addEventListener("input", () => {
    connectionDraftChanged = true;
    $("#connection-result").textContent = "";
    renderVerification();
  });
}
$("#api-official-preset").onclick = () => {
  if (connectionPending || $("#api-provider").value !== "chat") return;
  $("#api-url").value = "https://api.openai.com/v1";
  $("#api-model").value = "gpt-6-astra";
  $("#api-key").value = "";
  $("#api-json").checked = true;
  connectionDraftChanged = true;
  renderVerification();
  $("#connection-result").textContent =
    "Official example has been filled in, but not yet called. Fill in your own Key Can test afterwards; model permissions depend on the account.";
  $("#api-key").focus();
};
$("#connection-close").onclick = () => $("#connection-dialog").close();
$("#connection-dialog").onclose = () => {
  $("#api-key").value = "";
};
async function saveConnection(testCall = false) {
  if (connectionPending) return;
  if (!$("#connection-form").reportValidity()) return;
  connectionPending = true;
  const provider = $("#api-provider").value;
  setConnectionBusy(true);
  $("#connection-result").textContent = testCall
    ? "Testing call..."
    : "Saving...";
  try {
    const saved = await api("/api/connections", {
      provider,
      url: $("#api-url").value.trim(),
      model: $("#api-model").value.trim(),
      api_key: $("#api-key").value,
      json_mode: $("#api-json").checked,
    });
    $("#api-key").value = "";
    connectionValues = await api("/api/connections");
    connectionDraftChanged = false;
    $("#key-state").textContent = connectionValues[provider].key_configured
      ? "Configured"
      : "Not configured";
    renderVerification();
    await refreshProviders();
    $("#provider").value = provider;
    await reset();
    if (testCall) {
      const result = await api(`/api/connections/${provider}/test`, {});
      $("#connection-result").textContent =
        result.ok === false
          ? `Verification failed · ${result.detail || "Please check the interface configuration"}`
          : `Call successful · ${result.model} · ${result.latency_ms} ms${result.detail ? ` · ${result.detail}` : ""}`;
      connectionValues = await api("/api/connections");
      renderVerification();
      renderProviderStatus();
    } else {
      $("#connection-dialog").close();
      toast(
        `${storageLabel(saved.storage)} · ${verificationLabel(connectionValues[provider], provider)}`,
      );
    }
  } catch (error) {
    $("#connection-result").textContent = error.message;
    try {
      connectionValues = await api("/api/connections");
      renderVerification();
      renderProviderStatus();
    } catch {
      /* Preserve the original connection error. */
    }
  } finally {
    connectionPending = false;
    setConnectionBusy(false);
  }
}
function setConnectionBusy(busy) {
  for (const input of document.querySelectorAll(
    "#api-provider,#api-url,#api-model,#api-key,#api-json,#api-official-preset,#profile-name,#connection-save,#connection-test,#connection-profile",
  ))
    input.disabled = busy;
  if (editingProfileId) $("#api-provider").disabled = true;
}
async function saveProfile() {
  if (connectionPending || !$("#connection-form").reportValidity()) return;
  const name = $("#profile-name").value.trim();
  if (!name) {
    $("#connection-result").textContent = "Please give the model configuration a name.";
    $("#profile-name").focus();
    return;
  }
  connectionPending = true;
  setConnectionBusy(true);
  $("#connection-result").textContent = "Saving model configuration...";
  try {
    const saved = await api("/api/model-profiles", {
      ...(editingProfileId ? { id: editingProfileId } : {}),
      name,
      provider: $("#api-provider").value,
      url: $("#api-url").value.trim(),
      model: $("#api-model").value.trim(),
      api_key: $("#api-key").value,
      json_mode: $("#api-json").checked,
    });
    $("#api-key").value = "";
    await refreshProviders();
    await extensionsView?.refresh();
    $("#connection-dialog").close();
    toast(`${storageLabel(saved.storage)} · Model not called.`);
  } catch (error) {
    $("#connection-result").textContent = error.message;
  } finally {
    connectionPending = false;
    setConnectionBusy(false);
  }
}
$("#connection-form").onsubmit = (event) => {
  event.preventDefault();
  if (profileEditor) saveProfile();
  else saveConnection();
};
$("#connection-test").onclick = () => saveConnection(true);
$("#connection-profile").onclick = saveProfile;

async function boot() {
  try {
    await refreshProviders();
    connectionValues = await api("/api/connections");
    $("#task-goal").textContent = config.tasks.transfer.goal;
    await loadScene();
    renderState(await api("/api/state"));
    const poll = async () => {
      try {
        if (!resetting && !controlPending) {
          const next = await api("/api/state");
          if (!resetting && !controlPending) {
            if (activeId !== next.id) await loadScene();
            renderState(next);
          }
        }
      } catch (e) {
        $("#connection").textContent = "Connection disconnected";
      }
      setTimeout(
        poll,
        document.hidden
          ? 3000
          : comparisonVisible || extensionsVisible
            ? 1500
            : state?.status === "running"
              ? 180
              : 900,
      );
    };
    poll();
  } catch (e) {
    $("#loading").textContent = "Scene loading failed";
    toast(e.message);
  }
}
boot();

fetch("/api/omnijev/status").then(r=>r.json()).then(s=>{document.querySelector("#omni-health").textContent=s.ready?"Model online":"Model not ready · Available rule demos"}).catch(()=>{document.querySelector("#omni-health").textContent="Connection failed"});

function providerNote(p){return {baseline:"Offline · Deterministic policy",omnijev:"Local · Short tag / Uncalibrated score",omni_direct:"Local · Short answer / No candidate scores",omni_reasoning:"Local · Budgeted reasoning",omni_adaptive:"Local · Experimental on-demand reasoning",jev:"Remote · TypeSafe API"}[p]||"Model interface configured"}
