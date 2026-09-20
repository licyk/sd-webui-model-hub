"""WebUI callback entry point; optional hub dependencies are loaded lazily."""

import logging

from modules import paths_internal, script_callbacks, shared

from sd_webui_model_hub.host import mount_hub, on_ui_settings, on_ui_tabs

_runtime = None


def on_app_started(demo, app):
    global _runtime
    try:
        _runtime = mount_hub(demo, app, shared, paths_internal)
    except Exception:
        logging.getLogger(__name__).exception("Could not mount SD Model Hub")


def on_unloaded():
    global _runtime
    if _runtime is not None:
        _runtime.unload()
        _runtime = None


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_ui_tabs(on_ui_tabs)
script_callbacks.on_app_started(on_app_started)
script_callbacks.on_script_unloaded(on_unloaded)
