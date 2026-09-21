import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const pixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5N8AAAAASUVORK5CYII=",
  "base64",
);
const emptyZip = Buffer.from(
  "504b0506000000000000000000000000000000000000",
  "hex",
);

async function planningFixture(page) {
  // All service responses are fixtures: these tests verify the UI contract,
  // not model quality or the physical planner's success rate.
  const config = {
    tasks: Object.fromEntries(
      ["transfer", "stack", "barrier"].map((task) => [
        task,
        { goal: "Place the block into the target area" },
      ]),
    ),
    providers: [
      { id: "baseline", name: "Rule baseline", ready: true },
      { id: "chat", name: "OpenAI Compatible API", ready: true },
      { id: "claude", name: "Claude Native API", ready: true },
    ],
  };
  const snapshot = {
    id: "mock-planning",
    task: "transfer",
    provider: "baseline",
    status: "idle",
    stage: "ready",
    phase: null,
    control_mode: "skills",
    observation_mode: "privileged",
    camera_views: [],
    intervention: null,
    interventions: [],
    shuffle_candidates: false,
    seed: 0,
    max_cycles: 30,
    threshold: 0.55,
    speed: 1.5,
    preview: true,
    scene_config: {},
    user_context: {},
    perception: null,
    cycles: 0,
    frame_count: 1,
    model_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    wall_seconds: 0,
    history: [],
    events: [],
    candidates: [],
    last_decision: null,
    frame: {
      time: 0,
      qpos: [],
      positions: {},
      rotations: {},
      observation: {
        tcp: [0.3, 0, 0.2],
        gripper: "open",
        finger_contacts: [],
        sim_seconds: 0,
        success: false,
      },
    },
  };
  const metadata = {
    capture_id: "capture-1",
    source: "vision",
    status: "ready",
    captured_at: "2026-09-20T12:00:00Z",
    sim_time: 0.12,
    latency_ms: 18.4,
    objects: [],
    camera_views: ["external", "wrist"],
  };
  const requests = { resets: [], images: [], comparisons: [], exports: [] };
  const archive = { status: 200 };
  let comparison = { id: null, status: "empty", lanes: [] };
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const body =
      route.request().method() === "POST"
        ? route.request().postDataJSON()
        : null;
    let json;
    if (path === "/api/omnijev/status") json = { ready: true, model: "fixture-model" };
    else if (path === "/api/config") json = config;
    else if (path === "/api/model-profiles") json = { profiles: [] };
    else if (path === "/api/connections") json = {};
    else if (path === "/api/state") json = snapshot;
    else if (path === "/api/scene" || path.startsWith("/api/comparison/scene/"))
      json = { task: snapshot.task, geometries: [], meshes: {} };
    else if (path === "/api/reset") {
      requests.resets.push(body);
      Object.assign(snapshot, body, {
        id: `mock-planning-${requests.resets.length}`,
      });
      metadata.source = body.observation_mode;
      metadata.camera_views = [...body.camera_views];
      snapshot.perception = body.camera_views.length ? { ...metadata } : null;
      json = snapshot;
    } else if (path === "/api/perception") json = metadata;
    else if (path === "/api/export/cameras.zip") {
      requests.exports.push(url);
      if (archive.status !== 200)
        return route.fulfill({
          status: archive.status,
          json: { detail: "The experiment has been updated; please retry the export." },
        });
      return route.fulfill({
        contentType: "application/zip",
        headers: {
          "Content-Disposition": 'attachment; filename="observations.zip"',
        },
        body: emptyZip,
      });
    } else if (/^\/api\/perception\/.+\.png$/.test(path)) {
      requests.images.push(url);
      return route.fulfill({ contentType: "image/png", body: pixel });
    } else if (path === "/api/comparison" && body) {
      requests.comparisons.push(body);
      comparison = {
        id: `mock-comparison-${requests.comparisons.length}`,
        status: "idle",
        mode: body.mode,
        config: body,
        lanes: body.lanes.map((lane, index) => ({
          id: `lane-${index}`,
          ...lane,
          status: "idle",
          model: "Fixture multimodal model",
          session: { ...snapshot, ...body, ...lane },
        })),
        replay: { max_time: 0, common_time: 0 },
      };
      json = comparison;
    } else if (path === "/api/comparison") json = comparison;
    else if (path === "/api/comparison/control/start") json = comparison;
    else throw new Error(`Unmocked API request: ${path}`);
    await route.fulfill({ json });
  });
  return { snapshot, metadata, requests, archive };
}

