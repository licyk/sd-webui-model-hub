# SD WebUI Model Hub

Stable Diffusion WebUI（A1111）和 Forge 的模型管理、下载扩展，使用 `sd-model-hub>=0.1.1,<0.2`。

扩展在 **Model Hub** 标签页中嵌入 sd-model-hub 的原生界面，提供模型来源搜索、直链下载、Hugging Face / ModelScope 仓库下载、下载队列，以及本地模型浏览、识别、移动、重命名和删除。具体模型来源和下载能力由 sd-model-hub 提供。

## 安装

将本目录放在 WebUI 的 `extensions/sd-webui-model-hub` 下，然后完整重启 WebUI。

`install.py` 会通过 WebUI 的 `launch.run_pip` 安装 `requirements.txt` 中的依赖。安装和运行均使用 **WebUI 自身的 Python 环境**。满足版本要求时不会重复安装；不主动升级其他宿主依赖。使用 `--skip-install` 时，需要自行在同一环境安装依赖。

依赖发行包必须包含 `sd_model_hub/webui/dist`。如果从 sd-model-hub 源码安装，先按该库说明构建前端，再用 WebUI 的 Python 安装源码目录；本扩展不另行构建或复制 Vue 界面。缺少前端资源时，标签页会显示提示。

本扩展要求 Python 3.10 或更新版本。

## 使用

1. 打开 **Model Hub** 标签页，直接使用模型管理界面；在“本地模型”中选择模型目录。
2. 在原生界面搜索模型、选择仓库文件或输入下载链接。已识别的模型类型会推荐对应目录；无法识别的直链文件请手动选择目录。
3. 默认在下载完成或本地模型变化后自动刷新 WebUI 的模型列表，生成任务进行中会等待空闲。

刷新通过宿主已有的 Gradio 按钮进行，覆盖 Checkpoint、VAE、Extra Networks 和可用的 ControlNet 控件。每个浏览器页面独立接收更新，不自动选择或加载下载的模型。没有对应刷新控件的组件，以及部分放大模型，需要手动刷新或重启 WebUI。

标签页直接显示 Model Hub 界面，不附加工具栏、连接成功提示或模型目录路径。连接失败、登录失效或缺少前端资源时才显示错误提示。
独立访问原生界面也沿用 WebUI 登录；自动刷新宿主选择列表需要保留一个 WebUI 页面。

## 模型目录

扩展读取宿主运行时配置，而不是假定所有模型都在默认 `models` 文件夹：

本地模型的根目录下拉框还提供“全部模型目录”，指向宿主实际的 `models_path`。
便携包使用重定向后的模型目录，可从此入口逐级浏览所有子目录，包括未注册的自定义分类。
原有分类入口和各类型的下载位置保持有效；根目录外的自定义模型路径仍通过各自入口访问。

| 模型类型 | 目录来源 |
| --- | --- |
| Checkpoint | `sd_models.model_path` 和 `--ckpt-dir`；自定义目录优先用于下载 |
| VAE | 默认 VAE 目录和 `--vae-dir` |
| LoRA / LyCORIS | `--lora-dir`、`--lyco-dir-backcompat` |
| Embedding / Hypernetwork | `--embeddings-dir`、`--hypernetwork-dir` |
| Forge diffusion model | 使用 Checkpoint 下载目录 |
| Forge text encoder | `models/text_encoder` 和 `--text-encoder-dir` |
| ControlNet | 已加载的 ControlNet / Forge 模块目录、启动参数和额外目录设置 |
| Forge preprocessor | Forge 的实际预处理器目录 |
| Upscaler | 已注册放大器的模型目录和自定义目录 |

重复目录（包括指向同一位置的符号链接）合并，目录 ID 在重启后保持稳定。目录列表由宿主管理，在 Model Hub 中锁定；修改 WebUI 启动参数或目录配置后应完整重启。类型提示不会覆盖 sd-model-hub 的文件识别结果。目录接入不代表宿主能够加载任意模型架构。

扩展数据保存在 `<WebUI data_path>/model-hub/`，包括 `settings.toml`、数据库、下载记录和缓存；模型文件直接写入上述模型目录。是否生成 WebUI 模型侧车元数据可在 sd-model-hub 的下载设置中启用。

## 设置与部署

WebUI **Settings → SD Model Hub** 提供：

- 下载完成或模型变化后自动刷新 WebUI 模型列表。
- 反向代理外部地址，用于 OAuth。例如 `https://example.com/webui/sd-model-hub`，必须包含 WebUI 子路径及扩展路径；修改后完整重启。OAuth 客户端配置仍在 sd-model-hub 中设置。

服务在 WebUI 原有 HTTP 服务的 `/sd-model-hub/` 下运行，不启动第二个 HTTP 服务。使用 WebUI 子路径时，浏览器地址为 `<WebUI 子路径>/sd-model-hub/`。反向代理需要同时转发该路径下的 HTTP 和 WebSocket。

开启 Gradio 登录时，整个扩展（包括静态页面、API 和 WebSocket）校验宿主会话，兼容 Gradio 3 和 4 的 cookie 格式。不单独要求 sd-model-hub token。API-only 模式沿用 `--api-auth` 的 HTTP Basic 登录。普通图形界面模式使用 Gradio 登录，`--api-auth` 不替代图形界面的认证。

扩展提供与本机模型管理相同的文件操作权限，适合受信任的 WebUI 用户。锁定模型根目录仅用于宿主目录配置，不是文件系统沙箱；sd-model-hub 本身允许显式下载路径和本地导入。

## 开发与验证

`scripts/model_hub_setup.py` 注册 WebUI 回调，`sd_webui_model_hub/` 负责宿主适配，`javascript/model_hub.js` 负责 iframe 和刷新控件。不会修改宿主或 sd-model-hub 源文件。

安装开发依赖后，在能导入 sd-model-hub 的环境运行：

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
node --check javascript/model_hub.js
node --test tests/test_panel.mjs
```

测试覆盖目录映射、版本判断、两种 Gradio 会话、API-only 认证、挂载子路径、Socket.IO、真实下载工作线程、宿主变更通知、简化的嵌入界面及生命周期清理。测试使用临时目录和模拟的 HTTP 模型源，不读取或下载真实模型权重。

子应用在首次已认证请求时，于 WebUI 当前事件循环中启动。标准宿主 shutdown、服务器事件循环退出和脚本卸载均有清理路径，以适配 Forge 在服务器启动后才调用 `on_app_started` 的时序。

可选浏览器检查需要 Gradio 4、Playwright / Chromium 和已构建的 sd-model-hub 前端。测试夹具使用临时目录，不加载 Stable Diffusion：

```bash
PYTHONPATH=. python tests/browser_host.py --data-dir /tmp/model-hub-test --dist /path/to/sd_model_hub/webui/dist
# 在另一个终端运行，检查完成后用 Ctrl+C 停止夹具：
node tests/browser_smoke.mjs
```

夹具仅监听 `127.0.0.1:17863`，测试登录为 `smoke / smoke`。可通过 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH`、`MODEL_HUB_TEST_URL` 指定现有测试工具和地址。

## 协议

本项目采用 [GNU GPLv3](LICENSE)。协议文件复制自 sd-webui-all-in-one 项目。
