import { test, expect } from "@playwright/test";

async function canvasStats(page) {
  return page.locator("canvas").evaluate((canvas) => {
    const copy = document.createElement("canvas");
    copy.width = 160;
    copy.height = 100;
    const ctx = copy.getContext("2d");
    ctx.drawImage(canvas, 0, 0, 160, 100);
    const data = ctx.getImageData(0, 0, 160, 100).data;
    let dark = 0,
      red = 0,
      blue = 0,
      checksum = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] < 150 && data[i + 1] < 150 && data[i + 2] < 150) dark++;
      if (data[i] > data[i + 1] * 1.2 && data[i] > data[i + 2] * 1.2) red++;
      if (data[i + 2] > data[i] * 1.15) blue++;
      checksum = (checksum + data[i] * (i + 1) + data[i + 1]) % 1000000007;
    }
    return { dark, red, blue, checksum };
  });
}

async function openScene(page) {
  await page.goto("/");
  await expect(page.locator("#loading")).toHaveClass(/hidden/, {
    timeout: 30000,
  });
  await expect(page.locator("#connection")).toContainText("Connected");
  await expect
    .poll(async () => (await canvasStats(page)).dark, { timeout: 15000 })
    .toBeGreaterThan(20);
}

test("desktop physical run, controls, replay and export", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 960 });
  await openScene(page);
  const initial = await canvasStats(page);
  expect(initial.red).toBeGreaterThan(1);
  expect(initial.blue).toBeGreaterThan(10);
  await page.screenshot({ path: testInfo.outputPath("workbench-desktop.png") });
  await page.locator("#camera-top").click();
  await expect
    .poll(async () => (await canvasStats(page)).checksum, { timeout: 15000 })
    .not.toBe(initial.checksum);
  await page.locator("#camera-home").click();
  const canvas = await page.locator("canvas").boundingBox();
  await page.mouse.move(
    canvas.x + canvas.width / 2,
    canvas.y + canvas.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    canvas.x + canvas.width / 2 + 60,
    canvas.y + canvas.height / 2,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => (await canvasStats(page)).checksum, { timeout: 15000 })
    .not.toBe(initial.checksum);
  await page.locator("#camera-home").click();
  await page.locator("#step").click();
  await expect(page.locator("#status-text")).toHaveText("Paused", {
    timeout: 30000,
  });
  await expect(page.locator("#run-budget")).toContainText("01 /");
  await page.locator("#history-list > summary").click();
  await page.locator('#events [data-cycle="1"]').click();
  await expect(page.locator("#decision-heading")).toHaveText(
    "History output · Step 1 Step",
  );
  await expect(page.locator("#stage")).toHaveText("History");
  await expect(page.locator("#decision-note")).toContainText(
    "3D scene remains real-time display",
  );
  await page.screenshot({ path: testInfo.outputPath("history-decision.png") });
  await page.locator("#history-observations summary").first().click();
  await expect(page.locator("#history-before")).toContainText('"tcp"');
  await page.locator("#history-observations summary").nth(1).click();
  await expect(page.locator("#history-after")).toContainText(
    '"finger_contacts"',
  );
  await page.locator("#history-observations summary").nth(2).click();
  await expect(page.locator("#history-payload")).toContainText('"candidates"');
  await page.locator("#decision-live").click();
  await expect(page.locator("#decision-heading")).toHaveText("Action output");
  await expect(page.locator("#history-observations")).toBeHidden();
  const stepped = await canvasStats(page);
  expect(stepped.checksum).not.toBe(initial.checksum);
  await page.locator("#run").click();
  await expect(page.locator("#status-text")).toHaveText("Running");
  await page.locator("#run").click();
  await expect(page.locator("#status-text")).toHaveText("Paused");
  await page.locator("#run").click();
  await expect(page.locator("#status-text")).toHaveText("Verification passed", {
    timeout: 60000,
  });
  await expect(page.locator("#support")).toHaveText("YES");
  await expect(page.locator("#model-calls")).toHaveText("Call 0 Times");
  await page.screenshot({ path: testInfo.outputPath("completed.png") });
  await page.locator("#replay-play").click();
  await expect(page.locator("#status-text")).toHaveText("Trajectory replay");
  const first = await page.locator("#timeline").inputValue();
  await expect
    .poll(() => page.locator("#timeline").inputValue())
    .not.toBe(first);
  await page.locator("#live").click();
  await expect(page.locator("#status-text")).toHaveText("Verification passed");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("#export").click(),
  ]);
  expect(download.suggestedFilename()).toContain(".json");
  await page.locator('[data-task="barrier"]').click();
  await expect(page.locator("#scene-task")).toHaveText("BARRIER");
  await expect(page.locator("#status-text")).toHaveText("Standby");
  await page.locator("#run").click();
  await expect(page.locator("#status-text")).toHaveText("Running");
  await page.locator("#stop").click();
  await expect(page.locator("#status-text")).toHaveText("Stopped");
  expect(errors).toEqual([]);
});