async function boot(page) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator("#connection")).toContainText("Connected");
}

test("mocked planning settings validate vision and preserve modes across reset and task changes", async ({
  page,
}) => {
  const { requests } = await planningFixture(page);
  await boot(page);
  await page.locator("#observation-mode").selectOption("vision");
  await expect(page.locator("#toast")).toContainText("requires “Incremental XYZ”");
  await expect(page.locator("#observation-mode")).toHaveValue("privileged");
  expect(requests.resets).toHaveLength(0);
  await page.locator("#control-mode").selectOption("incremental");
  await expect(page.locator("#control-mode")).toHaveValue("incremental");
  await expect
    .poll(() => requests.resets.at(-1)?.control_mode)
    .toBe("incremental");
  expect(requests.resets.at(-1).max_cycles).toBe(100);
  await page.locator("#observation-mode").selectOption("vision");
  await expect(page.locator("#toast")).toContainText("Chat / Claude");
  await expect(page.locator("#observation-mode")).toHaveValue("privileged");
  await page.locator("#provider").selectOption("chat");
  await expect(page.locator("#observation-mode")).toBeEnabled();
  await page.locator("#observation-mode").selectOption("vision");
  await expect
    .poll(() => requests.resets.at(-1)?.observation_mode)
    .toBe("vision");
  expect(requests.resets.at(-1).control_mode).toBe("incremental");
  await page.locator('[data-task="barrier"]').click();
  await expect.poll(() => requests.resets.at(-1)?.task).toBe("barrier");
  await page.locator("#reset").click();
  await expect(page.locator("#reset")).toBeEnabled();
  expect(requests.resets.at(-1)).toMatchObject({
    control_mode: "incremental",
    observation_mode: "vision",
    camera_views: ["external", "wrist"],
    provider: "chat",
    max_cycles: 100,
  });
  await page.locator("#provider").selectOption("baseline");
  await expect(page.locator("#toast")).toContainText("Chat / Claude");
  await expect(page.locator("#provider")).toHaveValue("chat");
  await expect(page.locator("#budget")).toHaveAttribute("max", "200");
});

