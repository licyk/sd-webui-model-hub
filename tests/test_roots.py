from pathlib import Path
from types import SimpleNamespace

import pytest

from sd_webui_model_hub.roots import collect_roots


def destination_path(roots, kind):
    dest = roots.destinations[kind]
    return next(r["path"] for r in roots.roots if r["id"] == dest["root_id"])


def test_a1111_additional_roots_and_download_precedence(host):
    shared, paths = host
    roots = collect_roots(shared, paths, {})
    assert destination_path(roots, "checkpoint") == shared.cmd_opts.ckpt_dir
    assert str(Path(paths.models_path) / "Stable-diffusion") in {r["path"] for r in roots.roots}
    assert destination_path(roots, "lora") == shared.cmd_opts.lora_dir
    assert "text_encoder" not in roots.destinations
    assert "diffusion_model" not in roots.destinations
    assert not Path(paths.models_path).exists()  # Discovery does not create folders.


@pytest.mark.parametrize("scaler_name", ["ESRGAN", "Third-party"])
def test_forge_effective_paths_and_upscaler(host, tmp_path, scaler_name):
    shared, paths = host
    shared.cmd_opts.text_encoder_dir = str(tmp_path / "encoders")
    shared.cmd_opts.vae_dir = str(tmp_path / "vae")
    shared.opts.data["control_net_models_path"] = str(tmp_path / "cn-extra")
    scaler = SimpleNamespace(name=scaler_name, model_path=tmp_path / "upscale-default", user_path=tmp_path / "upscale")
    shared.sd_upscalers = [SimpleNamespace(scaler=scaler), SimpleNamespace(scaler=scaler)]
    modules = {"modules_forge.shared": SimpleNamespace(controlnet_dir=tmp_path / "cn", preprocessor_dir=tmp_path / "annotators")}
    roots = collect_roots(shared, paths, modules)
    assert destination_path(roots, "text_encoder") == shared.cmd_opts.text_encoder_dir
    assert destination_path(roots, "vae") == shared.cmd_opts.vae_dir
    assert destination_path(roots, "upscaler") == str(tmp_path / "upscale")
    assert destination_path(roots, "controlnet") == str(tmp_path / "cn-extra")
    assert roots.destinations["diffusion_model"] == roots.destinations["checkpoint"]
    assert len({r["path"] for r in roots.roots}) == len(roots.roots)


def test_symlink_deduplication_stable_ids_and_mixed_kind(host, tmp_path):
    shared, paths = host
    target = tmp_path / "shared-models"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    shared.cmd_opts.lora_dir = str(target)
    shared.cmd_opts.vae_dir = str(alias)
    roots = collect_roots(shared, paths, {})
    entries = [r for r in roots.roots if r["path"] == str(target)]
    assert len(entries) == 1 and entries[0]["kind"] is None
    shared.cmd_opts.vae_dir = str(target)
    assert collect_roots(shared, paths, {}).destinations["vae"] == roots.destinations["vae"]


def test_a1111_optional_controlnet_discovery(host, tmp_path):
    shared, paths = host
    modules = {"scripts.global_state": SimpleNamespace(cn_models_dir=tmp_path / "controlnet", update_cn_models=lambda: None)}
    roots = collect_roots(shared, paths, modules)
    assert destination_path(roots, "controlnet") == str(tmp_path / "controlnet")


def test_complete_model_directory_preserves_download_destinations(host):
    shared, paths = host
    roots = collect_roots(shared, paths, {})
    complete = next(r for r in roots.roots if r["path"] == str(Path(paths.models_path).resolve()))
    assert complete["name"] == "全部模型目录"
    assert complete["layout"] == "sd-webui" and complete["kind"] is None
    assert roots.roots[0]["path"] == str(Path(paths.models_path) / "Stable-diffusion")
    assert destination_path(roots, "checkpoint") == shared.cmd_opts.ckpt_dir
    assert destination_path(roots, "lora") == shared.cmd_opts.lora_dir
    assert all(d["root_id"] != complete["id"] for d in roots.destinations.values())
    assert None not in roots.destinations
    assert not Path(paths.models_path).exists()


def test_complete_directory_merges_with_existing_custom_destination(host):
    shared, paths = host
    shared.cmd_opts.ckpt_dir = paths.models_path
    roots = collect_roots(shared, paths, {})
    entries = [r for r in roots.roots if r["path"] == str(Path(paths.models_path).resolve())]
    assert len(entries) == 1
    assert entries[0]["name"] == "全部模型目录"
    assert entries[0]["kind"] is None and entries[0]["layout"] == "sd-webui"
    assert roots.destinations["checkpoint"] == {"root_id": entries[0]["id"], "rel_dir": ""}
