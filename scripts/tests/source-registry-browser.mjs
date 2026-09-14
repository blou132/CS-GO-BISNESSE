import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const origin = process.env.CS2_TEST_ORIGIN ?? "http://127.0.0.1:3000";
assert(["127.0.0.1", "localhost"].includes(new URL(origin).hostname), "Use an isolated localhost stack.");
assert(process.env.CS2_TEST_PASSWORD, "CS2_TEST_PASSWORD is required for the temporary account.");
const output = process.env.CS2_TEST_OUTPUT ?? "/tmp/cs2-source-check";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });

try {
  await page.goto(`${origin}/login`);
  await page.locator("input[name=username]").fill(process.env.CS2_TEST_USERNAME ?? "admin");
  await page.locator("input[name=password]").fill(process.env.CS2_TEST_PASSWORD);
  await Promise.all([
    page.waitForURL((url) => url.pathname === "/"),
    page.getByRole("button", { name: "Se connecter", exact: true }).click(),
  ]);
  const catalogResponse = page.waitForResponse((r) => r.url().endsWith("/api/integrations"));
  await page.locator('.sidebar nav a[href="/settings/integrations"]').click();
  const response = await catalogResponse;
  assert(response.ok(), `Catalog failed: HTTP ${response.status()}`);
  const catalog = await response.json();
  const source = catalog.sources.find((entry) => entry.id === "skinsniper");
  assert.equal(source.source_type, "AGGREGATOR");
  assert.equal(source.api_discovery_status, "API_NOT_FOUND");
  assert.equal(source.access_status, "RESEARCH_REQUIRED");
  assert.equal(source.runtime_status, "not_integrated");
  assert.deepEqual(source.collected_capabilities, []);
  assert(source.roles.includes("MARKET_DISCOVERY_SOURCE"));
  const card = page.locator(".source-card").filter({ has: page.getByRole("heading", { name: "SkinSniper", exact: true }) });
  await card.getByText("Non intégré", { exact: true }).waitFor();
  assert.equal(await card.getByRole("link", { name: "Site officiel", exact: true }).getAttribute("href"), "https://skinsniper.com/");
  for (const name of ["White.Market", "Waxpeer", "HaloSkins", "Skinflow", "BUFF Market"]) {
    await page.getByRole("heading", { name, exact: true }).waitFor();
  }
  const viewports = [];
  for (const width of [1440, 390, 360]) {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
    await card.scrollIntoViewIfNeeded();
    const dimensions = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, document: document.documentElement.scrollWidth }));
    assert.equal(dimensions.document, dimensions.viewport, `Horizontal overflow at ${width}px`);
    const overflow = await page.locator(".source-card").evaluateAll((cards) => cards.filter((item) => item.scrollWidth > item.clientWidth + 1).length);
    assert.equal(overflow, 0, `Source card overflow at ${width}px`);
    await page.screenshot({ path: `${output}/sources-${width}.png` });
    viewports.push(dimensions);
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ registry: "live API contract", sources: catalog.sources.length, skinsniper: "reference only, no collection", viewports, errors }, null, 2));
} finally {
  await browser.close();
}
