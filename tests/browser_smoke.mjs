// Optional: PLAYWRIGHT_MODULE may point to an installed playwright-core module.
import assert from "node:assert/strict";
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ["--no-sandbox"],
});
const base = process.env.MODEL_HUB_TEST_URL || "http://127.0.0.1:17863";
const context = await browser.newContext({viewport: {width: 1440, height: 1050}});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
// Model search is provided by the upstream library; browser integration runs offline.
await context.route("**/sd-model-hub/api/v1/sources/*/models**", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null}),
}));

try {
    assert.equal((await context.request.get(`${base}/sd-model-hub/_host/status`)).status(), 401);
    const login = await context.request.post(`${base}/login`, {form: {username: "smoke", password: "smoke"}});
    assert.equal(login.status(), 200);
    await page.goto(base);
    const frame = page.frameLocator(".model-hub-frame");
    await frame.locator("#app").waitFor();
    await frame.locator(".root-path").waitFor();
    assert.match(await frame.locator(".root-path").textContent(), /[/\\]models$/);
    const hostStatus = await (await context.request.get(`${base}/sd-model-hub/_host/status`)).json();
    assert.equal(await page.locator(".model-hub-frame").getAttribute("src"), `${base}/sd-model-hub/#/library?root=${hostStatus.default_library_root}`);
    assert.equal(await page.locator('#sd-model-hub-panel [data-action], .model-hub-toolbar, .model-hub-folders').count(), 0);
    assert.equal(await page.locator(".model-hub-status").isVisible(), false);
    const before = Number(await page.locator("#smoke-counter textarea").inputValue());
    await page.getByRole("button", {name: "Simulate file change", exact: true}).click();
    await page.waitForFunction((old) => Number(document.querySelector("#smoke-counter textarea")?.value) > old, before, {timeout: 15000});
    const idleCount = Number(await page.locator("#smoke-counter textarea").inputValue());
    await page.getByRole("button", {name: "Set busy", exact: true}).click();
    await page.getByRole("button", {name: "Simulate file change", exact: true}).click();
    await page.waitForFunction(async () => (await (await fetch('/sd-model-hub/_host/status')).json()).busy);
    await page.waitForTimeout(5500);
    assert.equal(await page.locator(".model-hub-status").isVisible(), false);
    assert.equal(Number(await page.locator("#smoke-counter textarea").inputValue()), idleCount);
    await page.getByRole("button", {name: "Set idle", exact: true}).click();
    await page.waitForFunction((old) => Number(document.querySelector("#smoke-counter textarea")?.value) > old, idleCount, {timeout: 15000});
    await page.reload();
    await frame.locator("#app").waitFor();
    await frame.locator(".root-path").waitFor();
    assert.match(await frame.locator(".root-path").textContent(), /[/\\]models$/);
    await page.screenshot({path: process.env.MODEL_HUB_SCREENSHOT || "/tmp/sd-webui-model-hub-smoke.png", fullPage: true});
    assert.deepEqual(errors, []);
    await context.clearCookies();
    await page.waitForFunction(() => document.querySelector(".model-hub-status")?.textContent.includes("登录已失效"), null, {timeout: 15000});
    assert.equal(await page.locator(".model-hub-frame").isVisible(), false);
    console.log("PASS: real Gradio login, embedded Vue UI without toolbar, library roots, automatic refresh, busy deferral, page reload, expired session");
} finally {
    await browser.close();
}
