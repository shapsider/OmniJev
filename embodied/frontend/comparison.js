import { RobotScene } from "./robot-scene.js";
import {
  selectionOptions,
  selectionConfig,
  profileReady,
} from "./model-options.js";
import "./comparison.css";

const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ],
  );
const phases = {
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
const statuses = {
  empty: "Not started yet",
  idle: "Ready",
  queued: "Waiting to run",
  running: "Running",
  paused: "Paused",
  done: "All finished",
  stopped: "Stopped",
  completed: "Task successful",
  uncertain: "Below decision threshold",
  exhausted: "Budget exhausted",
  error: "Execution error",
  stalled: "Decision stalled",
};
const numeric = (value, digits = 1) =>
  Number.isFinite(value) ? value.toFixed(digits) : "—";
const cameraSelections = {
  none: [],
  external: ["external"],
  wrist: ["wrist"],
  both: ["external", "wrist"],
};
function enabledCameras(snapshot) {
  if (snapshot.camera_views?.length) return snapshot.camera_views;
  return ["vision", "rgbd"].includes(snapshot.observation_mode)
    ? cameraSelections.both
    : [];
}
function cameraSelection(views) {
  return views.length === 2 ? "both" : views[0] || "none";
}
function cameraNames(views) {
  return views.map((view) => (view === "wrist" ? "Wrist" : "External")).join("With");
}

export async function createComparison(container, { api, toast }) {
  const $ = (selector) => container.querySelector(selector);
  let [config, { profiles }] = await Promise.all([
    api("/api/config"),
    api("/api/model-profiles"),
  ]);
  let sceneConfig = {},
    userContext = {},
    snapshot = { id: null, status: "empty", lanes: [] };
  let active = false,
    busy = false,
    initialized = false,
    sceneLoading = false,
    loadedSceneId,
    refreshing = false,
    timer,
    pendingRefresh = Promise.resolve();
  let replayMode = false,
    replayRequest = 0,
    replayTimer,
    replayPlaying = false,
    replayTime = 0;
  let desiredReplayTime = null,
    replayLoading = false,
    replayQueue = Promise.resolve();
  const scenes = new Map(),
    completed = new Map();
  container.innerHTML = `
    <div class="comparison-heading"><div><p class="eyebrow">Same task · Independent decision</p><h1>Model comparison</h1><p>Same start point, observe how different models choose and execute. Real-time views advance separately, replay aligns with simulation time.</p></div><span class="comparison-status" id="cmp-status">Not started yet</span></div>
    <details class="comparison-setup" id="cmp-setup" open><summary>Compare settings <span id="cmp-setup-summary">Select 2–3 model</span></summary><div class="comparison-settings">
      <label>Common task<select id="cmp-task"><option value="transfer">Transfer to tray</option><option value="stack">Block stacking</option><option value="barrier">Transfer over barrier</option></select></label>
      <label>Run mode<select id="cmp-mode"><option value="sequential">Run sequentially · More resource-efficient</option><option value="parallel">Run in parallel · At most 2 path</option></select></label>
      <label>Compare quantity<select id="cmp-count"><option value="2">2 model</option><option value="3">3 model</option></select></label>
    </div><div class="comparison-lane-setup" id="cmp-lane-setup"></div>
    <details class="comparison-advanced"><summary>Jointly execute parameters</summary><div class="comparison-settings">
      <label>Random seed<input id="cmp-seed" type="number" min="0" max="99999" value="0"></label>
      <label>Action budget<input id="cmp-budget" type="number" min="1" max="200" value="30"></label>
      <label>Probability threshold<input id="cmp-threshold" type="number" min="0" max="1" step="0.05" value="0"></label>
      <label>Execution speed<input id="cmp-speed" type="number" min="0.5" max="4" step="0.5" value="1.5"></label>
      <label>Joint action decision<select id="cmp-control-mode"><option value="skills">Preset skill selection</option><option value="incremental">Incremental XYZ · Closed-loop planning</option></select></label>
      <label>Shared observation source<select id="cmp-observation-mode"><option value="privileged">Simulation ground truth · Default</option><option value="rgbd">RGB-D Visual · Experiment</option><option value="vision">Direct image · Multimodal model</option></select></label>
      <label>Enable camera jointly<select id="cmp-camera-mode"><option value="none">No camera</option><option value="external">Only external camera</option><option value="wrist">Only wrist camera</option><option value="both">Dual camera</option></select></label>
      <label class="comparison-checkbox"><input id="cmp-preview" type="checkbox" checked> Action preview</label>
    </div><p id="cmp-observation-help">Threshold is used only for native candidate probability. RGB-D mode sends detected coordinates; direct image mode sends the selected camera RGB and robot proprioceptive state, without object/Target coordinates, need incremental XYZ and support image Chat / Claude Model. Independent observations from all channels.</p><p id="cmp-camera-help">No camera · The model uses simulated ground truth, Non-visual input.</p></details>
    <p id="cmp-preset-label" class="comparison-hint" hidden></p><p class="comparison-hint">API Address and Key Inherit the default connection or “Extensions → Model configuration”. Override the model here ID; Filling in the name does not represent that the account has been granted usage permissions. Not configured API You can first use two rule baselines to experience.</p></details>
    <div class="comparison-toolbar"><button class="primary" id="cmp-start" disabled>Start comparison</button><button class="secondary" id="cmp-pause" disabled>Pause</button><button class="secondary" id="cmp-stop" disabled>Stop</button><button class="secondary" id="cmp-export" disabled>Export records</button></div>
    <p id="cmp-message" class="comparison-message" role="status"></p>
    <div class="comparison-replay" id="cmp-replay" hidden><div><strong id="cmp-time-mode">Real-time · Independent advancement of each route</strong><span id="cmp-time-range"></span></div><div class="comparison-replay-controls"><button class="secondary" id="cmp-replay-play">Play back</button><input id="cmp-timeline" type="range" min="0" max="0" step="any" value="0" aria-label="Compare unified simulation time axis"><output id="cmp-time">0.00 s</output><button class="text-button" id="cmp-live">Return to real-time</button></div></div>
    <div class="comparison-cards" id="cmp-cards"><div class="comparison-empty">After selecting a model, start comparison; real scenes and decisions will be displayed here.</div></div>
    <p class="comparison-notes" id="cmp-notes"></p>`;

  function setupRows() {
    const previous = [...container.querySelectorAll(".lane-provider")].map(
      (select, index) => ({
        provider: select.value,
        model: container.querySelector(`#cmp-model-${index}`).value,
      }),
    );
    $("#cmp-lane-setup").innerHTML = Array.from(
      { length: Number($("#cmp-count").value) },
      (_, index) =>
        `<fieldset><legend>Model ${index + 1}</legend><label>Decision interface<select class="lane-provider" id="cmp-provider-${index}" aria-label="Model ${index + 1} Decision interface">${selectionOptions(config, profiles, escape)}</select></label><label>Model ID <span>Optional override</span><input id="cmp-model-${index}" class="lane-model" aria-label="Model ${index + 1} Model ID" placeholder="Inherit existing configuration" autocomplete="off"></label></fieldset>`,
    ).join("");
    container.querySelectorAll(".lane-provider").forEach((select, index) => {
      const previousValue = previous[index]?.provider;
      select.value =
        previousValue &&
        [...select.options].some((option) => option.value === previousValue)
          ? previousValue
          : "baseline";
      $(`#cmp-model-${index}`).value = previous[index]?.model || "";
      const update = () => {
        const fixed = ["baseline", "minicpm"].includes(
          selectionConfig(select.value, profiles).provider,
        );
        $(`#cmp-model-${index}`).disabled = fixed;
        if (fixed) $(`#cmp-model-${index}`).value = "";
      };
      select.onchange = update;
      update();
    });
  }
  setupRows();
  $("#cmp-count").onchange = setupRows;
  $("#cmp-control-mode").onchange = () => {
    if (
      $("#cmp-control-mode").value === "incremental" &&
      Number($("#cmp-budget").value) === 30
    )
      $("#cmp-budget").value = 100;
  };
  function cameraHelp() {
    const views = cameraSelections[$("#cmp-camera-mode").value];
    $("#cmp-camera-help").textContent = !views.length
      ? "No camera · The model uses simulated ground truth, Non-visual input."
      : $("#cmp-observation-mode").value === "privileged"
        ? `${cameraNames(views)} Camera for viewing only; model uses simulated ground truth, Non-visual input.`
        : `Each route independently collects ${cameraNames(views)} Camera observation.`;
  }
  $("#cmp-camera-mode").onchange = () => {
    if ($("#cmp-camera-mode").value === "none") {
      $("#cmp-observation-mode").value = "privileged";
      $("#cmp-message").textContent =
        "Camera disabled, model uses simulated ground truth (non-visual input).";
    }
    cameraHelp();
  };
  $("#cmp-observation-mode").onchange = () => {
    if (
      ["vision", "rgbd"].includes($("#cmp-observation-mode").value) &&
      $("#cmp-camera-mode").value === "none"
    )
      $("#cmp-camera-mode").value = "both";
    cameraHelp();
  };
  $("#cmp-task").onchange = () => {
    sceneConfig = {};
    userContext = {};
    renderPresetLabel();
  };
  function renderPresetLabel() {
    $("#cmp-preset-label").hidden =
      !Object.keys(sceneConfig).length && !Object.keys(userContext).length;
    $("#cmp-preset-label").textContent =
      `Common scene: ${sceneConfig.name || "Custom preset"} · Apply when ready to all models.`;
  }
  async function refreshModels() {
    [config, { profiles }] = await Promise.all([
      api("/api/config"),
      api("/api/model-profiles"),
    ]);
  }

  function scenePending() {
    return !initialized || sceneLoading || loadedSceneId !== snapshot.id;
  }
  function updateControls() {
    const running = snapshot.status === "running",
      paused = snapshot.status === "paused",
      locked = busy || scenePending();
    $("#cmp-start").disabled = locked || running || paused;
    $("#cmp-start").textContent = snapshot.id ? "Re-run" : "Start comparison";
    $("#cmp-pause").disabled = locked || !(running || paused);
    $("#cmp-pause").textContent = paused ? "Continue" : "Pause";
    $("#cmp-stop").disabled = locked || !(running || paused);
    $("#cmp-export").disabled = !snapshot.id || locked;
    $("#cmp-replay-play").disabled = !snapshot.replay?.max_time || locked;
    $("#cmp-timeline").disabled = !snapshot.replay?.max_time || locked;
    for (const input of container.querySelectorAll(
      "#cmp-setup input,#cmp-setup select",
    ))
      input.disabled = locked || running || paused;
    container.querySelectorAll(".lane-provider").forEach((select, index) => {
      if (
        ["baseline", "minicpm"].includes(
          selectionConfig(select.value, profiles).provider,
        )
      )
        $(`#cmp-model-${index}`).disabled = true;
    });
    $(".comparison-toolbar").setAttribute("aria-busy", String(locked));
  }
  updateControls();

  function stopReplay() {
    replayPlaying = false;
    clearTimeout(replayTimer);
    $("#cmp-replay-play").textContent = "Play back";
  }
  function source(provider) {
    return (
      {
        baseline: "Rule selection · No model probability",
        minicpm: "Candidate token Score normalization",
        jev: "Official API Return candidate probability",
        local: "Structured API Return candidate probability",
        chat: "Structured selection · Candidate probability not provided",
        claude: "Tool selection · Candidate probability not provided",
      }[provider] || provider
    );
  }
  function options(decision, labels) {
    if (!decision) return '<span class="comparison-muted">Waiting for decision</span>';
    const entries = Object.entries(decision.probabilities || {});
    if (!entries.length)
      return `<span class="comparison-choice">${escape(labels[decision.choice] || decision.choice)} · Selected</span>`;
    return entries
      .map(
        ([choice, probability]) =>
          `<div class="comparison-probability ${choice === decision.choice ? "selected" : ""}"><span>${escape(labels[choice] || choice)}</span><b>${numeric(probability * 100)}%</b><i style="--probability:${Math.min(100, Math.max(0, probability * 100))}%"></i></div>`,
      )
      .join("");
  }

  function renderLane(lane, recorded) {
    const card = container.querySelector(`[data-lane="${lane.id}"]`);
    if (!card) return;
    const session = lane.session;
    const frame = replayMode ? recorded?.frame : session.frame;
    scenes.get(lane.id)?.render(frame);
    const observation = frame?.observation || {};
    if (session.last_decision && session.candidates?.length)
      completed.set(lane.id, {
        intent: session.last_intent,
        decision: session.last_decision,
        candidates: session.candidates,
        phase: session.phase,
      });
    const previous = !session.last_decision && completed.has(lane.id);
    const choice = replayMode
      ? recorded?.decision
      : previous
        ? completed.get(lane.id)
        : {
            intent: session.last_intent,
            decision: session.last_decision,
            candidates: session.candidates,
            phase: session.phase,
          };
    const labels = Object.fromEntries(
      (choice?.candidates || []).map((candidate) => [
        candidate.id,
        candidate.label,
      ]),
    );
    if (choice?.action) labels[choice.action.id] = choice.action.label;
    const status = lane.status === "queued" ? "queued" : session.status;
    card.querySelector(".lane-status").textContent = replayMode
      ? `Replay ${numeric(recorded?.frame_time, 2)} s${recorded?.clamped ? " · Last frame" : ""}`
      : statuses[status] || status;
    card
      .querySelector(".lane-status")
      .classList.toggle(
        "failed",
        ["error", "exhausted", "uncertain", "stalled"].includes(status),
      );
    card.querySelector(".lane-model-name").textContent =
      lane.model ||
      lane.requested_model ||
      config.providers.find((provider) => provider.id === lane.provider)
        ?.name ||
      lane.provider;
    const incremental =
      session.control_mode === "incremental" || choice?.phase === "incremental";
    const direct = session.observation_mode === "vision";
    card.querySelector(".lane-source").textContent = source(lane.provider);
    card.querySelector(".lane-input-source").textContent = direct
      ? `Model input · ${cameraNames(enabledCameras(session))} RGB + Own state; object/Target judged by image`
      : session.observation_mode === "rgbd"
        ? "Model input · RGB-D Detection coordinates + Contact sensor"
        : `Non-visual input · Simulation ground truth ${enabledCameras(session).length ? "; Camera for viewing only" : "; No camera"}`;
    card.querySelector(".lane-decision-mode").textContent = replayMode
      ? "Decision at the simulated moment"
      : previous
        ? "Previous selection · New decision calculation"
        : "Current decision";
    card.querySelector(".lane-phase-heading").textContent = incremental
      ? "Action intention"
      : "Stage selection";
    card.querySelector(".lane-phase").innerHTML = incremental
      ? `<span class="comparison-choice">${escape(choice?.decision?.intent || (choice?.decision ? "No action intent provided" : "Waiting for decision"))}</span>`
      : options(choice?.intent, phases);
    card.querySelector(".lane-action").innerHTML = options(choice?.decision, {
      direct: "Normal execution",
      gentle: "Decelerated execution",
      hold: "Remain stationary",
      ...labels,
    });
    card.querySelector(".lane-planning").hidden = !incremental;
    const action =
      choice?.action ||
      choice?.candidates?.find(
        (candidate) => candidate.id === choice?.decision?.choice,
      );
    const before =
      choice?.before ||
      session.last_decision_inputs?.action?.state?.observation;
    const delta =
      action?.delta_xyz ||
      (action?.target?.length === 3 && before?.tcp?.length === 3
        ? action.target.map((value, index) => value - before.tcp[index])
        : null);
    card.querySelector(".lane-action-detail").textContent = !action
      ? "Waiting for selection"
      : `${delta?.every(Number.isFinite) ? `ΔXYZ (${delta.map((value) => `${value >= 0 ? "+" : ""}${value.toFixed(3)}`).join(", ")}) m` : "ΔXYZ Not recorded"} · Gripper ${{ open: "Open", close: "Close", closed: "Close" }[action.gripper] || "Keep"}`;
    card.querySelector(".lane-evidence").textContent =
      choice?.decision?.visual_evidence ||
      (direct ? "Model did not provide visual basis" : "Current input is structured observation");
    card.querySelector(".lane-pose").textContent =
      (observation.tcp || [])
        .map((position) => numeric(position, 3))
        .join(" / ") || "—";
    card.querySelector(".lane-fingers").textContent =
      `${observation.gripper === "closed" ? "Close" : "Open"} · ${observation.held ? "Two-sided grip" : observation.finger_contacts?.length ? "Single-sided contact" : "No object contact"}`;
    card.querySelector(".lane-sim").textContent =
      `${numeric(observation.sim_seconds, 2)} s`;
    const latency =
      (choice?.intent?.model_call ? choice.intent.latency_ms : 0) +
      (choice?.decision?.model_call ? choice.decision.latency_ms : 0);
    card.querySelector(".lane-latency").textContent = latency
      ? `${numeric(latency, 0)} ms`
      : "No model call";
    card.querySelector(".lane-stat-title").textContent = replayMode
      ? "Cumulative statistics for the entire round (not this frame)"
      : "Cumulative statistics for this route";
    card.querySelector(".lane-statistics").textContent =
      `Call ${session.model_calls} Times · Input ${session.input_tokens} / Output ${session.output_tokens || 0} tokens · Duration ${numeric(session.wall_seconds, 2)} s`;
    card.querySelector(".lane-message").textContent = replayMode
      ? recorded?.clamped
        ? "This run has reached the last frame currently recorded."
        : ""
      : session.message || "";
  }

  async function render(next) {
    const changed = next.id !== snapshot.id || loadedSceneId !== next.id;
    snapshot = next;
    if (changed) {
      sceneLoading = true;
      $("#cmp-status").textContent = "Loading scene...";
      updateControls();
      stopReplay();
      replayMode = false;
      replayRequest++;
      completed.clear();
      for (const scene of scenes.values()) scene.dispose();
      scenes.clear();
      if (next.id && !busy) {
        sceneConfig = next.config?.scene_config || {};
        userContext = next.config?.user_context || {};
        renderPresetLabel();
        for (const [field, key] of [
          ["task", "task"],
          ["seed", "seed"],
          ["budget", "max_cycles"],
          ["threshold", "threshold"],
          ["speed", "speed"],
          ["observation-mode", "observation_mode"],
          ["control-mode", "control_mode"],
        ])
          if (next.config?.[key] !== undefined)
            $(`#cmp-${field}`).value = next.config[key];
        $("#cmp-preview").checked = next.config?.preview !== false;
        $("#cmp-camera-mode").value = cameraSelection(
          enabledCameras(next.config || {}),
        );
        cameraHelp();
        $("#cmp-mode").value = next.mode;
        $("#cmp-count").value = next.lanes.length;
        setupRows();
        next.lanes.forEach((lane, index) => {
          const profileId = lane.profile_id || lane.session.profile_id;
          $(`#cmp-provider-${index}`).value = profileId
            ? "profile:" + profileId
            : lane.provider;
          $(`#cmp-model-${index}`).value = ["baseline", "minicpm"].includes(
            lane.provider,
          )
            ? ""
            : lane.requested_model || "";
        });
        $("#cmp-setup").open = false;
        updateControls();
      }
      $("#cmp-cards").innerHTML =
        next.lanes
          .map(
            (lane, index) =>
              `<article class="comparison-card" data-lane="${escape(lane.id)}"><header><div><span class="comparison-lane-label">Model ${index + 1} · ${escape(config.providers.find((provider) => provider.id === lane.provider)?.name || lane.provider)}</span><h2 class="lane-model-name"></h2></div><span class="lane-status"></span></header><div class="comparison-scene"><div class="comparison-camera"><button type="button" data-camera="home">Reset view</button><button type="button" data-camera="top">Top-down view</button></div></div><div class="comparison-card-body"><p class="lane-source"></p><p class="lane-input-source"></p><p class="lane-decision-mode"></p><div class="comparison-decision-grid"><section><h3 class="lane-phase-heading">Stage selection</h3><div class="lane-phase"></div></section><section><h3>Action output</h3><div class="lane-action"></div></section></div><div class="lane-planning" hidden><p><span>Action in this step</span><strong class="lane-action-detail"></strong></p><p><span>Visual basis</span><strong class="lane-evidence"></strong></p><p class="lane-planning-note">Physical success and planning capability need to be verified separately.</p></div><dl><dt>End effector X / Y / Z · m</dt><dd class="lane-pose"></dd><dt>Gripper / Contact</dt><dd class="lane-fingers"></dd><dt>Simulation time</dt><dd class="lane-sim"></dd><dt>Inference time for this request</dt><dd class="lane-latency"></dd></dl><p class="lane-message"></p><details><summary class="lane-stat-title">Cumulative statistics for this route</summary><p class="lane-statistics"></p></details></div></article>`,
          )
          .join("") ||
        '<div class="comparison-empty">After selecting a model, start comparison; real scenes and decisions will be displayed here.</div>';
      $("#cmp-cards").style.setProperty("--lane-count", next.lanes.length || 2);
      try {
        if (next.id)
          await Promise.all(
            next.lanes.map(async (lane) => {
              const element = container.querySelector(
                `[data-lane="${lane.id}"] .comparison-scene`,
              );
              const scene = new RobotScene(element, {
                label: `${lane.id} Robotic arm 3D scene`,
                pixelRatio: 1.25,
                onError: toast,
              });
              scenes.set(lane.id, scene);
              scene.load(
                await api(
                  `/api/comparison/scene/${lane.id}?comparison_id=${encodeURIComponent(next.id)}`,
                ),
              );
              element.querySelector('[data-camera="home"]').onclick = () =>
                scene.cameraHome();
              element.querySelector('[data-camera="top"]').onclick = () =>
                scene.cameraTop();
            }),
          );
        loadedSceneId = next.id;
      } finally {
        sceneLoading = false;
      }
    }
    initialized = true;
    $("#cmp-status").textContent = statuses[next.status] || next.status;
    $("#cmp-replay").hidden = !next.id;
    $("#cmp-time-range").textContent =
      `Joint recording ${numeric(next.replay?.common_time, 2)} s · Longest ${numeric(next.replay?.max_time, 2)} s`;
    $("#cmp-timeline").max = next.replay?.max_time || 0;
    $("#cmp-notes").textContent = (next.notes || []).join(" ");
    if (!replayMode) {
      syncLiveTime();
      next.lanes.forEach((lane) => renderLane(lane));
    }
    updateControls();
  }

  function syncLiveTime() {
    const time = snapshot.replay?.max_time || 0;
    $("#cmp-time-mode").textContent = "Real-time · Independent advancement of each route";
    $("#cmp-time").textContent = `${numeric(time, 2)} s`;
    $("#cmp-timeline").value = time;
  }

  function refresh() {
    if (refreshing || busy) {
      schedule();
      return;
    }
    refreshing = true;
    pendingRefresh = (async () => {
      try {
        await render(await api("/api/comparison"));
      } catch (error) {
        $("#cmp-message").textContent = error.message;
      } finally {
        refreshing = false;
        schedule();
      }
    })();
    return pendingRefresh;
  }
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(
      refresh,
      document.hidden || !active
        ? 3000
        : snapshot.status === "running"
          ? 180
          : 900,
    );
  }
  async function control(action) {
    if (busy || scenePending() || !snapshot.id) return;
    const comparisonId = snapshot.id;
    busy = true;
    updateControls();
    try {
      await pendingRefresh;
      if (snapshot.id !== comparisonId)
        throw new Error("Comparison updated, please check current state before operating.");
      await render(
        await api(`/api/comparison/control/${action}`, {
          comparison_id: comparisonId,
        }),
      );
    } catch (error) {
      $("#cmp-message").textContent = error.message;
    } finally {
      busy = false;
      updateControls();
    }
  }
  $("#cmp-start").onclick = async () => {
    if (busy || scenePending()) return;
    const expectedId = snapshot.id;
    if (
      ![...container.querySelectorAll("#cmp-setup input")].every((input) =>
        input.reportValidity(),
      )
    )
      return;
    busy = true;
    updateControls();
    $("#cmp-message").textContent = "";
    try {
      if ($("#cmp-observation-mode").value === "vision") {
        if ($("#cmp-control-mode").value !== "incremental")
          throw new Error(
            "Direct image input requires “Incremental XYZ”Action decision. Please modify joint execution parameters.",
          );
        if (
          ![...container.querySelectorAll(".lane-provider")].every((select) =>
            ["chat", "claude", "omnijev", "omni_direct", "omni_reasoning", "omni_adaptive"].includes(
              selectionConfig(select.value, profiles).provider,
            ),
          )
        )
          throw new Error(
            "Direct image requirement: each route must use image support. Chat or Claude model, please modify model interface.",
          );
      }
      await pendingRefresh;
      if (snapshot.id !== expectedId)
        throw new Error("Comparison updated, please check current state before creating.");
      await refreshModels();
      const lanes = [...container.querySelectorAll(".lane-provider")].map(
        (select, index) => {
          const selected = selectionConfig(select.value, profiles);
          const ready = selected.profile_id
            ? profileReady(
                profiles.find((profile) => profile.id === selected.profile_id),
              )
            : config.providers.find(
                (provider) => provider.id === selected.provider,
              )?.ready;
          if (!ready)
            throw new Error("First configure the model connection on the workbench, then start the comparison.");
          const model = $(`#cmp-model-${index}`).value.trim();
          return { ...selected, ...(model ? { model } : {}) };
        },
      );
      const next = await api("/api/comparison", {
        task: $("#cmp-task").value,
        scene_config: sceneConfig,
        user_context: userContext,
        observation_mode: $("#cmp-observation-mode").value,
        control_mode: $("#cmp-control-mode").value,
        camera_views: [...cameraSelections[$("#cmp-camera-mode").value]],
        seed: Number($("#cmp-seed").value),
        preview: $("#cmp-preview").checked,
        threshold: Number($("#cmp-threshold").value),
        max_cycles: Number($("#cmp-budget").value),
        speed: Number($("#cmp-speed").value),
        mode: $("#cmp-mode").value,
        lanes,
        expected_comparison_id: expectedId,
      });
      await render(next);
      $("#cmp-setup").open = false;
      $("#cmp-setup-summary").textContent =
        `${lanes.length} path · ${$("#cmp-task").selectedOptions[0].textContent} · ${$("#cmp-mode").value === "parallel" ? "At most two parallel paths" : "Run sequentially"}`;
      await render(
        await api("/api/comparison/control/start", {
          comparison_id: snapshot.id,
        }),
      );
    } catch (error) {
      $("#cmp-message").textContent = error.message;
    } finally {
      busy = false;
      updateControls();
    }
  };
  $("#cmp-pause").onclick = () => {
    stopReplay();
    desiredReplayTime = null;
    replayRequest++;
    replayMode = false;
    syncLiveTime();
    control(snapshot.status === "paused" ? "start" : "pause");
  };
  $("#cmp-stop").onclick = () => control("stop");
  $("#cmp-export").onclick = () => {
    const link = document.createElement("a");
    link.href = `/api/comparison/export?comparison_id=${encodeURIComponent(snapshot.id)}`;
    link.download = `comparison-${snapshot.id}.json`;
    link.click();
  };
  async function replayAt(time) {
    const request = ++replayRequest;
    const comparisonId = snapshot.id;
    if (snapshot.status === "running") await control("pause");
    if (request !== replayRequest || busy || snapshot.id !== comparisonId)
      return;
    if (snapshot.status === "running")
      throw new Error("Pause incomplete, please replay later.");
    replayMode = true;
    const result = await api(
      `/api/comparison/replay?time=${time}&comparison_id=${encodeURIComponent(comparisonId)}`,
    );
    if (request !== replayRequest || result.id !== snapshot.id) return;
    replayTime = result.time;
    $("#cmp-time-mode").textContent = "Record playback · Align by uniform simulation time";
    $("#cmp-time").textContent = `${numeric(result.time, 2)} s`;
    $("#cmp-timeline").value = result.time;
    snapshot.lanes.forEach((lane) =>
      renderLane(
        lane,
        result.lanes.find((item) => item.id === lane.id),
      ),
    );
  }
  function queueReplay(time) {
    desiredReplayTime = time;
    if (replayLoading) return replayQueue;
    replayLoading = true;
    replayQueue = (async () => {
      while (desiredReplayTime !== null) {
        const next = desiredReplayTime;
        desiredReplayTime = null;
        await replayAt(next);
      }
    })().finally(() => {
      replayLoading = false;
    });
    return replayQueue;
  }
  $("#cmp-timeline").oninput = () => {
    stopReplay();
    queueReplay(Number($("#cmp-timeline").value)).catch((error) => {
      $("#cmp-message").textContent = error.message;
    });
  };
  $("#cmp-live").onclick = () => {
    stopReplay();
    desiredReplayTime = null;
    replayRequest++;
    replayMode = false;
    syncLiveTime();
    snapshot.lanes.forEach((lane) => renderLane(lane));
  };
  $("#cmp-replay-play").onclick = async () => {
    if (replayPlaying) {
      stopReplay();
      return;
    }
    replayPlaying = true;
    $("#cmp-replay-play").textContent = "Pause playback";
    if (!replayMode || replayTime >= snapshot.replay.max_time) replayTime = 0;
    const tick = async () => {
      if (!replayPlaying || !active) return;
      try {
        await queueReplay(Math.min(snapshot.replay.max_time, replayTime + 0.1));
      } catch (error) {
        $("#cmp-message").textContent = error.message;
        stopReplay();
        return;
      }
      if (replayTime >= snapshot.replay.max_time) {
        stopReplay();
        return;
      }
      if (replayPlaying) replayTimer = setTimeout(tick, 120);
    };
    await tick();
  };
  await refresh();
  async function editableDraft() {
    await pendingRefresh;
    if (busy || ["running", "paused"].includes(snapshot.status))
      throw new Error("Please stop model comparison first, then modify preset or model.");
  }
  return {
    async applyPreset(preset) {
      await editableDraft();
      $("#cmp-task").value = preset.task;
      sceneConfig = structuredClone(preset.scene_config);
      userContext = structuredClone(preset.user_context);
      renderPresetLabel();
      $("#cmp-setup").open = true;
      $("#cmp-message").textContent =
        "The preset has been loaded into the shared settings. Scenes are created and models are called only after Start is clicked.";
    },
    async applyModel(profileId) {
      await editableDraft();
      await refreshModels();
      setupRows();
      if (!profiles.some((profile) => profile.id === profileId))
        throw new Error("Model configuration is invalid, please reselect.");
      $("#cmp-provider-0").value = "profile:" + profileId;
      $("#cmp-provider-0").onchange();
      $("#cmp-setup").open = true;
      $("#cmp-message").textContent =
        "Model filled in 1; Other models can be selected in comparison settings. model not called yet.";
    },
    async setActive(value) {
      active = value;
      if (!value) {
        stopReplay();
        schedule();
        return;
      }
      clearTimeout(timer);
      try {
        await refreshModels();
        setupRows();
        updateControls();
        await refresh();
      } catch (error) {
        $("#cmp-message").textContent = error.message;
      }
    },
  };
}
