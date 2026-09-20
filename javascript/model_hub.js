/* global gradioApp, onUiLoaded, onUiUpdate */
(() => {
    "use strict";
    let currentPanel = null;
    let dispose = () => {};

    function boot() {
        const root = typeof gradioApp === "function" ? gradioApp() : document;
        const panel = root.querySelector("#sd-model-hub-panel");
        if (!panel || panel === currentPanel) return;
        dispose();
        currentPanel = panel;
        const status = panel.querySelector(".model-hub-status");
        const frame = panel.querySelector("iframe");
        const base = new URL(window.location.pathname.replace(/\/?$/, "/") + "sd-model-hub/", window.location.origin);
        let stopped = false;
        let timer;
        let latest = null;
        let refreshed = null;
        let inFlight = false;
        const message = (text = "") => {
            status.textContent = text;
            status.hidden = !text;
        };

        function clickFirst(selectors) {
            for (const selector of selectors) {
                const element = root.querySelector(selector);
                const button = element?.matches("button") ? element : element?.querySelector("button");
                if (button && !button.disabled) {
                    button.click();
                    return;
                }
            }
        }

        function refresh() {
            if (!latest || latest.busy) return;
            clickFirst(["#forge_refresh_checkpoint", "#refresh_sd_model_checkpoint"]);
            clickFirst(["#refresh_sd_vae"]);
            for (const tab of ["txt2img", "img2img"]) {
                // One extra-network refresh refreshes all pages in that tab.
                clickFirst([`[id^="${tab}_"][id$="_extra_refresh_internal"]`]);
                clickFirst([`#${tab}_controlnet_refresh_models`]);
            }
            refreshed = `${latest.instance}:${latest.revision}`;
        }

        async function poll() {
            if (stopped || inFlight) return;
            inFlight = true;
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 20000);
            try {
                const response = await fetch(new URL("_host/status", base), {credentials: "same-origin", cache: "no-store", signal: controller.signal});
                if (stopped) return;
                if (response.status === 401) {
                    frame.hidden = true;
                    frame.removeAttribute("src");
                    message("WebUI 登录已失效，请刷新整个页面并重新登录。");
                    return;
                }
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                latest = await response.json();
                if (stopped) return;
                const key = `${latest.instance}:${latest.revision}`;
                if (!latest.ui_available) {
                    frame.hidden = true;
                    message("sd-model-hub 缺少前端资源，请安装包含 webui/dist 的发行包；源码安装需先构建前端。");
                    return;
                }
                if (!frame.hasAttribute("src")) {
                    frame.src = base.href;
                }
                frame.hidden = false;
                message();
                // Catch downloads completed before this browser connected as well.
                if (refreshed === null && latest.revision === 0) refreshed = key;
                if (latest.auto_refresh && refreshed !== key) refresh();
            } catch (error) {
                if (!stopped) message(`无法连接 SD Model Hub（${error.message}），正在重试；启动错误请查看 WebUI 控制台。`);
            } finally {
                clearTimeout(timeout);
                inFlight = false;
                if (!stopped) timer = setTimeout(poll, 5000);
            }
        }

        dispose = () => { stopped = true; clearTimeout(timer); };
        poll();
    }

    if (typeof onUiLoaded === "function") onUiLoaded(boot);
    if (typeof onUiUpdate === "function") onUiUpdate(boot);
    window.addEventListener("pagehide", () => dispose());
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) { currentPanel = null; boot(); }
    });
})();
