import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const origin = process.env.CS2_TEST_ORIGIN ?? "http://127.0.0.1:3000";
assert(["127.0.0.1", "localhost"].includes(new URL(origin).hostname));
assert(process.env.CS2_TEST_PASSWORD);
const output = process.env.CS2_TEST_OUTPUT ?? "/tmp/cs2-realtime-check";
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", error => errors.push(error.message));
page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
const views = [];

async function capture(label, region) {
  for (const width of [1440, 390, 360]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    await region.scrollIntoViewIfNeeded();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${label} overflow ${width}`);
    const overflow = await page.locator(".stream-metrics > div").evaluateAll(rows => rows.some(row => row.scrollWidth > row.clientWidth + 1));
    assert.equal(overflow, false);
    await page.screenshot({ path: `${output}/${label}-${width}.png` });
    views.push({ label, width });
  }
}

try {
  await page.goto(`${origin}/login`);
  await page.locator("input[name=username]").fill(process.env.CS2_TEST_USERNAME ?? "admin");
  await page.locator("input[name=password]").fill(process.env.CS2_TEST_PASSWORD);
  await Promise.all([page.waitForURL(url => url.pathname === "/"), page.getByRole("button", { name: "Se connecter", exact: true }).click()]);
  await page.locator('.sidebar nav a[href="/markets"]').click();
  const stream = page.getByRole("region", { name: "Skinport temps réel", exact: true });
  await stream.getByText("Désactivé", { exact: true }).waitFor();
  await capture("realtime-disabled", stream);
  // Browser-only fixture: the real isolated API remains disabled and has no upstream session.
  let polls = 0;
  await page.route("**/api/market-monitor", async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.realtime.skinport = { ...data.realtime.skinport, enabled: true, status: "disconnected", http_status: 403, last_error: "connection_failed", reconnect_count: 1, dropped_events: 2 };
    polls += 1;
    await route.fulfill({ response, json: data });
  });
  await stream.getByText("Déconnecté", { exact: true }).waitFor({ timeout: 12000 });
  await stream.getByText("connection_failed (HTTP 403)", { exact: true }).waitFor();
  assert(polls >= 1, "Monitor must refresh without a reload");
  await capture("realtime-refused-fixture", stream);
  await page.unroute("**/api/market-monitor");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Charger la démo" }).click();
  await page.getByRole("button", { name: "Passer en live" }).waitFor();
  await page.locator('.sidebar nav a[href="/scanner"]').click();
  await page.locator("tbody a").first().click();
  const provenance = page.getByRole("region", { name: "Provenance de la valorisation", exact: true });
  await provenance.getByText("Simulation DEMO", { exact: true }).waitFor();
  await provenance.getByRole("cell", { name: /^Référence retenue/ }).first().waitFor();
  await provenance.getByText("Synthétiques, 10 % en DEMO", { exact: true }).waitFor();
  await capture("valuation-provenance-demo", provenance);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ transport: "disabled API + explicitly injected 403 browser fixture", provenance: "real isolated API, DEMO-labelled data", polls, views, errors }, null, 2));
} finally {
  await browser.close();
}