test("mobile layout, scene and settings drawer", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openScene(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const stats = await canvasStats(page);
  expect(stats.red).toBeGreaterThan(1);
  expect(stats.blue).toBeGreaterThan(10);
  await page.screenshot({
    path: testInfo.outputPath("workbench-mobile.png"),
    fullPage: true,
  });
  await page.locator("#decision-open").click();
  await expect(page.locator("#decision-section")).toBeInViewport();
  await expect(page.locator("#decision-section")).toBeFocused();
  await page.locator("#settings-open").click();
  await expect(page.locator("#sidebar")).toBeVisible();
  await page.locator('[data-task="stack"]').click();
  await page.locator("#settings-close").click();
  await expect(page.locator("#scene-task")).toHaveText("STACK");
  await page.locator('[data-tab="data"]').click();
  await expect(page.locator("#raw-state")).toBeVisible();
  await page.locator('[data-tab="scene"]').click();
  await expect(page.locator("canvas")).toBeVisible();
});

test("model connection form works on desktop and mobile without exposing keys", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await openScene(page);
  await page.locator("#model-connect").click();
  await expect(page.locator("#connection-dialog")).toBeVisible();
  await page.locator("#api-url").fill("https://example.invalid/v1");
  await page.locator("#api-model").fill("example/model");
  await page.locator("#api-key").fill("test-ui-secret");
  await page.screenshot({ path: testInfo.outputPath("model-connection.png") });
  await page.locator("#connection-save").click();
  await expect(page.locator("#connection-dialog")).not.toBeVisible();
  await expect(page.locator("#provider")).toHaveValue("chat");
  await expect(page.locator("#threshold")).toBeDisabled();
  await expect(page.locator("#api-key")).toHaveValue("");
  await expect(page.locator("#provider-note")).toContainText("Configured · Not verified");
  const configured = await (await page.request.get("/api/state")).json();
  let inferenceRequests = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/(decision\/probe|connections\/.+\/test|control\/(start|step))/.test(
        request.url(),
      )
    )
      inferenceRequests++;
  });
  await page.reload();
  await expect(page.locator("#loading")).toHaveClass(/hidden/);
  await expect(page.locator("#provider")).toHaveValue("chat");
  expect((await (await page.request.get("/api/state")).json()).id).toBe(
    configured.id,
  );
  expect(inferenceRequests).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#settings-open").click();
  await page.locator("#model-connect").click();
  await expect(page.locator("#connection-dialog")).toBeVisible();
  await expect(page.locator("#key-state")).toHaveText("Configured");
  await expect(page.locator("#api-key")).toHaveValue("");
  await expect(page.locator("#connection-storage")).toContainText(
    "refreshing page will not lose data",
  );
  const box = await page.locator("#connection-dialog").boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  await expect(page.locator("#verification-label")).toContainText(
    "Configured · Not verified",
  );
  await page.screenshot({
    path: testInfo.outputPath("model-connection-mobile.png"),
  });
  await page.locator("#connection-close").click();
});

