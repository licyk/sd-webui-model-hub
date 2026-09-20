"""Connect the generic hub to the WebUI's directories, login and UI lifecycle."""

import logging
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from sd_webui_model_hub import MOUNT_PATH, VERSION
from sd_webui_model_hub.auth import HostAuth
from sd_webui_model_hub.roots import collect_roots
from sd_webui_model_hub.runtime import HubRuntime

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

if TYPE_CHECKING:
    from sd_model_hub.core.context import Services


class Changes:
    """Worker-thread events only invalidate the browser's model list."""

    def __init__(self):
        self.instance = uuid.uuid4().hex
        self.revision = 0
        self.lock = threading.Lock()

    def receive(self, event):
        if event.__event_name__ in {"download_completed", "library_changed"}:
            with self.lock:
                self.revision += 1

    def snapshot(self):
        with self.lock:
            return {"instance": self.instance, "revision": self.revision}


@dataclass
class Resources:
    services: "Services"
    unsubscribe: Callable[[], None]

    def close(self):
        self.unsubscribe()
        self.services.close()


def create_factory(shared, paths, demo, loaded=None):
    loaded = sys.modules if loaded is None else loaded

    def factory():
        from packaging.version import Version
        from sd_model_hub.api.app import create_app
        from sd_model_hub.api.paths import validate_public_base_url
        from sd_model_hub.api.static import web_dist_dir
        from sd_model_hub.core.context import build_services
        from sd_model_hub.version import VERSION as HUB_VERSION

        if Version(HUB_VERSION) < Version("0.1.4"):
            raise RuntimeError(f"sd-model-hub>=0.1.4 required; found {HUB_VERSION}")
        cmd = shared.cmd_opts
        settings = shared.opts.data
        public_url = validate_public_base_url(settings.get("model_hub_public_url") or None)
        bound_host = getattr(cmd, "server_name", None) or ("0.0.0.0" if getattr(cmd, "listen", False) or getattr(cmd, "share", False) else "127.0.0.1")
        port = getattr(demo, "server_port", None) or getattr(cmd, "port", None) or 7860
        extra_hosts = {urlsplit(public_url).hostname} if public_url else set()
        roots = collect_roots(shared, paths, loaded)
        services = build_services(
            data_dir=DATA_DIR,
            settings_path=DATA_DIR / "settings.toml",
            roots_locked=True,
            settings_overrides={
                "paths": {"model_roots": roots.roots},
                "downloads": {"kind_destinations": roots.destinations, "default_root": None},
                "server": {"host": bound_host, "port": port, "access_token": None, "allowed_origins": [], "open_browser": False},
            },
        )
        changes = Changes()
        unsubscribe = services.events.subscribe(changes.receive)
        try:
            app = create_app(services, bound_host=bound_host, bound_port=port, extra_hosts=extra_hosts, public_base_url=public_url)

            async def status(_request):
                state = getattr(shared, "state", None)
                return JSONResponse(
                    {
                        **changes.snapshot(),
                        "extension_version": VERSION,
                        "hub_version": HUB_VERSION,
                        "host": "Forge" if "modules_forge.main_entry" in loaded or "modules_forge.shared" in loaded else "A1111",
                        "roots": roots.roots,
                        "default_library_root": roots.default_library_root,
                        "ui_available": (web_dist_dir() / "index.html").is_file(),
                        "auto_refresh": bool(shared.opts.data.get("model_hub_auto_refresh", True)),
                        "busy": bool(getattr(state, "job_count", 0) > 0 or getattr(state, "job", "")),
                    },
                    headers={"Cache-Control": "no-store"},
                )

            # Precede the library's static-file catch-all; its security middleware also
            # protects this route, including Host validation.
            app.router.routes.insert(0, Route("/_host/status", status, methods=["GET"]))
        except BaseException:
            unsubscribe()
            services.close()
            raise
        return Resources(services, unsubscribe), app

    return factory


def mount_hub(demo, app, shared, paths):
    existing = getattr(app.state, "sd_webui_model_hub", None)
    if existing is not None:
        return existing
    if any(getattr(route, "path", None) == MOUNT_PATH for route in app.routes):
        raise RuntimeError(f"Another application already occupies {MOUNT_PATH}")
    runtime = HubRuntime(create_factory(shared, paths, demo))
    guarded = HostAuth(runtime, app, api_only=demo is None, api_auth=getattr(shared.cmd_opts, "api_auth", None))
    # Insert before any host catch-all route, without changing the host's middleware.
    app.router.routes.insert(0, Mount(MOUNT_PATH, guarded, name="sd-webui-model-hub"))
    app.add_event_handler("shutdown", runtime.shutdown)
    app.state.sd_webui_model_hub = runtime
    return runtime


def on_ui_settings():
    from modules import shared

    section = ("model_hub", "SD Model Hub")
    shared.opts.add_option("model_hub_auto_refresh", shared.OptionInfo(True, "下载完成或本地模型改变后自动刷新 WebUI 模型列表", section=section))
    shared.opts.add_option(
        "model_hub_public_url",
        shared.OptionInfo("", "反向代理外部地址（含 /sd-model-hub，用于 OAuth；修改后重启 WebUI）", section=section),
    )


def on_ui_tabs():
    import gradio as gr

    with gr.Blocks(analytics_enabled=False) as tab:
        gr.HTML(
            """<div id="sd-model-hub-panel">
  <p class="model-hub-status" role="status" aria-live="polite" hidden></p>
  <iframe title="SD Model Hub 模型管理和下载" class="model-hub-frame" hidden></iframe>
</div>"""
        )
    return [(tab, "Model Hub", "sd_model_hub")]
