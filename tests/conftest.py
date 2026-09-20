from types import SimpleNamespace

import pytest

from sd_webui_model_hub import host as host_module


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setattr(host_module, "DATA_DIR", tmp_path / "extension" / "data")
    shared = SimpleNamespace(
        cmd_opts=SimpleNamespace(
            ckpt_dir=str(tmp_path / "custom-checkpoints"),
            vae_dir=None,
            lora_dir=str(tmp_path / "custom-loras"),
            lyco_dir_backcompat=str(tmp_path / "models" / "LyCORIS"),
            embeddings_dir=str(tmp_path / "embeddings"),
            hypernetwork_dir=str(tmp_path / "models" / "hypernetworks"),
            listen=False,
            share=False,
            api_auth=None,
        ),
        opts=SimpleNamespace(data={}),
        sd_upscalers=[],
        state=SimpleNamespace(job_count=0, job=""),
    )
    paths = SimpleNamespace(models_path=str(tmp_path / "models"), data_path=str(tmp_path / "data"))
    return shared, paths
