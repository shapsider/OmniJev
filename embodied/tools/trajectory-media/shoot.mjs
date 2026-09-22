/**
 * Drive the render page in headless Chrome and dump one PNG per trajectory frame.
 *
 * Examples:
 *   # probe four frames with a candidate camera
 *   node shoot.mjs --data=transfer-omnijev --out=probe --only=0,90,180,282 \
 *                  --cam="-58,26,2.10,0.34,0.02,0.16,36"
 *   # full sequence with a slow camera arc
 *   node shoot.mjs --data=transfer-omnijev --out=frames/transfer \
 *                  --cam="-64,26,2.10,0.34,0.02,0.16,36" --orbit=12
 */
import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";

function arg(name, fallback) {
  const hit = process.argv.find((value) => value.startsWith(`--${name}=`));
  return hit ? hit.split("=")[1] : fallback;
}

const dataset = arg("data", "transfer-omnijev");
const outDir = path.resolve(arg("out", `frames/${dataset}`));
const scale = Number(arg("scale", 2));
const step = Number(arg("step", 1));
const port = arg("port", "5199");
const only = arg("only", "");
const base = arg("base", `./data/${dataset}/`);
const orbit = Number(arg("orbit", 0));

/* az,el,dist,lookX,lookY,lookZ,fov */
const cam = (arg("cam", "") || "").split(",").map(Number);
const baseCamera = cam.length === 7 && cam.every((value) => !Number.isNaN(value))
  ? { azimuth: cam[0], elevation: cam[1], distance: cam[2], look: cam.slice(3, 6), fov: cam[6] }
  : {};

const url = `http://127.0.0.1:${port}/?data=${encodeURIComponent(dataset)}&base=${encodeURIComponent(base)}`;
await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  deviceScaleFactor: scale,
});
const page = await context.newPage();
page.on("pageerror", (error) => console.error("[pageerror]", error.message));

await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction("window.__ready === true", null, { timeout: 120000 });

const total = await page.evaluate("window.__omnijev.frameCount");
const meta = await page.evaluate("window.__omnijev.meta");
console.log(`frames=${total} task=${meta.task_name} success=${meta.success}`);
if (Object.keys(baseCamera).length) console.log(`camera=${JSON.stringify(baseCamera)}`);

const indices = only
  ? only.split(",").map(Number)
  : Array.from({ length: Math.ceil(total / step) }, (_, k) => k * step).filter((i) => i < total);

const started = Date.now();
for (const [position, index] of indices.entries()) {
  const progress = total > 1 ? index / (total - 1) : 0;
  const camera = { ...baseCamera };
  if (orbit && camera.azimuth !== undefined) {
    camera.azimuth = camera.azimuth + orbit * (progress - 0.5);
  }
  await page.evaluate(
    ([i, cam]) => window.__omnijev.render(i, cam),
    [index, camera],
  );
  await page.screenshot({
    path: path.join(outDir, `${String(position).padStart(4, "0")}.png`),
  });
  if (position % 50 === 0) console.log(`  ${position}/${indices.length}`);
}

console.log(`wrote ${indices.length} frames to ${outDir} in ${((Date.now() - started) / 1000).toFixed(1)}s`);
await browser.close();
