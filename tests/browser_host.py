"""Optional browser fixture: real Gradio, temporary models, no Stable Diffusion imports.

Run with the host's Gradio installed and a built sd-model-hub dist directory.
The only login is smoke / smoke; this fixture binds exclusively to localhost.
"""

import argparse
import time
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
from sd_model_hub.api import app as hub_app
from sd_model_hub.api import static
from sd_model_hub.core.events.models import LibraryChangedEvent

from sd_webui_model_hub import host as host_module
from sd_webui_model_hub.host import mount_hub, on_ui_tabs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17863)
    args = parser.parse_args()
    host_module.DATA_DIR = args.data_dir / "extension" / "data"
    static.web_dist_dir = lambda: args.dist
    hub_app.web_dist_dir = lambda: args.dist
    root = Path(__file__).resolve().parents[1]
    shared = SimpleNamespace(
        cmd_opts=SimpleNamespace(lora_dir=str(args.data_dir / "loras"), embeddings_dir=str(args.data_dir / "embeddings")),
        opts=SimpleNamespace(data={}),
        state=SimpleNamespace(job_count=0, job=""),
        sd_upscalers=[],
    )
    paths = SimpleNamespace(models_path=str(args.data_dir / "models"), data_path=str(args.data_dir / "data"))
    for path in (args.data_dir / "loras", args.data_dir / "models" / "Stable-diffusion", args.data_dir / "models" / "VAE", args.data_dir / "embeddings"):
        path.mkdir(parents=True, exist_ok=True)
    hooks = """
window.gradioApp = () => document.querySelector('gradio-app')?.shadowRoot || document;
const callbacks = [];
window.onUiLoaded = window.onUiUpdate = (callback) => callbacks.push(callback);
function observe() {
    new MutationObserver(() => callbacks.forEach((callback) => callback())).observe(document.body, {subtree: true, childList: true});
    callbacks.forEach((callback) => callback());
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', observe);
else setTimeout(observe, 0);
"""
    head = "<script>" + hooks + (root / "javascript/model_hub.js").read_text() + "</script>"
    count = 0
    runtime = None

    def refresh():
        nonlocal count
        count += 1
        return str(count)

    def change():
        services = runtime.services.services
        services.events.publish(LibraryChangedEvent(root_id=services.library.list_roots()[0].id))

    hub_tab = on_ui_tabs()[0][0]
    with gr.Blocks(head=head, css=(root / "style.css").read_text(), analytics_enabled=False) as demo:
        with gr.Tab("Model Hub"):
            hub_tab.render()
        counter = gr.Textbox("0", label="Refresh count", elem_id="smoke-counter")
        gr.Button("Checkpoint refresh", elem_id="forge_refresh_checkpoint").click(refresh, outputs=counter)
        gr.Button("Simulate file change").click(change)
        gr.Button("Set busy").click(lambda: setattr(shared.state, "job_count", 1))
        gr.Button("Set idle").click(lambda: setattr(shared.state, "job_count", 0))
    app, _, _ = demo.launch(server_name="127.0.0.1", server_port=args.port, auth=("smoke", "smoke"), prevent_thread_lock=True)
    runtime = mount_hub(demo, app, shared, paths)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        demo.close()
        runtime.unload()
        assert runtime.task is None or runtime.task.done()
        print("Model Hub lifespan stopped", flush=True)


if __name__ == "__main__":
    main()