test("mocked direct-image decisions show evidence and exact delta with independent camera views", async ({
  page,
}, testInfo) => {
  const { snapshot, metadata, requests } = await planningFixture(page);
  Object.assign(snapshot, {
    provider: "chat",
    control_mode: "incremental",
    observation_mode: "vision",
    camera_views: ["external", "wrist"],
    phase: "incremental",
    perception: { ...metadata },
    cycles: 1,
    candidates: [
      {
        id: "move_x",
        label: "Along X Move in the direction",
        phase: "incremental",
        target: [0.33, 0, 0.2],
        delta_xyz: [0.03, 0, 0],
        gripper: "open",
        admitted: true,
      },
    ],
    last_decision: {
      choice: "move_x",
      intent: "Approach the red block in the image",
      visual_evidence: "The block is to the right of the gripper, and the target tray is farther away.",
      image_sha256: "a".repeat(64),
      model: "Fixture multimodal model",
      model_call: true,
      latency_ms: 120,
      probabilities: {},
    },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await boot(page);
  await expect(page.locator("#input-positions")).toContainText("Determine from image");
  await expect(page.locator("#planning-intent")).toHaveText(
    "Approach the red block in the image",
  );
  await expect(page.locator("#planning-evidence")).toContainText(
    "The block is to the right of the gripper",
  );
  await expect(page.locator("#planning-action")).toHaveText(
    "ΔXYZ (+0.030, +0.000, +0.000) m · Gripper Open",
  );
  await expect(page.locator("#planning-image")).toContainText("a".repeat(64));
  await expect(page.locator("#decision-note")).toContainText(
    "Physical success does not equal verified planning capability",
  );
  await page.locator('[data-tab="vision"]').click();
  await expect(page.locator("#vision-image")).toBeVisible();
  await expect(page.locator("#vision-visibility")).toHaveText("Determine from image");
  await expect(page.locator("#vision-status")).not.toHaveClass(/has-alert/);
  await expect(page.locator("#vision-source-label")).toContainText(
    "Multimodal model",
  );
  await expect(page.locator("#vision-note")).toContainText("not real-time video");
  await expect(page.locator('[data-vision-channel="depth"]')).toBeDisabled();
  await page.locator('[data-vision-view="wrist"]').click();
  await expect(page.locator("#vision-image")).toHaveAttribute(
    "src",
    /view=wrist/,
  );
  await expect(page.locator("#vision-view-help")).toContainText("Moves with the robotic arm");
  expect(requests.resets).toHaveLength(0);
  expect(requests.images.at(-1).pathname).toBe("/api/perception/rgb.png");
  // RGB-D permits depth; view and channel remain independent.
  snapshot.observation_mode = "rgbd";
  metadata.source = "rgbd";
  metadata.capture_id = "capture-2";
  snapshot.perception = { ...metadata };
  await expect(page.locator('[data-vision-channel="depth"]')).toBeEnabled();
  await page.locator('[data-vision-channel="depth"]').click();
  await expect(page.locator("#vision-image")).toHaveAttribute(
    "src",
    /depth\.png.*view=wrist/,
  );
  await page.locator('[data-vision-view="external"]').click();
  await expect(page.locator("#vision-image")).toHaveAttribute(
    "src",
    /depth\.png.*view=external/,
  );
  await expect(page.locator("#vision-time")).toHaveText("t = 0.12 s");
  for (const width of [1440, 768, 390, 330]) {
    await page.setViewportSize({ width, height: 960 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    expect(
      await page
        .locator("#planning-output")
        .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
    await expect(page.locator('[data-vision-view="wrist"]')).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`planning-${width}.png`),
      fullPage: true,
    });
  }
  expect(errors).toEqual([]);
});

test("mocked comparison requires visual providers and forwards shared incremental settings", async ({
  page,
}) => {
  const { snapshot, requests } = await planningFixture(page);
  snapshot.phase = "incremental";
  snapshot.candidates = [
    {
      id: "up",
      label: "Move upward",
      phase: "incremental",
      delta_xyz: [0, 0, 0.02],
      gripper: null,
    },
  ];
  snapshot.last_decision = {
    choice: "up",
    intent: "Raise the gripper to pass over the obstacle",
    visual_evidence: "The obstacle is in front of the gripper.",
    probabilities: {},
    model_call: true,
    latency_ms: 120,
  };
  await boot(page);
  await page.locator("#comparison-open").click();
  await expect(page.locator("#cmp-start")).toBeEnabled();
  await page.locator(".comparison-advanced > summary").click();
  await page.locator("#cmp-observation-mode").selectOption("vision");
  await page.locator("#cmp-start").click();
  await expect(page.locator("#cmp-message")).toContainText("requires “Incremental XYZ”");
  await page.locator("#cmp-control-mode").selectOption("incremental");
  await expect(page.locator("#cmp-budget")).toHaveValue("100");
  await page.locator("#cmp-start").click();
  await expect(page.locator("#cmp-message")).toContainText("each route");
  expect(requests.comparisons).toHaveLength(0);
  await page.locator("#cmp-provider-0").selectOption("chat");
  await page.locator("#cmp-provider-1").selectOption("claude");
  await page.locator("#cmp-start").click();
  await expect(page.locator(".comparison-card")).toHaveCount(2);
  expect(requests.comparisons[0]).toMatchObject({
    control_mode: "incremental",
    observation_mode: "vision",
    max_cycles: 100,
  });
  await expect(page.locator(".lane-phase").first()).toHaveText(
    "Raise the gripper to pass over the obstacle",
  );
  await expect(page.locator(".lane-evidence").first()).toHaveText(
    "The obstacle is in front of the gripper.",
  );
  await expect(page.locator(".lane-action-detail").first()).toHaveText(
    "ΔXYZ (+0.000, +0.000, +0.020) m · Gripper Keep",
  );
  await expect(page.locator(".lane-input-source").first()).toContainText(
    "Object/Target judged by image",
  );
});

test("mocked evaluation settings persist, validate displacements and lock while running", async ({
  page,
}) => {
  const { snapshot, requests } = await planningFixture(page);
  snapshot.intervention = {
    kind: "target_shift",
    after_cycle: 7,
    delta_xy: [-0.02, 0.01],
  };
  snapshot.shuffle_candidates = true;
  await boot(page);
  await page.locator("#advanced-settings > summary").click();
  await expect(page.locator("#intervention-kind")).toHaveValue("target_shift");
  await expect(page.locator("#intervention-cycle")).toHaveValue("7");
  await expect(page.locator("#intervention-x")).toHaveValue("-0.02");
  await expect(page.locator("#intervention-y")).toHaveValue("0.01");
  await expect(page.locator("#shuffle-candidates")).toBeChecked();
  await expect(page.locator("#intervention-help")).toContainText(
    "not a model action",
  );
  await page.locator("#intervention-kind").selectOption("object_shift");
  await page.locator("#intervention-cycle").fill("5");
  await page.locator("#intervention-x").fill("0");
  await page.locator("#intervention-y").fill("0");
  await page.locator("#reset").click();
  await expect(page.locator("#toast")).toContainText("Cannot be simultaneously zero");
  expect(requests.resets).toHaveLength(0);
  await page.locator("#intervention-x").fill("0.07");
  await page.locator("#reset").click();
  await expect(page.locator("#toast")).toContainText("±0.06 meters");
  expect(requests.resets).toHaveLength(0);
  await page.locator("#intervention-x").fill("0.04");
  await page.locator("#reset").click();
  await expect.poll(() => requests.resets.length).toBe(1);
  await expect(page.locator("#reset")).toBeEnabled();
  expect(requests.resets[0]).toMatchObject({
    intervention: { kind: "object_shift", after_cycle: 5, delta_xy: [0.04, 0] },
    shuffle_candidates: true,
  });
  await expect(page.locator("#intervention-x")).toHaveValue("0.04");
  snapshot.status = "running";
  for (const selector of [
    "#intervention-kind",
    "#intervention-cycle",
    "#intervention-x",
    "#intervention-y",
    "#shuffle-candidates",
  ])
    await expect(page.locator(selector)).toBeDisabled();
  snapshot.interventions = [
    {
      kind: "object_shift",
      after_cycle: 5,
      sim_time: 1.2,
      delta_xy: [0.04, 0],
    },
  ];
  await expect(page.locator("#intervention-status")).toContainText(
    "Injected 1 external evaluation perturbations",
  );
  await expect(page.locator("#log-entries")).toContainText(
    "External evaluation disturbance: move the block",
  );
  await expect(page.locator("#event-count")).toHaveText("0 Item");
  snapshot.status = "idle";
  await expect(page.locator("#intervention-kind")).toBeEnabled();
  await page.locator("#intervention-kind").selectOption("none");
  await expect(page.locator("#intervention-fields")).toBeHidden();
  await page.locator("#shuffle-candidates").uncheck();
  await page.locator("#reset").click();
  await expect.poll(() => requests.resets.length).toBe(2);
  expect(requests.resets[1]).toMatchObject({
    intervention: null,
    shuffle_candidates: false,
  });
});

test("mocked camera archive download follows the current episode and requires a capture", async ({
  page,
}) => {
  const { snapshot, metadata, requests } = await planningFixture(page);
  await boot(page);
  await page.locator('[data-tab="vision"]').click();
  await expect(page.locator("#vision-export")).toBeDisabled();
  Object.assign(snapshot, {
    id: "new-camera-episode",
    provider: "chat",
    control_mode: "incremental",
    observation_mode: "vision",
    camera_views: ["external", "wrist"],
    perception: { ...metadata },
  });
  await expect(page.locator("#vision-export")).toBeEnabled();
  await expect(page.locator(".vision-download-row")).toContainText(
    "All RGB Viewpoint + SHA-256 List",
  );
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#vision-export").click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
  expect(await download.failure()).toBeNull();
  expect(await readFile(await download.path())).toEqual(emptyZip);
  expect(requests.exports).toHaveLength(1);
  expect(requests.exports[0].searchParams.get("episode_id")).toBe(
    "new-camera-episode",
  );
  expect(requests.resets).toHaveLength(0);
  snapshot.perception = null;
  await expect(page.locator("#vision-export")).toBeDisabled();
});

test("mocked camera configuration supports all four modes and keeps preview separate from model vision", async ({
  page,
}) => {
  const { snapshot, requests } = await planningFixture(page);
  await boot(page);
  await expect(page.locator("#camera-mode")).toHaveValue("none");
  await expect(page.locator("#camera-help")).toContainText("Non-visual input");
  await page.locator("#camera-mode").selectOption("external");
  await expect
    .poll(() => requests.resets.at(-1)?.camera_views)
    .toEqual(["external"]);
  expect(requests.resets.at(-1).observation_mode).toBe("privileged");
  await page.locator('[data-tab="vision"]').click();
  await expect(page.locator("#vision-image")).toBeVisible();
  await expect(page.locator("#vision-source-label")).toContainText(
    "Do not send model",
  );
  await expect(page.locator("#vision-visibility")).toHaveText("Preview only");
  await expect(page.locator('[data-vision-view="external"]')).toBeVisible();
  await expect(page.locator('[data-vision-view="wrist"]')).toBeHidden();
  await page.locator("#observation-mode").selectOption("rgbd");
  await expect
    .poll(() => requests.resets.at(-1)?.observation_mode)
    .toBe("rgbd");
  expect(requests.resets.at(-1).camera_views).toEqual(["external"]);
  await page.locator("#camera-mode").selectOption("wrist");
  await expect(page.locator("#vision-image")).toHaveAttribute(
    "src",
    /view=wrist/,
  );
  await expect(page.locator('[data-vision-view="external"]')).toBeHidden();
  await expect(page.locator('[data-vision-view="wrist"]')).toBeVisible();
  expect(requests.resets.at(-1).camera_views).toEqual(["wrist"]);
  await page.locator("#reset").click();
  await expect(page.locator("#reset")).toBeEnabled();
  await expect(page.locator("#camera-mode")).toHaveValue("wrist");
  expect(requests.resets.at(-1).camera_views).toEqual(["wrist"]);
  await page.locator("#camera-mode").selectOption("both");
  await expect(page.locator('[data-vision-view="external"]')).toBeVisible();
  await expect(page.locator('[data-vision-view="wrist"]')).toBeVisible();
  expect(requests.resets.at(-1).camera_views).toEqual(["external", "wrist"]);
  const resetCount = requests.resets.length;
  await page.locator('[data-vision-view="external"]').click();
  await expect(page.locator("#vision-image")).toHaveAttribute(
    "src",
    /view=external/,
  );
  expect(requests.resets).toHaveLength(resetCount);
  snapshot.status = "running";
  await expect(page.locator("#camera-mode")).toBeDisabled();
  snapshot.status = "idle";
  await expect(page.locator("#camera-mode")).toBeEnabled();
  await page.locator("#camera-mode").selectOption("none");
  await expect(page.locator("#observation-mode")).toHaveValue("privileged");
  await expect.poll(() => requests.resets.at(-1)?.camera_views).toEqual([]);
  await expect(page.locator("#camera-help")).toContainText("No camera");
  await expect(page.locator("#observation-source")).toContainText("Non-visual input");
  await expect(page.locator("#vision-image")).toHaveCount(0);
  await expect(page.locator('[data-vision-view="external"]')).toBeHidden();
  await expect(page.locator('[data-vision-view="wrist"]')).toBeHidden();
  await page.locator("#control-mode").selectOption("incremental");
  await page.locator("#provider").selectOption("chat");
  await page.locator("#observation-mode").selectOption("vision");
  await expect(page.locator("#camera-mode")).toHaveValue("both");
  await expect
    .poll(() => requests.resets.at(-1)?.observation_mode)
    .toBe("vision");
  expect(requests.resets.at(-1).camera_views).toEqual(["external", "wrist"]);
});

test("mocked comparison forwards the camera subset and marks no-camera runs as nonvisual", async ({
  page,
}) => {
  const { requests } = await planningFixture(page);
  await boot(page);
  await page.locator("#comparison-open").click();
  await expect(page.locator("#cmp-start")).toBeEnabled();
  await page.locator(".comparison-advanced > summary").click();
  await expect(page.locator("#cmp-camera-mode")).toHaveValue("none");
  await page.locator("#cmp-observation-mode").selectOption("rgbd");
  await expect(page.locator("#cmp-camera-mode")).toHaveValue("both");
  await page.locator("#cmp-camera-mode").selectOption("wrist");
  await page.locator("#cmp-start").click();
  await expect(page.locator(".comparison-card")).toHaveCount(2);
  expect(requests.comparisons[0]).toMatchObject({
    camera_views: ["wrist"],
    observation_mode: "rgbd",
  });
  await page.locator("#cmp-setup > summary").click();
  await expect(page.locator("#cmp-camera-mode")).toHaveValue("wrist");
  await page.locator("#cmp-camera-mode").selectOption("none");
  await expect(page.locator("#cmp-observation-mode")).toHaveValue("privileged");
  await expect(page.locator("#cmp-camera-help")).toContainText("Non-visual input");
  await page.locator("#cmp-start").click();
  await expect.poll(() => requests.comparisons.length).toBe(2);
  expect(requests.comparisons[1]).toMatchObject({
    camera_views: [],
    observation_mode: "privileged",
  });
  await expect(page.locator(".lane-input-source").first()).toContainText(
    "Non-visual input",
  );
});

test("mocked archive server errors remain visible and cannot masquerade as successful downloads", async ({
  page,
}) => {
  const { snapshot, metadata, archive, requests } = await planningFixture(page);
  Object.assign(snapshot, {
    provider: "chat",
    control_mode: "incremental",
    observation_mode: "vision",
    camera_views: ["external"],
    perception: { ...metadata, camera_views: ["external"] },
  });
  archive.status = 409;
  const downloads = [];
  page.on("download", (download) => downloads.push(download));
  await boot(page);
  await page.locator('[data-tab="vision"]').click();
  await expect(page.locator("#vision-export")).toBeEnabled();
  await page.locator("#vision-export").click();
  await expect(page.locator("#toast")).toHaveText("The experiment has been updated; please retry the export.");
  expect(requests.exports).toHaveLength(1);
  expect(downloads).toHaveLength(0);
  await expect(page.locator("#vision-export")).toBeEnabled();
});