test("official Jev preset links to key signup and preserves the resolved model", async ({
  page,
}) => {
  await openScene(page);
  await page.locator("#model-connect").click();
  await page.locator("#api-provider").selectOption("jev");
  await expect(page.locator("#api-url")).toHaveValue(
    "https://api.typesafe.ai/v1/systemone",
  );
  await expect(page.locator("#api-url")).toHaveAttribute("readonly", "");
  await expect(page.locator("#api-model")).toHaveValue("jev-latest");
  await expect(page.locator("#typesafe-links")).toBeVisible();
  await expect(page.locator("#typesafe-links a").first()).toHaveAttribute(
    "href",
    "https://console.typesafe.ai",
  );
  await expect(page.locator("#json-mode-row")).toBeHidden();
  // Stub only this test call; saving still exercises the local backend.
  await page.route("**/api/connections/jev/test", (route) =>
    route.fulfill({
      json: { ok: true, model: "jev-1.13.0", latency_ms: 123 },
    }),
  );
  await page.locator("#api-key").fill("test-typesafe-secret");
  await page.locator("#connection-test").click();
  await expect(page.locator("#connection-result")).toContainText("jev-1.13.0");
  await expect(page.locator("#api-key")).toHaveValue("");
  await expect(page.locator("#provider")).toHaveValue("jev");
  await expect(page.locator("#threshold")).toBeEnabled();
  const state = await page.request.get("/api/state");
  expect((await state.json()).cycles).toBe(0);
  await page.locator("#api-provider").selectOption("chat");
  await expect(page.locator("#typesafe-links")).toBeHidden();
  await page.locator("#connection-close").click();
});

test("Claude native configuration is separate and does not expose credentials", async ({
  page,
}) => {
  await openScene(page);
  await page.locator("#model-connect").click();
  await page.locator("#api-provider").selectOption("claude");
  await expect(page.locator("#api-url")).toHaveValue(
    "https://api.anthropic.com/v1",
  );
  await expect(page.locator("#json-mode-row")).toBeHidden();
  await page.locator("#api-model").fill("claude-test");
  await page.locator("#api-key").fill("test-claude-secret");
  await page.locator("#connection-save").click();
  await expect(page.locator("#provider")).toHaveValue("claude");
  await expect(page.locator("#threshold")).toBeDisabled();
  await expect(page.locator("#provider-note")).toContainText("Claude API");
  await page.locator("#model-connect").click();
  await expect(page.locator("#api-provider")).toHaveValue("claude");
  await expect(page.locator("#api-key")).toHaveValue("");
  await expect(page.locator("#key-state")).toHaveText("Configured");
  await page.locator("#connection-close").click();
});

