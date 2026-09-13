import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const origin = process.env.CS2_TEST_ORIGIN ?? "http://127.0.0.1:3000";
assert(["127.0.0.1", "localhost"].includes(new URL(origin).hostname), "Use an isolated localhost stack.");
assert(process.env.CS2_TEST_PASSWORD, "CS2_TEST_PASSWORD is required for the temporary account.");
const output = process.env.CS2_TEST_OUTPUT ?? "/tmp/cs2-watchlist-check";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
const name = `TEST watchlist ${Date.now()}`;
let ruleId;

async function go(path) {
  await Promise.all([
    page.waitForURL((url) => url.pathname === path),
    page.locator(`.sidebar nav a[href="${path}"]`).click(),
  ]);
  await page.locator("h1").waitFor();
}

async function demo() {
  await page.getByRole("button", { name: "Charger la démo" }).click();
  await page.getByRole("button", { name: "Passer en live" }).waitFor();
}

async function saved() {
  const response = page.waitForResponse((r) =>
    r.url().includes("/api/watchlist") && ["POST", "PUT"].includes(r.request().method()),
  );
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  const value = await response;
  assert(value.ok(), `Save failed: HTTP ${value.status()}`);
  const body = await value.json();
  ruleId = body.id;
  await page.getByText("Règle enregistrée.", { exact: true }).waitFor();
}

try {
  await page.goto(`${origin}/login`);
  await page.locator("input[name=username]").fill(process.env.CS2_TEST_USERNAME ?? "admin");
  await page.locator("input[name=password]").fill(process.env.CS2_TEST_PASSWORD);
  await Promise.all([
    page.waitForURL((url) => url.pathname === "/"),
    page.getByRole("button", { name: "Se connecter", exact: true }).click(),
  ]);
  await demo();
  for (const path of ["/markets", "/settings/integrations", "/scanner"]) await go(path);
  await page.locator("tbody tr").first().waitFor();
  const firstLink = page.locator("tbody a").first();
  await Promise.all([page.waitForURL(/\/items\//), firstLink.click()]);
  await page.locator("h1").waitFor();
  await go("/watchlist");
  await page.getByRole("button", { name: "Nouvelle règle" }).click();
  await page.locator("input[name=name]").fill(name);
  await page.locator("input[name=market_hash_name]").fill("AK-47 | Redline (Field-Tested)");
  await page.locator("input[name=max_price_eur]").fill("25.12345678");
  await page.locator("input[name=max_float]").fill("0.17");
  await page.screenshot({ path: `${output}/watchlist-editor-desktop.png`, fullPage: true });
  await saved();
  await page.locator("tbody tr").first().waitFor();
  assert.equal(await page.locator("tbody tr").count(), 1);
  await page.screenshot({ path: `${output}/watchlist-desktop.png`, fullPage: true });

  await page.reload();
  await page.getByText("Aucune règle enregistrée en mode LIVE.", { exact: true }).waitFor();
  await demo();
  await page.getByRole("article", { name, exact: true }).waitFor();
  await page.getByRole("button", { name: "Correspondances", exact: true }).click();
  await page.locator("tbody tr").first().waitFor();
  assert.equal(await page.locator("tbody tr").count(), 1);

  const viewports = [];
  for (const width of [390, 360]) {
    await page.setViewportSize({ width, height: 844 });
    const dimensions = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, document: document.documentElement.scrollWidth }));
    assert.equal(dimensions.document, dimensions.viewport, `Horizontal overflow at ${width}px`);
    viewports.push(dimensions);
    await page.screenshot({ path: `${output}/watchlist-${width}.png`, fullPage: true });
  }

  await page.getByRole("button", { name: `Modifier ${name}`, exact: true }).click();
  await page.screenshot({ path: `${output}/watchlist-editor-mobile.png`, fullPage: true });
  await page.locator("input[name=max_float]").fill("0");
  await saved();
  await page.getByText("Aucune annonce observée ne correspond à cette règle.", { exact: true }).waitFor();
  await page.getByRole("button", { name: `Modifier ${name}`, exact: true }).click();
  await page.locator("input[name=enabled]").uncheck();
  await saved();
  await page.getByText("Cette règle est en pause.", { exact: true }).waitFor();
  assert(await page.getByRole("button", { name: "Correspondances", exact: true }).isDisabled());
  await page.getByRole("button", { name: `Modifier ${name}`, exact: true }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Supprimer", exact: true }).click();
  await page.getByText("Règle supprimée.", { exact: true }).waitFor();
  await page.getByText("Aucune règle enregistrée en mode DEMO.", { exact: true }).waitFor();
  ruleId = undefined;
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ pages: "dashboard, markets, integrations, scanner, item, watchlist", created: true, persistedAfterReload: true, liveDemoIsolated: true, priceFloatMatch: true, paused: true, deleted: true, viewports, errors }, null, 2));
} finally {
  if (ruleId) await context.request.delete(`${origin}/api/watchlist/${ruleId}?mode=demo`);
  await browser.close();
}
