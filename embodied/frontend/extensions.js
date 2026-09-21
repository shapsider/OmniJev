import {
  selectionOptions,
  selectionConfig,
  storageLabel,
  storageDescription,
} from "./model-options.js";
import "./extensions.css";

const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ],
  );
const STORE = "embodied-jev-presets-v1";
const TASKS = ["transfer", "stack", "barrier"];
function finiteJSON(value) {
  return typeof value === "number"
    ? Number.isFinite(value)
    : value && typeof value === "object"
      ? Object.values(value).every(finiteJSON)
      : true;
}
function validatedObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`${label} Must be JSON Object.`);
  if (!finiteJSON(value)) throw new Error(`${label} Cannot contain non-finite values.`);
  if (new TextEncoder().encode(JSON.stringify(value)).length > 8192)
    throw new Error(`${label} Cannot exceed 8 KB.`);
  return value;
}
function objectJSON(text, label) {
  let value;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error(`${label} Requires valid JSON.`);
  }
  return validatedObject(value, label);
}
function validatePreset(value) {
  if (!value || value.format !== "embodied-jev-preset-v1")
    throw new Error("Not supported embodied-jev-preset-v1 Preset.");
  if (
    Object.keys(value).some(
      (key) =>
        !["format", "name", "task", "scene_config", "user_context"].includes(
          key,
        ),
    )
  )
    throw new Error(
      "Preset can only include name, task, scene, and extra requirements; cannot include model connections or keys.",
    );
  if (
    typeof value.name !== "string" ||
    !value.name.trim() ||
    value.name.length > 80 ||
    !TASKS.includes(value.task)
  )
    throw new Error("Please fill in valid name and select base task template.");
  const scene = validatedObject(value.scene_config ?? {}, "Scene configuration"),
    context = validatedObject(value.user_context ?? {}, "Extra decision requirements");
  if (
    Object.keys(scene).some(
      (key) =>
        !["name", "source_xy", "target_xy", "barrier_height"].includes(key),
    )
  )
    throw new Error(
      "Scene configuration contains unsupported fields; only supports name, source_xy, target_xy, barrier_height.",
    );
  if (
    scene.name !== undefined &&
    (typeof scene.name !== "string" || scene.name.length > 80)
  )
    throw new Error("Scene name must be 80 Text within characters.");
  for (const key of ["source_xy", "target_xy"]) {
    const xy = scene[key];
    if (xy === undefined || (key === "source_xy" && xy === null)) continue;
    if (
      !Array.isArray(xy) ||
      xy.length !== 2 ||
      xy.some((value) => typeof value !== "number") ||
      xy[0] < 0.3 ||
      xy[0] > 0.58 ||
      xy[1] < -0.28 ||
      xy[1] > 0.28
    )
      throw new Error(
        "Scene coordinates need to be [X, Y]: X in 0.30–0.58, Y in -0.28–0.28 meters.",
      );
  }
  if (
    scene.barrier_height != null &&
    (value.task !== "barrier" ||
      typeof scene.barrier_height !== "number" ||
      scene.barrier_height < 0.02 ||
      scene.barrier_height > 0.16)
  )
    throw new Error("Obstacle height only applies to transfer over barrier tasks, range is 0.02–0.16 meters.");
  const secret = (item) =>
    item &&
    typeof item === "object" &&
    Object.entries(item).some(
      ([key, nested]) =>
        /^(api[_-]?key|authorization|password|secret|access[_-]?token|refresh[_-]?token)$/i.test(
          key,
        ) || secret(nested),
    );
  if (secret(scene) || secret(context))
    throw new Error("Preset detected key field; manage credentials via model connection.");
  return {
    format: "embodied-jev-preset-v1",
    name: value.name.trim(),
    task: value.task,
    scene_config: scene,
    user_context: context,
  };
}
function downloadJSON(name, value) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function createExtensions(
  container,
  { api, openConnection, applyPreset, applyModel },
) {
  const $ = (selector) => container.querySelector(selector);
  let profiles = [],
    config,
    probeBusy = false,
    actionBusy = false;
  let saved = [];
  try {
    saved = JSON.parse(localStorage.getItem(STORE) || "[]").map(validatePreset);
  } catch {
    saved = [];
  }
  container.innerHTML = `<div class="extension-heading"><div><p class="eyebrow">Configuration and experiment tools</p><h1>Extensions</h1><p>Save model connections, reuse scene presets, or test decision individually.</p></div><label>Application target<select id="ext-target"><option value="workbench">Workbench</option><option value="comparison">Model comparison</option></select></label></div>
  <details class="extension-section" id="ext-models" open><summary>Model configuration <span>Name different platforms and models</span></summary><div class="extension-body"><div class="extension-actions"><button class="secondary" id="ext-new-profile">New model configuration</button></div><div id="ext-profile-list" class="extension-profile-list"></div><p class="extension-hint" id="ext-profile-storage"></p></div></details>
  <details class="extension-section" id="ext-presets"><summary>Task and scene presets <span>Save / Import / Export JSON</span></summary><div class="extension-body"><div class="extension-grid"><label>Saved presets<select id="ext-preset-select"><option value="">New preset</option></select></label><label>Preset name<input id="ext-preset-name" maxlength="80" value="My transfer scene"></label><label>Basic task<select id="ext-task"><option value="transfer">Transfer to tray</option><option value="stack">Block stacking</option><option value="barrier">Transfer over barrier</option></select></label><label>Object X · m<input id="ext-source-x" type="number" min="0.30" max="0.58" step="any" placeholder="Leave blank to generate by seed"></label><label>Object Y · m<input id="ext-source-y" type="number" min="-0.28" max="0.28" step="any" placeholder="Leave blank to generate by seed"></label><label>Target X · m<input id="ext-target-x" type="number" min="0.30" max="0.58" step="any" value="0.43"></label><label>Target Y · m<input id="ext-target-y" type="number" min="-0.28" max="0.28" step="any" value="0.18"></label><label>Obstacle height · m<input id="ext-barrier-height" type="number" min="0.02" max="0.16" step="any" value="0.11" disabled></label></div><label class="extension-json-label">Extra decision requirements · user_context JSON<textarea id="ext-user-context" spellcheck="false" rows="5">{}</textarea></label><p class="extension-hint">JSON Do not fill in here API Key, Password or private credentials. Additional requirements must be added independently and will not overwrite actual position, contact, or success conditions. Rule baseline does not read natural language instructions; new task semantics and robot type require code extension. Reachability and safety of the scene are subject to backend verification.</p><div class="extension-actions"><button class="primary" id="ext-apply-preset">Apply preset</button><button class="secondary" id="ext-save-preset">Save to browser</button><button class="secondary" id="ext-import-preset">Import JSON</button><button class="secondary" id="ext-export-preset">Export JSON</button><input id="ext-import-file" type="file" accept="application/json,.json" hidden></div></div></details>
  <details class="extension-section" id="ext-probe"><summary>Input test <span>Select only candidates, do not move robot</span></summary><div class="extension-body"><div class="extension-grid"><label>Decision model<select id="ext-probe-provider"></select></label><label>Model ID · Optional override<input id="ext-probe-model" placeholder="Inherit existing configuration" disabled></label></div><label class="extension-json-label">Observation data · JSON<textarea id="ext-probe-observation" rows="6" spellcheck="false">{"gripper":"open","object_reachable":true}</textarea></label><label class="extension-json-label">Decision question<textarea id="ext-probe-question" rows="3">Choose the next safe action using the supplied observation.</textarea></label><label class="extension-json-label">Candidate · key → Description JSON<textarea id="ext-probe-options" rows="5" spellcheck="false">{"approach":"Move above the reachable object","hold":"Keep the current pose"}</textarea></label><div class="extension-actions"><button class="primary" id="ext-probe-run">Test a decision once</button></div><p class="extension-hint">This is an independent input experiment here, not executing robotic arm control. Rule baseline fixedly selects the first candidate for checking input flow, not validating semantics.</p><div id="ext-probe-result" class="extension-probe-result" hidden><p id="ext-probe-summary"></p><details><summary>Model return and actual input</summary><pre id="ext-probe-json"></pre></details></div></div></details><p id="ext-message" class="extension-message" role="status"></p>`;

  function showSaved() {
    $("#ext-preset-select").innerHTML =
      '<option value="">New preset</option>' +
      saved
        .map(
          (preset, index) =>
            `<option value="${index}">${escape(preset.name)}</option>`,
        )
        .join("");
  }
  function setPreset(preset) {
    $("#ext-preset-name").value = preset.name;
    $("#ext-task").value = preset.task;
    $("#ext-source-x").value = preset.scene_config.source_xy?.[0] ?? "";
    $("#ext-source-y").value = preset.scene_config.source_xy?.[1] ?? "";
    $("#ext-target-x").value = preset.scene_config.target_xy?.[0] ?? 0.43;
    $("#ext-target-y").value = preset.scene_config.target_xy?.[1] ?? 0.18;
    $("#ext-barrier-height").value = preset.scene_config.barrier_height ?? 0.11;
    $("#ext-barrier-height").disabled = preset.task !== "barrier";
    $("#ext-user-context").value = JSON.stringify(preset.user_context, null, 2);
  }
  function currentPreset() {
    if (
      ![
        ...container.querySelectorAll("#ext-presets input:not([type=file])"),
      ].every((input) => input.reportValidity())
    )
      throw new Error("Please check the scene parameter range.");
    const x = $("#ext-source-x").value,
      y = $("#ext-source-y").value;
    if (!!x !== !!y) throw new Error("Object X and Y Need to fill in together, or leave empty at the same time.");
    if (!$("#ext-target-x").value || !$("#ext-target-y").value)
      throw new Error("Please fill in the target X and Y.");
    const scene_config = {
      name: $("#ext-preset-name").value.trim(),
      source_xy: x ? [Number(x), Number(y)] : null,
      target_xy: [
        Number($("#ext-target-x").value),
        Number($("#ext-target-y").value),
      ],
    };
    if ($("#ext-task").value === "barrier")
      scene_config.barrier_height = Number($("#ext-barrier-height").value);
    return validatePreset({
      format: "embodied-jev-preset-v1",
      name: scene_config.name,
      task: $("#ext-task").value,
      scene_config,
      user_context: objectJSON($("#ext-user-context").value, "Extra decision requirements"),
    });
  }
  async function checkedPreset() {
    return api("/api/presets/validate", currentPreset());
  }
  async function handle(action) {
    if (actionBusy) return;
    actionBusy = true;
    $("#ext-message").textContent = "Processing...";
    try {
      await action();
    } catch (error) {
      $("#ext-message").textContent = error.message;
    } finally {
      actionBusy = false;
    }
  }
  $("#ext-task").onchange = () => {
    $("#ext-barrier-height").disabled = $("#ext-task").value !== "barrier";
  };
  $("#ext-preset-select").onchange = () => {
    const index = $("#ext-preset-select").value;
    if (index !== "") setPreset(saved[Number(index)]);
  };
  $("#ext-save-preset").onclick = () =>
    handle(async () => {
      const preset = await checkedPreset();
      saved = [
        ...saved.filter((item) => item.name !== preset.name),
        preset,
      ].slice(-30);
      localStorage.setItem(STORE, JSON.stringify(saved));
      showSaved();
      $("#ext-preset-select").value = saved.length - 1;
      $("#ext-message").textContent = "Saved in this browser; no inference has run.";
    });
  $("#ext-export-preset").onclick = () =>
    handle(async () =>
      downloadJSON("embodied-jev-preset.json", await checkedPreset()),
    );
  $("#ext-import-preset").onclick = () => $("#ext-import-file").click();
  $("#ext-import-file").onchange = () =>
    handle(async () => {
      const file = $("#ext-import-file").files[0];
      if (!file) return;
      if (file.size > 40000) throw new Error("Preset file too large.");
      const preset = await api(
        "/api/presets/validate",
        validatePreset(JSON.parse(await file.text())),
      );
      setPreset(preset);
      $("#ext-import-file").value = "";
      $("#ext-message").textContent = "Imported preset draft loaded; click to apply to change scene.";
    });
  $("#ext-apply-preset").onclick = () =>
    handle(async () => {
      await applyPreset(await checkedPreset(), $("#ext-target").value);
      $("#ext-message").textContent = "Preset applied; no inference has run yet.";
    });
  $("#ext-new-profile").onclick = () => openConnection();
  $("#ext-profile-list").onclick = (event) =>
    handle(async () => {
      const button = event.target.closest("[data-profile]");
      if (!button) return;
      if (button.dataset.action === "edit")
        await openConnection(button.dataset.profile);
      else {
        await applyModel(button.dataset.profile, $("#ext-target").value);
        $("#ext-message").textContent = "Model configuration selected, model not called yet.";
      }
    });
  $("#ext-probe-provider").onchange = () => {
    const selected = selectionConfig($("#ext-probe-provider").value, profiles);
    $("#ext-probe-model").disabled = ["baseline", "minicpm"].includes(
      selected.provider,
    );
    if ($("#ext-probe-model").disabled) $("#ext-probe-model").value = "";
  };
  $("#ext-probe-run").onclick = async () => {
    if (probeBusy) return;
    probeBusy = true;
    $("#ext-probe-result").hidden = true;
    $("#ext-probe-run").disabled = true;
    for (const input of container.querySelectorAll(
      "#ext-probe textarea,#ext-probe input,#ext-probe select",
    ))
      input.disabled = true;
    $("#ext-message").textContent = "Testing a decision, robot will not move...";
    try {
      const selected = selectionConfig(
        $("#ext-probe-provider").value,
        profiles,
      );
      const options = objectJSON($("#ext-probe-options").value, "Candidate");
      if (
        Object.keys(options).length < 2 ||
        Object.keys(options).length > 12 ||
        Object.values(options).some(
          (value) => typeof value !== "string" || !value.trim(),
        )
      )
        throw new Error("Please provide 2–12 candidates, each description must be a non-empty string.");
      const question = $("#ext-probe-question").value.trim();
      if (!question) throw new Error("Please fill in the decision question.");
      const model = $("#ext-probe-model").value.trim();
      const result = await api("/api/decision/probe", {
        ...selected,
        ...(model ? { model } : {}),
        observation: objectJSON($("#ext-probe-observation").value, "Observation data"),
        question,
        options,
      });
      $("#ext-probe-result").hidden = false;
      $("#ext-probe-summary").textContent =
        `Select ${result.decision.choice} · ${result.decision.model_call ? `${Number(result.decision.latency_ms).toFixed(0)} ms` : "No model call"}`;
      $("#ext-probe-json").textContent = JSON.stringify(result, null, 2);
      $("#ext-message").textContent =
        result.message || "Input test completed, robot did not execute action.";
    } catch (error) {
      $("#ext-message").textContent = error.message;
    } finally {
      probeBusy = false;
      $("#ext-probe-run").disabled = false;
      for (const input of container.querySelectorAll(
        "#ext-probe textarea,#ext-probe input,#ext-probe select",
      ))
        input.disabled = false;
      $("#ext-probe-provider").onchange();
    }
  };
  showSaved();
  async function refresh(target) {
    if (target) $("#ext-target").value = target;
    const previous = $("#ext-probe-provider").value;
    let storage;
    [config, { profiles, storage }] = await Promise.all([
      api("/api/config"),
      api("/api/model-profiles"),
    ]);
    $("#ext-profile-list").innerHTML =
      profiles
        .map(
          (profile) =>
            `<article><div><strong>${escape(profile.name)}</strong><p>${escape(profile.provider)} · ${escape(profile.model)} · ${profile.key_configured ? "Key configured" : "Key not configured"}</p><p>${escape(storageLabel(profile.storage || storage))}</p></div><div><button class="text-button" data-profile="${escape(profile.id)}" data-action="use">Use</button><button class="text-button" data-profile="${escape(profile.id)}" data-action="edit">Edit</button></div></article>`,
        )
        .join("") ||
      '<p class="extension-hint">No named model configuration yet, can use built-in rule baseline first.</p>';
    $("#ext-profile-storage").textContent =
      `${storageDescription(storage)} Key will not be written to browser preset or experiment export.`;
    $("#ext-probe-provider").innerHTML = selectionOptions(
      config,
      profiles,
      escape,
    );
    $("#ext-probe-provider").value =
      previous &&
      [...$("#ext-probe-provider").options].some(
        (option) => option.value === previous,
      )
        ? previous
        : "baseline";
    $("#ext-probe-provider").onchange();
  }
  await refresh();
  return { refresh };
}
