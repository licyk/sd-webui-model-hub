# SD WebUI Model Hub

English | [简体中文](README_zh-CN.md)

A model management and download extension for Stable Diffusion WebUI (A1111) and Forge, powered by sd-model-hub.

The extension embeds the native sd-model-hub interface in the **Model Hub** tab. It supports searching model sources, downloading from direct links and Hugging Face / ModelScope repositories, managing download queues, and browsing, identifying, moving, renaming, and deleting local models. Available model sources and download capabilities are provided by sd-model-hub.

## Installation

Requires Python 3.10 or newer.

### Option 1: Install through WebUI

1. Open **Extensions → Install from URL** in WebUI.
2. Enter `https://github.com/licyk/sd-webui-model-hub.git` and click **Install**.
3. Fully restart WebUI. Dependencies will be installed automatically, and the **Model Hub** tab will become available.

### Option 2: Install from the command line

Open a terminal in the WebUI root directory (the directory containing the `extensions` folder) and run:

```bash
git clone https://github.com/licyk/sd-webui-model-hub.git extensions/sd-webui-model-hub
```

Start or fully restart WebUI after installation. Dependencies will be installed automatically, and the **Model Hub** tab will become available.

## Usage

1. Open the **Model Hub** tab. It opens the local library at **All model directories** by default; switch to a category directory when needed.
2. Search for models, select repository files, or enter a download URL in the embedded interface. Recognized model types suggest a matching destination; choose a directory manually for unrecognized files downloaded from direct links.
3. By default, WebUI model lists refresh automatically after downloads finish or local models change. Refreshes wait until any active generation task finishes.

Refreshes use the host's existing Gradio buttons for Checkpoints, VAEs, Extra Networks, and available ControlNet controls. Each browser page receives updates independently. Downloaded models are not selected or loaded automatically. Components without a matching refresh control, and some upscalers, require a manual refresh or a WebUI restart.

The tab displays the Model Hub interface directly, without an extra toolbar, connection success message, or model directory paths. Error messages appear only when the connection fails, authentication expires, or frontend assets are missing.
Opening the native interface separately also uses WebUI authentication. Keep a WebUI page open to receive automatic updates to the host's model lists.

## Model directories

The extension reads the host's runtime configuration instead of assuming that all models live in the default `models` folder.

The local library's root selector includes **All model directories**, which points to the host's actual `models_path`.
Reloading the extension interface always opens this directory, regardless of the previously selected category. After opening it, manually selected directories are not reset by background polling.
Portable installations use the redirected model directory. This entry lets you browse all its subdirectories, including unregistered custom categories.
Existing category entries and download destinations remain available. Custom model paths outside this root are still accessible through their own entries.

| Model type | Directory source |
| --- | --- |
| Checkpoint | `sd_models.model_path` and `--ckpt-dir`; the custom directory takes priority for downloads |
| VAE | Default VAE directory and `--vae-dir` |
| LoRA / LyCORIS | `--lora-dir`, `--lyco-dir-backcompat` |
| Embedding / Hypernetwork | `--embeddings-dir`, `--hypernetwork-dir` |
| Forge diffusion model | Uses the Checkpoint download directory |
| Forge text encoder | `models/text_encoder` and `--text-encoder-dir` |
| ControlNet | Directories from loaded ControlNet / Forge modules, launch arguments, and additional directory settings |
| Forge preprocessor | Forge's actual preprocessor directory |
| Upscaler | Model directories of registered upscalers and custom directories |

Duplicate directories, including symbolic links to the same location, are merged. Directory IDs remain stable across restarts. The host manages the directory list, which is locked in Model Hub; fully restart WebUI after changing launch arguments or directory settings. Type hints do not override sd-model-hub's file identification results. Registering a directory does not mean the host can load every model architecture.

Extension data is stored in `data/` inside the extension directory, including `settings.toml`, the database, download history, and caches. This directory is excluded by `.gitignore`. Model files are saved directly to the model directories above. WebUI model sidecar metadata can be enabled in sd-model-hub's download settings.

## Settings and deployment

WebUI **Settings → SD Model Hub** provides:

- Automatic refresh of WebUI model lists after downloads finish or models change.
- An external reverse proxy URL for OAuth, such as `https://example.com/webui/sd-model-hub`. It must include both the WebUI subpath and the extension path. Fully restart WebUI after changing it. OAuth client settings are still configured in sd-model-hub.

The service runs under `/sd-model-hub/` on WebUI's existing HTTP server; it does not start a second HTTP server. When WebUI uses a subpath, the browser URL is `<WebUI subpath>/sd-model-hub/`. Reverse proxies must forward both HTTP and WebSocket traffic under this path.

When Gradio login is enabled, the entire extension, including static pages, APIs, and WebSockets, validates the host session. Both Gradio 3 and 4 cookie formats are supported. No separate sd-model-hub token is required. API-only mode uses HTTP Basic authentication from `--api-auth`. The regular graphical interface uses Gradio login; `--api-auth` does not replace authentication for the graphical interface.

The extension grants the same file operation permissions as local model management and is intended for trusted WebUI users. Locked model roots control host directory configuration; they are not a filesystem sandbox. sd-model-hub itself allows explicit download paths and local imports.

## Development and validation

`scripts/model_hub_setup.py` registers WebUI callbacks, `sd_webui_model_hub/` adapts the host, and `javascript/model_hub.js` handles the iframe and refresh controls. The extension does not modify host or sd-model-hub source files.

After installing development dependencies, run these checks in an environment that can import sd-model-hub:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
node --check javascript/model_hub.js
node --test tests/test_panel.mjs
```

Tests cover directory mapping, both Gradio session formats, API-only authentication, mount subpaths, Socket.IO, real download workers, host change notifications, the minimal embedded interface, and lifecycle cleanup. They use temporary directories and simulated HTTP model sources without reading or downloading real model weights.

The sub-application starts in WebUI's current event loop on the first authenticated request. Cleanup handles normal host shutdown, server event loop exit, and script unloading, including Forge's behavior of calling `on_app_started` after the server starts.

Optional browser checks require Gradio 4, Playwright / Chromium, and a built sd-model-hub frontend. The test fixture uses temporary directories and does not load Stable Diffusion:

```bash
PYTHONPATH=. python tests/browser_host.py --data-dir /tmp/model-hub-test --dist /path/to/sd_model_hub/webui/dist
# Run in another terminal, then stop the fixture with Ctrl+C after checking:
node tests/browser_smoke.mjs
```

The fixture listens only on `127.0.0.1:17863`, with test credentials `smoke / smoke`. Use `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH`, and `MODEL_HUB_TEST_URL` to specify existing test tools and the target URL.

## License

This project is licensed under [GNU GPLv3](LICENSE).