test("pending inference retains the previous result and history stays separate from live decisions", async ({
  page,
}) => {
  await page.request.post("/api/reset", {
    data: { task: "transfer", provider: "baseline" },
  });
  const initial = await (await page.request.get("/api/state")).json();
  const intent = {
    choice: "approach",
    probabilities: { approach: 0.82, descend: 0.18 },
    model_call: true,
    latency_ms: 420,
  };
  const decision = {
    choice: "direct",
    probabilities: { direct: 0.73, hold: 0.27 },
    model_call: true,
    latency_ms: 310,
  };
  const candidates = [
    { id: "direct", label: "Normal execution", admitted: true },
    { id: "hold", label: "Remain stationary", admitted: true },
  ];
  const first = {
    cycle: 1,
    phase: "approach",
    label: "Normal execution",
    intent,
    decision,
    candidates,
    action: candidates[0],
    decision_inputs: {
      phase: {
        state: { fixture: "compact-phase-input" },
        decision: {
          instructions: "Choose phase",
          criteria: { approach: "Approach object" },
        },
      },
      action: null,
    },
    before: initial.frame.observation,
    after: initial.frame.observation,
  };
  let snapshot = {
    ...initial,
    status: "paused",
    stage: "observing",
    phase: "approach",
    cycles: 1,
    last_intent: intent,
    last_decision: decision,
    candidates,
    history: [first],
  };
  await page.route("**/api/state", (route) =>
    route.fulfill({ json: snapshot }),
  );
  await openScene(page);
  await expect(page.locator("#probabilities")).toContainText("73.0%");
  snapshot = {
    ...snapshot,
    status: "running",
    stage: "deciding",
    last_intent: null,
    last_decision: null,
    candidates: [],
  };
  await expect(page.locator("#decision-context")).toHaveText(
    "Previous decision · Computing new decision",
  );
  await expect(page.locator("#probabilities")).toContainText("73.0%");
  await expect(page.locator("#intent-probabilities")).toContainText("82.0%");
  snapshot = {
    ...snapshot,
    stage: "executing",
    phase: "descend",
    cycles: 2,
    last_intent: {
      ...intent,
      choice: "descend",
      probabilities: { approach: 0.1, descend: 0.9 },
    },
    last_decision: { ...decision, probabilities: { direct: 0.91, hold: 0.09 } },
    candidates,
  };
  await expect(page.locator("#probabilities")).toContainText("91.0%");
  await page.locator("#history-list > summary").click();
  await page.locator('#events [data-cycle="1"]').click();
  await expect(page.locator("#decision-heading")).toHaveText(
    "History output · Step 1 Step",
  );
  await expect(page.locator("#intent-probabilities .selected")).toContainText(
    "Move above object",
  );
  await expect(page.locator("#probabilities")).toContainText("73.0%");
  await expect(page.locator("#intent-latency")).toHaveText("420 ms");
  await expect(page.locator("#latency")).toHaveText("310 ms");
  await page.locator("#history-inputs-detail summary").click();
  await expect(page.locator("#history-inputs")).toContainText(
    "compact-phase-input",
  );
  snapshot = {
    ...snapshot,
    stage: "observing",
    history: [first, { ...first, cycle: 2, phase: "descend" }],
  };
  await expect(page.locator("#event-count")).toHaveText("2 Step");
  await expect(page.locator("#intent-probabilities .selected")).toContainText(
    "Move above object",
  );
  await page.locator("#decision-live").click();
  await expect(page.locator("#intent-probabilities .selected")).toContainText(
    "Lower to align",
  );
  await expect(page.locator("#probabilities")).toContainText("91.0%");
  snapshot = {
    ...snapshot,
    status: "stalled",
    message: "Continuous actions have no valid changes; please check records and reset.",
    last_decision_inputs: {
      phase: {
        state: { fixture: "actual-failed-step-input" },
        decision: {
          instructions: "Choose next phase",
          criteria: { approach: "Approach" },
        },
      },
      action: null,
    },
    events: [
      {
        time: 12.3,
        event: "stalled",
        level: "warning",
        message: "Continuous actions have no valid changes",
        cycle: 2,
      },
    ],
  };
  await expect(page.locator("#status-text")).toHaveText("Decision stalled");
  await expect(page.locator("#decision-note")).toContainText(
    "Please check records and reset",
  );
  await expect(page.locator("#run")).toBeDisabled();
  await expect(page.locator("#step")).toBeDisabled();
  await expect(page.locator("#reset")).toBeEnabled();
  await page.locator("#live-inputs-detail summary").click();
  await expect(page.locator("#live-inputs")).toContainText(
    "actual-failed-step-input",
  );
  await page.locator("#runtime-log > summary").click();
  await expect(page.locator("#log-entries .warning")).toContainText(
    "Continuous actions have no valid changes",
  );
});

test("connection verification distinguishes saved, passed and failed calls", async ({
  page,
}) => {
  await page.request.post("/api/reset", {
    data: { task: "transfer", provider: "baseline" },
  });
  let verification = { status: "untested" };
  await page.route("**/api/connections", async (route) => {
    const response = await route.fetch();
    if (route.request().method() === "GET") {
      const values = await response.json();
      values.chat.verification = verification;
      return route.fulfill({ response, json: values });
    }
    return route.fulfill({ response });
  });
  let shouldPass = true;
  await page.route("**/api/connections/chat/test", (route) => {
    verification = {
      status: shouldPass ? "passed" : "failed",
      model: "test-resolved-model",
      latency_ms: 89,
      message: shouldPass ? "Test passed" : "Service authentication failed, please check API Key",
    };
    return route.fulfill({
      json: {
        ok: shouldPass,
        model: verification.model,
        latency_ms: 89,
        detail: verification.message,
      },
    });
  });
  await openScene(page);
  await page.locator("#model-connect").click();
  let outboundCalls = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().includes("/api/connections")
    )
      outboundCalls++;
  });
  await page.locator("#api-key").fill("unsaved-placeholder-key");
  await page.locator("#api-official-preset").click();
  await expect(page.locator("#api-url")).toHaveValue(
    "https://api.openai.com/v1",
  );
  await expect(page.locator("#api-model")).toHaveValue("gpt-6-astra");
  await expect(page.locator("#api-key")).toHaveValue("");
  await expect(page.locator("#verification-label")).toHaveText(
    "Draft modified · Not saved or verified",
  );
  expect(outboundCalls).toBe(0);
  await page.locator("#api-url").fill("https://example.invalid/v1");
  await page.locator("#api-model").fill("test-ui-model");
  await page.locator("#api-key").fill("test-ui-verification-secret");
  await page.locator("#connection-save").click();
  await expect(page.locator("#provider-note")).toContainText("Configured · Not verified");
  await page.locator("#model-connect").click();
  await page.locator("#connection-test").click();
  await expect(page.locator("#verification-label")).toContainText(
    "Verified · test-resolved-model · 89 ms",
  );
  await expect(page.locator("#provider-note")).toContainText("Verified");
  await expect(page.locator("#api-key")).toHaveValue("");
  shouldPass = false;
  await page.locator("#connection-test").click();
  await expect(page.locator("#verification-label")).toContainText("Verification failed");
  await expect(page.locator("#connection-result")).toContainText(
    "Service authentication failed",
  );
  await expect(page.locator("#provider-note")).toContainText("Verification failed");
});

