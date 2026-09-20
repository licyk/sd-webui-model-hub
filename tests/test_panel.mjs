import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const script = readFileSync(new URL("../javascript/model_hub.js", import.meta.url), "utf8");
const settled = () => new Promise((resolve) => setImmediate(resolve));

async function panel() {
    let boot;
    let refreshes = 0;
    let sequence = 0;
    let httpStatus = 200;
    let failure = null;
    const timers = new Map();
    const state = {instance: "server", revision: 0, busy: false, auto_refresh: true, ui_available: true};
    const status = {hidden: true, textContent: ""};
    const frame = {
        hidden: true,
        hasAttribute: (name) => Object.hasOwn(frame, name),
        removeAttribute: (name) => { delete frame[name]; },
    };
    const root = {
        querySelector(selector) {
            if (selector === "#sd-model-hub-panel") return element;
            if (selector === "#forge_refresh_checkpoint") return {
                matches: () => true,
                disabled: false,
                click: () => { refreshes++; },
            };
            return null;
        },
    };
    const element = {
        querySelector(selector) {
            if (selector === ".model-hub-status") return status;
            if (selector === "iframe") return frame;
            throw new Error(`Removed interface element requested: ${selector}`);
        },
    };
    vm.runInNewContext(script, {
        window: {location: {pathname: "/webui/", origin: "https://example.test"}, addEventListener() {}},
        document: root,
        onUiLoaded: (fn) => { boot = fn; },
        URL,
        AbortController,
        setTimeout: (fn, delay) => { const id = ++sequence; timers.set(id, {fn, delay}); return id; },
        clearTimeout: (id) => timers.delete(id),
        fetch: async (url, options) => {
            assert.equal(url.href, "https://example.test/webui/sd-model-hub/_host/status");
            assert.equal(options.credentials, "same-origin");
            if (failure) throw failure;
            return {status: httpStatus, ok: httpStatus === 200, json: async () => ({...state})};
        },
    });
    boot();
    await settled();
    return {
        frame, status, state,
        refreshes: () => refreshes,
        setResponse: (code, error = null) => { httpStatus = code; failure = error; },
        async poll() {
            const [id, timer] = [...timers].find(([, timer]) => timer.delay === 5000);
            timers.delete(id);
            await timer.fn();
        },
    };
}

test("connected panel shows the iframe without connection or folder information", async () => {
    const ui = await panel();
    assert.equal(ui.frame.hidden, false);
    assert.equal(ui.frame.src, "https://example.test/webui/sd-model-hub/");
    assert.equal(ui.status.hidden, true);
    assert.equal(ui.status.textContent, "");
    assert.equal(ui.refreshes(), 0);
});

test("automatic refresh waits silently until generation is idle", async () => {
    const ui = await panel();
    ui.state.revision = 1;
    ui.state.busy = true;
    await ui.poll();
    assert.equal(ui.refreshes(), 0);
    assert.equal(ui.status.hidden, true);
    ui.state.busy = false;
    await ui.poll();
    assert.equal(ui.refreshes(), 1);
    assert.equal(ui.status.hidden, true);
    await ui.poll();
    assert.equal(ui.refreshes(), 1);
    ui.state.auto_refresh = false;
    ui.state.revision = 2;
    await ui.poll();
    assert.equal(ui.refreshes(), 1);
    assert.equal(ui.status.hidden, true);
});

test("expired login hides the iframe and recovery clears the error", async () => {
    const ui = await panel();
    ui.setResponse(401);
    await ui.poll();
    assert.equal(ui.frame.hidden, true);
    assert.equal(ui.frame.hasAttribute("src"), false);
    assert.equal(ui.status.hidden, false);
    assert.match(ui.status.textContent, /登录已失效/);
    ui.setResponse(200);
    await ui.poll();
    assert.equal(ui.frame.hidden, false);
    assert.equal(ui.status.hidden, true);
});

test("missing assets and connection errors remain visible until recovery", async () => {
    const ui = await panel();
    ui.state.ui_available = false;
    await ui.poll();
    assert.equal(ui.frame.hidden, true);
    assert.equal(ui.status.hidden, false);
    assert.match(ui.status.textContent, /缺少前端资源/);
    ui.setResponse(200, new Error("offline"));
    await ui.poll();
    assert.match(ui.status.textContent, /无法连接.*offline/);
    ui.setResponse(200);
    ui.state.ui_available = true;
    await ui.poll();
    assert.equal(ui.frame.hidden, false);
    assert.equal(ui.status.hidden, true);
});
