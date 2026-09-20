"""Read effective host directories without importing optional model loaders."""

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HostRoots:
    roots: list[dict] = field(default_factory=list)
    destinations: dict[str, dict] = field(default_factory=dict)
    default_library_root: str | None = None

    def add(self, path, name: str, kind: str | None, preferred: bool = False, *, layout: str = "custom") -> str | None:
        if not path:
            return
        path = str(Path(path).expanduser().resolve())
        existing = next((r for r in self.roots if os.path.normcase(r["path"]) == os.path.normcase(path)), None)
        if existing is None:
            existing = {
                "id": "webui-" + hashlib.sha256(os.path.normcase(path).encode()).hexdigest()[:16],
                "name": name,
                "path": path,
                "layout": layout,
                "kind": kind,
            }
            self.roots.append(existing)
        elif kind is None:
            existing.update(name=name, layout=layout, kind=None)
        elif existing["kind"] != kind:
            # A shared directory must not mislabel every unknown file as one kind.
            existing["kind"] = None
        if kind is not None and (preferred or kind not in self.destinations):
            self.destinations[kind] = {"root_id": existing["id"], "rel_dir": ""}
        return existing["id"]


def collect_roots(shared, paths, loaded: dict) -> HostRoots:
    """Command-line overrides win for downloads; additional scan roots stay visible."""
    roots = HostRoots()
    cmd = shared.cmd_opts
    models = Path(paths.models_path)

    def attr(module, name, default=None):
        return getattr(loaded.get(module), name, default)

    roots.add(attr("modules.sd_models", "model_path", models / "Stable-diffusion"), "Checkpoint", "checkpoint")
    roots.add(getattr(cmd, "ckpt_dir", None), "Checkpoint (custom)", "checkpoint", True)
    roots.add(attr("modules.sd_vae", "vae_path", models / "VAE"), "VAE", "vae")
    roots.add(getattr(cmd, "vae_dir", None), "VAE (custom)", "vae", True)
    roots.add(getattr(cmd, "lora_dir", None), "LoRA", "lora")
    roots.add(getattr(cmd, "lyco_dir_backcompat", None), "LyCORIS", "lora")
    roots.add(getattr(cmd, "embeddings_dir", None), "Textual inversion", "embedding")
    roots.add(getattr(cmd, "hypernetwork_dir", None), "Hypernetworks", "hypernetwork")

    if "modules_forge.main_entry" in loaded or "modules_forge.shared" in loaded:
        roots.destinations["diffusion_model"] = dict(roots.destinations["checkpoint"])
        roots.add(models / "text_encoder", "Text encoder", "text_encoder")
        roots.add(getattr(cmd, "text_encoder_dir", None), "Text encoder (custom)", "text_encoder", True)
        roots.add(attr("modules_forge.shared", "controlnet_dir"), "ControlNet", "controlnet")
        roots.add(attr("modules_forge.shared", "preprocessor_dir"), "ControlNet preprocessor", "annotator")
    # The A1111 ControlNet extension exposes cn_models_dir; Forge exposes controlnet_dir.
    for module_name, module in tuple(loaded.items()):
        if (module_name.endswith("controlnet.global_state") or module_name == "scripts.global_state") and (
            callable(getattr(module, "update_cn_models", None)) or callable(getattr(module, "update_controlnet_filenames", None))
        ):
            roots.add(getattr(module, "cn_models_dir", None), "ControlNet", "controlnet")
            roots.add(getattr(module, "controlnet_dir", None), "ControlNet", "controlnet")
    roots.add(shared.opts.data.get("control_net_models_path"), "ControlNet (settings)", "controlnet", True)
    roots.add(getattr(cmd, "controlnet_dir", None), "ControlNet (custom)", "controlnet", True)

    # Scalers carry their effective paths, including third-party and command-line ones.
    for item in getattr(shared, "sd_upscalers", []):
        scaler = getattr(item, "scaler", None)
        name = getattr(scaler, "name", None) or "Upscaler"
        preferred = name == "ESRGAN" or "upscaler" not in roots.destinations
        roots.add(getattr(scaler, "model_path", None), name, "upscaler", preferred)
        roots.add(getattr(scaler, "user_path", None), name + " (custom)", "upscaler", preferred)
    # Register the complete host directory without replacing per-kind download destinations
    # or the existing first-root fallback for downloads whose kind is unknown.
    roots.default_library_root = roots.add(models, "全部模型目录", None, layout="sd-webui")
    return roots