test("control buttons send only one command while a request is pending", async ({
  page,
}) => {
  await page.request.post("/api/reset", {
    data: { task: "transfer", provider: "baseline" },
  });
  await openScene(page);
  let requestCount = 0;
  let release;
  const waiting = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/api/control/start", async (route) => {
    requestCount++;
    await waiting;
    const snapshot = await (await page.request.get("/api/state")).json();
    await route.fulfill({ json: snapshot });
  });
  await page.locator("#run").click();
  await expect.poll(() => requestCount).toBe(1);
  await expect(page.locator("#run")).toBeDisabled();
  await expect(page.locator("#step")).toBeDisabled();
  await expect(page.locator("#reset")).toBeDisabled();
  await page
    .locator("#run")
    .evaluate((button) =>
      button.dispatchEvent(new MouseEvent("click", { bubbles: true })),
    );
  expect(requestCount).toBe(1);
  release();
  await expect(page.locator(".controls")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#run")).toBeEnabled();
  expect(requestCount).toBe(1);
});

test("real decision layout adapts continuously from desktop to narrow phones", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.request.post("/api/reset", {
    data: { task: "transfer", provider: "baseline" },
  });
  await page.setViewportSize({ width: 1440, height: 960 });
  await openScene(page);
  await expect(page.locator("#advanced-settings")).not.toHaveAttribute(
    "open",
    "",
  );
  await expect(page.locator("#history-list")).not.toHaveAttribute("open", "");
  await page.locator("#step").click();
  await expect(page.locator("#status-text")).toHaveText("Paused");
  await expect(page.locator("#probabilities .selected")).toHaveCount(1);
  for (const [width, height] of [
    [1440, 960],
    [1024, 768],
    [768, 1024],
    [390, 844],
    [330, 812],
    [1440, 960],
  ]) {
    await page.setViewportSize({ width, height });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await expect
      .poll(() =>
        page.locator("canvas").evaluate((canvas) => {
          const viewport = canvas.parentElement;
          return (
            Math.abs(canvas.clientWidth - viewport.clientWidth) < 1 &&
            Math.abs(canvas.clientHeight - viewport.clientHeight) < 1 &&
            canvas.width > 0 &&
            canvas.height > 0
          );
        }),
      )
      .toBe(true);
    for (const selector of [
      "#input-positions",
      "#probabilities",
      "#intent-probabilities",
    ]) {
      const bounds = await page.locator(selector).boundingBox();
      expect(bounds.x).toBeGreaterThanOrEqual(0);
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
      expect(
        await page
          .locator(selector)
          .evaluate((element) => element.scrollWidth <= element.clientWidth),
      ).toBe(true);
    }
    await page.screenshot({
      path: testInfo.outputPath(`responsive-${width}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 330, height: 812 });
  await page.locator("#reset").click();
  await expect(page.locator("#status-text")).toHaveText("Standby");
  await page.locator("#settings-open").click();
  await page.locator("#model-connect").click();
  await expect(page.locator("#connection-dialog")).toBeVisible();
  const dialog = await page.locator("#connection-dialog").boundingBox();
  expect(dialog.x).toBeGreaterThanOrEqual(0);
  expect(dialog.x + dialog.width).toBeLessThanOrEqual(330);
  expect(
    await page
      .locator("#connection-dialog")
      .evaluate((element) => element.scrollWidth <= element.clientWidth),
  ).toBe(true);
  await page.locator("#connection-close").click();
  await page.locator("#settings-close").click();
  expect(errors).toEqual([]);
});
